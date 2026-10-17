import os, secrets, hmac, re, io, time, threading, warnings
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode
import requests
import cloudinary, cloudinary.api, cloudinary.uploader
from cloudinary.exceptions import Error, NotFound
from PIL import Image, ImageOps, UnidentifiedImageError
from flask import Flask, session, redirect, request, abort, jsonify, render_template_string

app = Flask(__name__)
secret = os.environ.get('SESSION_SECRET', '')
if len(secret) < 32:
    raise RuntimeError('Set SESSION_SECRET to at least 32 random characters')
app.config.update(SECRET_KEY=secret, SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=6*1024*1024)
CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID', '1560918278493184102').strip()
CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET', '').strip()
BASE = os.environ.get('APP_URL', '').strip().rstrip('/')
CALLBACK = os.environ.get('DISCORD_REDIRECT_URI', BASE + '/auth/discord/callback').strip()
OWNER = os.environ.get('OWNER_DISCORD_ID', '603378750738137088').strip()
EDITORS = {v.strip() for v in os.environ.get('EDITOR_DISCORD_IDS', '1081902407501479946').split(',') if v.strip()} | {OWNER}
PUBLIC_ID = 'luka-discord-site/hero'
Image.MAX_IMAGE_PIXELS = 15000000
cache = {'until': 0, 'url': None}
lock = threading.Lock()

def can_edit():
    return session.get('uid') in EDITORS

def csrf_ok():
    return bool(session.get('csrf')) and hmac.compare_digest(session['csrf'], request.form.get('csrf', '') or request.headers.get('X-CSRF-Token', ''))

def storage():
    if not os.environ.get('CLOUDINARY_URL', '').strip():
        raise ValueError('Storage not configured')
    cloudinary.config(secure=True)

