import os, io, re, json, time, threading, secrets, hmac
from urllib.parse import urlparse
import requests
import cloudinary, cloudinary.api, cloudinary.uploader
from cloudinary.exceptions import Error, NotFound
from flask import session, request, abort, jsonify, render_template_string

TEXT = {
 'page_title': ('Browser tab title', "Luka's Little Corner · Discord"),
 'site_name': ('Site name', "LUKA'S LITTLE CORNER ♡"),
 'badge': ('Small badge', '✦ A LITTLE FAN-MADE HAPPY PLACE ✦'),
 'headline_top': ('Headline first line', 'oh, hi'),
 'headline_bottom': ('Headline second line', 'Luka.'),
 'subtitle': ('Subtitle', 'a little star in our little universe.'),
 'description': ('Server description', '✿ ART & GFX aspired ✦ Active VCs and chat 🎨 Multifandom engagement 🍰 Showcase your art skills and find new mutuals! LGBTQ+ friendly 🌈 Active events & Giveaways ♫ A lot of original emotes and stickers 🌷'),
 'caption': ('Image caption', 'my favorite little star ★'),
 'ribbon': ('Decorative ribbon text', 'MINT DAYDREAMS ♡ PINK LITTLE HEARTS ★'),
 'community_heading': ('Invitation heading', 'Your invitation is right here ♡'),
 'join_top': ('Main join button', '♡ Join our Discord ↗'),
 'join_bottom': ('Second join button', 'Join the server ↗'),
 'navigation': ('Scroll button', 'Your invitation ↓'),
 'nav_discord': ('Header Discord link', 'Discord ↗'),
 'copy_text': ('Copy invite button', 'Copy invite ♡'),
 'placeholder': ('Empty image message', 'your favorite Luka goes here ♡'),
 'footer': ('Footer text', 'Unofficial fan project. Not affiliated with ALIEN STAGE or its creators. Artwork belongs to its respective artist. Only upload artwork you have permission to use.'),
 'invite': ('Discord invite URL', 'https://discord.gg/ct7AS7m9RP')
}
COLORS = {'background_one': ('Stripe color 1', '#c9eee4'), 'background_two': ('Stripe color 2', '#addbd0'), 'paper': ('Main card color', '#fffdf7'), 'accent': ('Button color', '#ff83b0'), 'headline_color': ('Headline accent', '#e55e95'), 'ink': ('Main text color', '#34564e'), 'community_color': ('Invitation card color', '#fff5fa')}
DEFAULT = {k:v[1] for k,v in {**TEXT, **COLORS}.items()}
DEFAULT.update(font='sans', image_fit='cover')
ID = 'luka-discord-site/settings.json'
CACHE = {'until':0, 'data':None}
LOCK = threading.Lock()

def clean(data):
    if not isinstance(data, dict) or set(data) - set(DEFAULT):
        raise ValueError('Invalid settings fields')
    result = dict(DEFAULT)
    for key, value in data.items():
        if not isinstance(value, str) or len(value) > (4000 if key in {'description','footer'} else 400):
            raise ValueError('A text field is too long or invalid')
        if key in COLORS and not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError('Colors must be six-digit hex colors')
        result[key] = value
    if not re.fullmatch(r'https://discord\.gg/[A-Za-z0-9-]+', result['invite']):
        raise ValueError('Use a Discord invite in the form https://discord.gg/your-code')
    if result['font'] not in {'sans', 'serif'} or result['image_fit'] not in {'cover', 'contain'}:
        raise ValueError('Invalid font or image fit')
    return result

def configure():
    if not os.environ.get('CLOUDINARY_URL', '').strip():
        raise ValueError('Cloudinary is not configured')
    cloudinary.config(secure=True)

def load():
    with LOCK:
        if CACHE['data'] is not None and time.monotonic() < CACHE['until']:
            return dict(CACHE['data'])
        configure()
        try:
            resource = cloudinary.api.resource(ID, resource_type='raw', type='upload', timeout=15)
        except NotFound:
            result = dict(DEFAULT)
        else:
            url = resource['secure_url']
            if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'res.cloudinary.com':
                raise ValueError('Unexpected storage response')
            response = requests.get(url, timeout=15, allow_redirects=False)
            response.raise_for_status()
            if len(response.content) > 40000:
                raise ValueError('Settings too large')
            result = clean(response.json())
        CACHE.update(data=result, until=time.monotonic()+60)
        return dict(result)

def install(app):
    allowed = {os.environ.get('OWNER_DISCORD_ID', '603378750738137088').strip()} | {s.strip() for s in os.environ.get('EDITOR_DISCORD_IDS', '1081902407501479946').split(',') if s.strip()}
    def authorized():
        return session.get('uid') in allowed
    original_home = app.view_functions['home']
    original_editor = app.view_functions['editor']
    app.add_url_rule('/editor/artwork', 'artwork_editor', original_editor)
    def home():
        page = original_home()
        return page.replace('</body>', CLIENT + '</body>')
    app.view_functions['home'] = home
    def editor():
        if not authorized():
            abort(403)
        try:
            values = load()
        except (Error, ValueError, KeyError, requests.RequestException):
            return 'Cannot load page settings from Cloudinary. Check storage before editing. Existing settings were not changed.', 503
        return render_template_string(TEMPLATE, values=values, text=TEXT, colors=COLORS, csrf=session.setdefault('csrf', secrets.token_urlsafe(32)))
    app.view_functions['editor'] = editor
    @app.get('/api/page-settings')
    def public_settings():
        try:
            return jsonify(load())
        except (Error, ValueError, KeyError, requests.RequestException):
            return jsonify(error='Page settings could not be loaded.'), 503
    @app.post('/api/page-settings')
    def save_settings():
        if not authorized() or not session.get('csrf') or not hmac.compare_digest(session['csrf'], request.headers.get('X-CSRF-Token', '')):
            abort(403)
        if request.content_length is None or request.content_length > 40000:
            return jsonify(error='Settings request is too large.'), 400
        try:
            data = clean(request.get_json())
        except (ValueError, TypeError):
            return jsonify(error='Invalid settings. Check field lengths, colors, and the Discord invite URL.'), 400
        try:
            configure()
            with LOCK:
                cloudinary.uploader.upload(io.BytesIO(json.dumps(data, ensure_ascii=False).encode('utf-8')), resource_type='raw', type='upload', public_id=ID, overwrite=True, invalidate=True, timeout=30)
                CACHE.update(data=data, until=time.monotonic()+60)
            return jsonify(ok=True)
        except (Error, ValueError):
            return jsonify(error='Saving failed. Check Cloudinary configuration or limits.'), 503

