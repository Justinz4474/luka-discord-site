import os, secrets, hmac
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode
import requests
from flask import Flask, session, redirect, request, abort, jsonify

app = Flask(__name__)
secret = os.environ.get('SESSION_SECRET', '')
if len(secret) < 32:
    raise RuntimeError('Set SESSION_SECRET to at least 32 random characters')
app.config.update(SECRET_KEY=secret, SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=8 * 1024 * 1024)
CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID', '1560918278493184102')
CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET', '')
BASE = os.environ.get('APP_URL', '').rstrip('/')
CALLBACK = os.environ.get('DISCORD_REDIRECT_URI', BASE + '/auth/discord/callback')
OWNER = os.environ.get('OWNER_DISCORD_ID', '603378750738137088')
EDITORS = {v.strip() for v in os.environ.get('EDITOR_DISCORD_IDS', '1081902407501479946').split(',') if v.strip()} | {OWNER}

def can_edit():
    return session.get('uid') in EDITORS

@app.after_request
def security(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    return response

@app.get('/health')
def health():
    return jsonify(ok=True)

@app.get('/')
def home():
    page = Path(__file__).with_name('index.html').read_text(encoding='utf-8')
    controls = '<aside style="text-align:center;padding:20px">'
    if session.get('uid'):
        if can_edit():
            controls += '<a class="btn pink" href="/editor">Edit website</a> '
        csrf = session.setdefault('csrf', secrets.token_urlsafe(32))
        controls += '<form action="/logout" method="post" style="display:inline"><input type="hidden" name="csrf" value="' + csrf + '"><button class="btn">Sign out</button></form>'
    else:
        controls += '<a class="btn pink" href="/auth/discord">Sign in with Discord</a>'
    controls += '</aside>'
    return page.replace('</body>', controls + '</body>')

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
    supplied = request.args.get('state', '')
    if not expected or not hmac.compare_digest(expected, supplied):
        abort(400)
    code = request.args.get('code')
    if not code or request.args.get('error'):
        return redirect('/')
    try:
        result = requests.post('https://discord.com/api/v10/oauth2/token', data=dict(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, grant_type='authorization_code', code=code, redirect_uri=CALLBACK), timeout=15)
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
    session['uid'] = uid
    session['csrf'] = secrets.token_urlsafe(32)
    return redirect('/')

@app.post('/logout')
def logout():
    if not hmac.compare_digest(session.get('csrf', ''), request.form.get('csrf', '')) or not session.get('csrf'):
        abort(403)
    session.clear()
    return redirect('/')

@app.get('/editor')
def editor():
    if not can_edit():
        abort(403)
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Editor setup</title><body style="font-family:Arial;background:#e0f4eb;color:#34564e;padding:40px"><h1>Editor access confirmed</h1><p>Your Discord account is approved.</p><p>Permanent image storage is not connected yet. Image publishing is disabled until that setup is complete.</p><a href="/">Back to website</a></body></html>'

@app.post('/api/artwork')
def artwork():
    if not can_edit():
        abort(403)
    if not session.get('csrf') or not hmac.compare_digest(session['csrf'], request.headers.get('X-CSRF-Token', '')):
        abort(403)
    return jsonify(error='Permanent image storage has not been configured. No image was saved.'), 503