@app.after_request
def security(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' https://res.cloudinary.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    return response

@app.get('/health')
def health():
    return jsonify(ok=True)

@app.get('/')
def home():
    page = Path(__file__).with_name('index.html').read_text(encoding='utf-8')
    page = re.sub(r'<script\b[^>]*>.*?</script>', '', page, flags=re.S)
    page = re.sub(r'<button[^>]*id="upload"[^>]*>.*?</button>', '', page, flags=re.S)
    page = re.sub(r'<input[^>]*id="file"[^>]*>', '', page)
    page = re.sub(r'<p class="note">Local preview only.*?</p>', '', page, flags=re.S)
    controls = '<aside style="text-align:center;padding:20px">'
    if session.get('uid'):
        if can_edit():
            controls += '<a class="btn pink" href="/editor">Edit website</a> '
        csrf = session.setdefault('csrf', secrets.token_urlsafe(32))
        controls += '<form action="/logout" method="post" style="display:inline"><input type="hidden" name="csrf" value="' + csrf + '"><button class="btn">Sign out</button></form>'
    else:
        controls += '<a class="btn pink" href="/auth/discord">Sign in with Discord</a>'
    controls += '</aside>'
    script = '''<script>fetch('/api/public-artwork').then(r=>r.json()).then(d=>{if(d.url){const a=document.getElementById('art');a.onload=()=>{a.hidden=false;document.getElementById('placeholder').hidden=true};a.src=d.url}}).catch(()=>{});const b=document.getElementById('copy');if(b)b.onclick=async()=>{const s=document.getElementById('status');try{await navigator.clipboard.writeText('https://discord.gg/ct7AS7m9RP');s.textContent='Copied! Ready to share ♡'}catch(e){s.textContent='Copy this link: https://discord.gg/ct7AS7m9RP'}};</script>'''
    return page.replace('</body>', controls + script + '</body>')

@app.get('/auth/discord')
def login():
    if not CLIENT_SECRET or not BASE.startswith('https://') or not CALLBACK.startswith(BASE + '/'):
        return 'Discord login is awaiting backend environment configuration.', 503
    session.clear()
    session.permanent = True
    session['state'] = secrets.token_urlsafe(32)
    params = dict(client_id=CLIENT_ID, response_type='code', redirect_uri=CALLBACK, scope='identify', state=session['state'])
    return redirect('https://discord.com/oauth2/authorize?' + urlencode(params))

@app.get('/auth/discord/callback')
def callback():
    expected = session.pop('state', None)
    if not expected or not hmac.compare_digest(expected, request.args.get('state', '')):
        abort(400)
    if not request.args.get('code') or request.args.get('error'):
        return redirect('/')
    try:
        result = requests.post('https://discord.com/api/v10/oauth2/token', data=dict(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, grant_type='authorization_code', code=request.args['code'], redirect_uri=CALLBACK), timeout=15)
        result.raise_for_status()
        token = result.json()['access_token']
        user = requests.get('https://discord.com/api/v10/users/@me', headers={'Authorization': 'Bearer ' + token}, timeout=15)
        user.raise_for_status()
        uid = user.json()['id']
        if not isinstance(uid, str) or not uid.isdigit():
            abort(400)
    except (requests.RequestException, KeyError, ValueError):
        return 'Discord sign-in failed. Please return home and try again.', 502
    session.clear()
    session.permanent = True
    session.update(uid=uid, csrf=secrets.token_urlsafe(32))
    return redirect('/')

@app.post('/logout')
def logout():
    if not csrf_ok():
        abort(403)
    session.clear()
    return redirect('/')

@app.get('/api/public-artwork')
def public_artwork():
    with lock:
        if time.monotonic() >= cache['until']:
            try:
                storage()
                asset = cloudinary.api.resource(PUBLIC_ID, resource_type='image', type='upload', timeout=15)
                cache.update(url=asset['secure_url'], until=time.monotonic()+60)
            except NotFound:
                cache.update(url=None, until=time.monotonic()+60)
            except (Error, ValueError, KeyError):
                return jsonify(url=None), 503
        return jsonify(url=cache['url'])

@app.get('/api/storage-check')
def storage_check():
    if not can_edit():
        abort(403)
    try:
        storage()
        cloudinary.api.ping(timeout=15)
        return jsonify(ok=True, message='Cloudinary connection works.')
    except (Error, ValueError):
        return jsonify(ok=False, message='Cloudinary connection failed. Check CLOUDINARY_URL privately in Render.'), 503

@app.get('/editor')
def editor():
    if not can_edit():
        abort(403)
    token = session.setdefault('csrf', secrets.token_urlsafe(32))
    return render_template_string(EDITOR, csrf=token)

@app.post('/api/artwork')
def artwork():
    if not can_edit() or not csrf_ok():
        abort(403)
    if request.form.get('permission') != 'yes':
        return jsonify(error='Confirm that you have permission to publish this artwork.'), 400
    uploaded = request.files.get('artwork')
    if not uploaded:
        return jsonify(error='Choose a PNG, JPG, or WebP image.'), 400
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(uploaded.stream)
            if image.format not in {'PNG', 'JPEG', 'WEBP'}:
                raise ValueError('Unsupported image format')
            image.load()
            image = ImageOps.exif_transpose(image).convert('RGBA')
            image.thumbnail((2400, 2400))
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            if buffer.tell() > 8*1024*1024:
                raise ValueError('Image too large')
            buffer.seek(0)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return jsonify(error='Use a valid PNG, JPG, or WebP under 5 MB and 15 million pixels.'), 400
    try:
        storage()
        with lock:
            asset = cloudinary.uploader.upload(buffer, public_id=PUBLIC_ID, resource_type='image', type='upload', overwrite=True, invalidate=True, format='png', timeout=30)
            cache.update(url=asset['secure_url'], until=time.monotonic()+60)
        return jsonify(ok=True, url=asset['secure_url'])
    except (Error, ValueError, KeyError):
        return jsonify(error='Saving failed. Check Cloudinary configuration or usage limits, then retry.'), 503

@app.errorhandler(413)
def too_large(error):
    return jsonify(error='Upload is too large. Choose an image under 5 MB.'), 413

EDITOR = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Artwork editor</title><style>body{font:15px Arial;background:#d8f0e5;color:#34564e;padding:30px}main{max-width:600px;margin:auto;background:#fffaf6;border:2px solid #75a18c;border-radius:22px;padding:30px}button,a{display:inline-block;margin:10px 8px 10px 0;padding:12px;border:1px solid #ae5980;border-radius:10px;background:#ffd4e5;color:#63394c;cursor:pointer}label{display:block;line-height:1.8;margin:20px 0}input[type=file]{max-width:100%}img{display:block;max-width:100%;max-height:350px;margin:20px auto}[hidden]{display:none!important}#status{line-height:1.8}</style><main><h1>Change the Luka artwork ♡</h1><p>Saving replaces the shared website image for every visitor. PNG, JPG, or WebP; under 5 MB.</p><button id="check">Check Cloudinary connection</button><form id="form"><input type="hidden" name="csrf" value="{{ csrf }}"><label>Choose artwork <input required type="file" name="artwork" accept="image/png,image/jpeg,image/webp"></label><label><input required type="checkbox" name="permission" value="yes"> I own this artwork or have permission to publish it publicly.</label><button id="save" type="submit">Save image for everyone</button></form><p id="status" role="status"></p><img id="preview" alt="Saved website artwork" hidden><a href="/">Back to website ↗</a></main><script>const status=document.getElementById('status'),preview=document.getElementById('preview');function show(url){if(url){preview.src=url;preview.hidden=false}}fetch('/api/public-artwork').then(r=>r.json()).then(d=>show(d.url)).catch(()=>{});document.getElementById('check').onclick=async()=>{status.textContent='Checking…';try{const r=await fetch('/api/storage-check'),d=await r.json();status.textContent=d.message||'Unable to check connection.'}catch(e){status.textContent='Connection check failed. Try again.'}};document.getElementById('form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,button=document.getElementById('save'),file=form.elements.artwork.files[0];if(!file||file.size>5*1024*1024){status.textContent='Choose an image under 5 MB.';return}button.disabled=true;status.textContent='Saving… Please keep this page open.';try{const r=await fetch('/api/artwork',{method:'POST',body:new FormData(form)}),d=await r.json();if(!r.ok)throw new Error(d.error||'Saving failed.');status.textContent='Saved for everyone! Reload the website to see it.';show(d.url)}catch(e){status.textContent=e.message}finally{button.disabled=false}};</script></html>'''