CLIENT = '''<script>(async()=>{try{const r=await fetch('/api/page-settings');if(!r.ok)return;const d=await r.json();const put=(selector,key)=>{const el=document.querySelector(selector);if(el)el.textContent=d[key]};document.title=d.page_title;put('header a[href="#"]','site_name');put('.pill','badge');const h=document.querySelector('.hero h1');if(h){h.replaceChildren(document.createTextNode(d.headline_top),document.createElement('br'));const s=document.createElement('span');s.textContent=d.headline_bottom;h.append(s)}put('.subtitle','subtitle');put('.description','description');put('.caption','caption');put('.ribbon','ribbon');put('.community h2','community_heading');put('.hero .btn.pink','join_top');put('.community .btn.pink','join_bottom');put('a[href="#community"]','navigation');put('header a[target]','nav_discord');put('#copy','copy_text');put('.placeholder p','placeholder');put('footer','footer');document.querySelectorAll('a[href^="https://discord.gg/"]').forEach(a=>a.href=d.invite);const i=document.querySelector('.invite');if(i)i.textContent=d.invite.replace('https://','');const copy=document.getElementById('copy');if(copy)copy.onclick=async()=>{const s=document.getElementById('status');try{await navigator.clipboard.writeText(d.invite);s.textContent='Copied! Ready to share ♡'}catch(e){s.textContent='Copy this link: '+d.invite}};const css=document.createElement('style');css.textContent='body{background:repeating-linear-gradient(100deg,'+d.background_one+' 0 35px,'+d.background_two+' 35px 65px);color:'+d.ink+';font-family:'+(d.font==='serif'?'Georgia,serif':'Arial,sans-serif')+'}.hero{background:'+d.paper+'}.pink{background:'+d.accent+'}.hero h1 span{color:'+d.headline_color+'}.community{background:'+d.community_color+'}.artbox img{object-fit:'+d.image_fit+'}.description,footer{white-space:pre-wrap}';document.head.append(css)}catch(e){}})();</script>'''

TEMPLATE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Edit website</title><style>body{font:15px Arial;background:#d8f0e5;color:#34564e;padding:25px}main{max-width:750px;margin:auto;background:#fffaf6;padding:30px;border-radius:22px}label{display:block;margin:18px 0;font-weight:bold}textarea,input[type=url],select{display:block;width:100%;margin-top:7px;padding:10px;border:1px solid #9cb8a9;border-radius:8px;font:14px Arial}textarea{min-height:55px;resize:vertical}input[type=color]{display:block;margin-top:8px;width:90px;height:40px}button,a{display:inline-block;margin:8px;padding:12px 18px;background:#ffd4e5;border:1px solid #b86587;border-radius:10px;color:#63394c;cursor:pointer}.colors{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}#status{line-height:1.8}</style><main><h1>Edit your website ♡</h1><p>These settings are public. Never enter passwords, secrets, or private information here. Saving replaces the current page settings for everyone; if two admins edit at once, the last save wins.</p><a href="/editor/artwork">Upload / replace artwork</a><a href="/" target="_blank" rel="noopener">View website ↗</a><form id="settings">{% for key, field in text.items() %}<label>{{ field[0] }}{% if key == 'invite' %}<input required type="url" name="{{ key }}" value="{{ values[key] }}">{% else %}<textarea name="{{ key }}" maxlength="{{ 4000 if key in ['description','footer'] else 400 }}">{{ values[key] }}</textarea>{% endif %}</label>{% endfor %}<h2>Colors</h2><div class="colors">{% for key,field in colors.items() %}<label>{{ field[0] }}<input type="color" name="{{ key }}" value="{{ values[key] }}"></label>{% endfor %}</div><label>Body font<select name="font"><option value="sans" {% if values.font == 'sans' %}selected{% endif %}>Simple sans-serif</option><option value="serif" {% if values.font == 'serif' %}selected{% endif %}>Classic serif</option></select></label><label>Image fit<select name="image_fit"><option value="cover" {% if values.image_fit == 'cover' %}selected{% endif %}>Fill frame (may crop)</option><option value="contain" {% if values.image_fit == 'contain' %}selected{% endif %}>Show entire image</option></select></label><button id="save">Save page for everyone</button></form><p role="status" id="status"></p></main><script>document.getElementById('settings').onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.currentTarget)),b=document.getElementById('save'),s=document.getElementById('status');b.disabled=true;s.textContent='Saving…';try{const r=await fetch('/api/page-settings',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':{{ csrf|tojson }}},body:JSON.stringify(data)}),d=await r.json();if(!r.ok)throw new Error(d.error||'Saving failed.');s.textContent='Saved for everyone! Reload the public website to see your changes.'}catch(e){s.textContent=e.message}finally{b.disabled=false}};</script></html>'''
