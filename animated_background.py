import io, json, secrets, threading, time
from urllib.parse import urlparse, unquote
import requests
import cloudinary.api, cloudinary.uploader
from cloudinary.exceptions import Error, NotFound
from flask import request, session, abort, jsonify, render_template_string

ORIGIN = 'https://pub-64f1c2f5cbd44dcfafc9f94b8c5f743c.r2.dev'
GIF = ORIGIN + '/20a10dab0077e41f9e6ff4bbda0d6815.gif'
ID = 'luka-discord-site/background-settings.json'
DEFAULT = {'mode':'image', 'url':GIF, 'overlay':66}
CACHE = {'data':None, 'until':0}
LOCK = threading.Lock()


def clean(data):
    if not isinstance(data, dict) or set(data) != {'mode','url','overlay'}:
        raise ValueError('Invalid background settings.')
    mode, url, overlay = data['mode'], data['url'], data['overlay']
    if mode not in {'image','plain'} or type(overlay) is not int or not 0 <= overlay <= 85:
        raise ValueError('Choose an image or plain background and an overlay from 0 to 85%.')
    if not isinstance(url,str) or len(url)>2000:
        raise ValueError('The background URL is too long or invalid.')
    if url:
        parsed = urlparse(url)
        if parsed.scheme!='https' or parsed.netloc!=urlparse(ORIGIN).netloc or not unquote(parsed.path).lower().endswith(('.gif','.jpg','.jpeg','.png','.webp')) or parsed.fragment or any(ord(c)<33 or c in "\"'\\()" for c in url):
            raise ValueError('Use a public GIF, JPG, PNG, or WebP URL from your existing R2 bucket.')
    elif mode=='image':
        raise ValueError('Paste the public image URL first.')
    return {'mode':mode, 'url':url, 'overlay':overlay}


def load():
    from app import storage
    with LOCK:
        if CACHE['data'] is not None and time.monotonic()<CACHE['until']:
            return dict(CACHE['data'])
        storage()
        try:
            asset = cloudinary.api.resource(ID, resource_type='raw', type='upload', timeout=15)
        except NotFound:
            data = dict(DEFAULT)
        else:
            url = asset['secure_url']
            if urlparse(url).scheme!='https' or urlparse(url).hostname!='res.cloudinary.com':
                raise ValueError('Unexpected settings storage URL.')
            with requests.get(url, timeout=15, allow_redirects=False, stream=True) as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_content(4096):
                    body.extend(chunk)
                    if len(body)>6000:
                        raise ValueError('Background settings are too large.')
                data = clean(json.loads(body))
        CACHE.update(data=data, until=time.monotonic()+5)
        return dict(data)


def install(application):
    if application.extensions.get('animated_background_ready'):
        return
    from app import can_edit, csrf_ok, storage
    @application.get('/api/background-settings')
    def background_settings():
        try:
            return jsonify(load())
        except (Error, ValueError, KeyError, requests.RequestException):
            return jsonify(error='Background settings could not be loaded.'), 503
    @application.get('/editor/background')
    def background_editor():
        if not can_edit():
            abort(403)
        return render_template_string(EDITOR, csrf=session.setdefault('csrf',secrets.token_urlsafe(32)), defaults=DEFAULT)
    @application.post('/api/background-settings')
    def save_background():
        if not can_edit() or not csrf_ok():
            abort(403)
        if request.content_length is None or request.content_length>6000:
            return jsonify(error='Background settings request is too large.'), 400
        data = request.get_json(silent=True)
        if not isinstance(data,dict) or data.pop('permission',False) is not True:
            return jsonify(error='Confirm permission to display the background publicly.'), 400
        try:
            data = clean(data)
        except (ValueError, TypeError):
            return jsonify(error='Use a supported image URL from your R2 bucket and a valid overlay.'), 400
        try:
            storage()
            with LOCK:
                cloudinary.uploader.upload(io.BytesIO(json.dumps(data).encode('utf-8')), public_id=ID, resource_type='raw', type='upload', overwrite=True, invalidate=True, timeout=30)
                CACHE.update(data=data, until=time.monotonic()+5)
            return jsonify(ok=True)
        except (Error, ValueError):
            return jsonify(error='Saving failed. Check settings storage and try again.'), 503
    def allow_background(response):
        policy = response.headers.get('Content-Security-Policy','')
        if policy:
            parts = [part.strip() for part in policy.split(';') if part.strip()]
            for i,part in enumerate(parts):
                if part.split()[0]=='img-src':
                    if ORIGIN not in part.split()[1:]:
                        parts[i]+=' '+ORIGIN
                    break
            else:
                parts.append("img-src 'self' https://res.cloudinary.com "+ORIGIN)
            response.headers['Content-Security-Policy']='; '.join(parts)
        return response
    application.after_request_funcs.setdefault(None,[]).insert(0,allow_background)
    import design_studio
    design_studio.UI = design_studio.UI.replace('<h2>Layers</h2>','<p><a href="/editor/background">Background ↗</a></p><h2>Layers</h2>',1)
    application.jinja_env.parse(MARKUP)
    application.jinja_env.parse(EDITOR)
    application.extensions['animated_background_ready']=True


def markup():
    return render_template_string(MARKUP, defaults=DEFAULT)


MARKUP = r'''<style>body{isolation:isolate}#site-animated-bg{position:fixed;inset:0;z-index:-1;pointer-events:none;background-color:#211332;background-image:linear-gradient(#130d29aa,#130d29aa);background-position:center;background-repeat:no-repeat;background-size:cover}#background-motion{position:fixed;top:64px;right:12px;z-index:1190;padding:8px 12px;border:1px solid #b991d1;border-radius:12px;background:#241534ed;color:#fff;font:12px Arial;cursor:pointer}.wrap>header,.wrap>footer,.wrap>.ribbon{color:#fff;text-shadow:0 1px 4px #000}@media print{ #site-animated-bg,#background-motion{display:none}}</style><div id="site-animated-bg" aria-hidden="true"></div><button id="background-motion" type="button" hidden>Pause background</button><script>(()=>{const layer=document.getElementById('site-animated-bg'),button=document.getElementById('background-motion'),preference=matchMedia('(prefers-reduced-motion: reduce)');let settings={{ defaults|tojson }},paused=false;try{paused=localStorage.getItem('luka-background-paused')==='1'}catch(e){}function apply(){const active=settings.mode==='image'&&settings.url,running=active&&!paused&&!preference.matches,shade='linear-gradient(rgba(19,13,41,'+settings.overlay/100+'),rgba(19,13,41,'+settings.overlay/100+'))';layer.style.backgroundImage=running?shade+',url('+JSON.stringify(settings.url)+')':shade;button.hidden=!active||preference.matches;button.textContent=running?'Pause background':'Play background';button.setAttribute('aria-label',running?'Pause background and use a plain background':'Show background')}button.onclick=()=>{paused=!paused;try{localStorage.setItem('luka-background-paused',paused?'1':'0')}catch(e){}apply()};if(preference.addEventListener)preference.addEventListener('change',apply);else if(preference.addListener)preference.addListener(apply);fetch('/api/background-settings',{cache:'no-store'}).then(async r=>{const data=await r.json();if(!r.ok)throw new Error();if(!['image','plain'].includes(data.mode)||!Number.isInteger(data.overlay)||data.overlay<0||data.overlay>85)throw new Error();settings=data;apply()}).catch(()=>apply())})();</script>'''

EDITOR = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Background editor</title><style>body{font:16px/1.6 Arial;background:#ded1ea;color:#352244;padding:22px}main{max-width:760px;margin:auto;background:#fffaf7;padding:25px;border-radius:20px}label{display:block;margin:18px 0}input[type=url],select{display:block;width:100%;box-sizing:border-box;padding:10px}button{padding:10px 14px;margin:6px 6px 6px 0;border:1px solid #a984bf;border-radius:10px;background:#ead8f5;cursor:pointer}fieldset{border:0;padding:0}#bg-preview{position:relative;min-height:220px;border-radius:14px;background:#211332 center/cover no-repeat;overflow:hidden}#bg-shade{position:absolute;inset:0;background:#130d29;pointer-events:none}#preview-error{color:#9e254e}</style><main><h1>Background ♡</h1><p>Paste a public GIF, JPG, PNG, or WebP link from your existing R2 bucket. This saves a shared background for all visitors without redeploying. The media stays in R2; only these small settings are stored in Cloudinary. If two editors save, the last save wins.</p><form id="bg-form"><fieldset id="bg-fields" disabled><label>Background mode<select id="bg-mode"><option value="image">Image / animated GIF</option><option value="plain">Plain background</option></select></label><label>R2 public image URL<input id="bg-url" type="url" maxlength="2000" placeholder="https://pub-…r2.dev/background.gif"></label><label>Dark overlay: <output id="bg-percent">66%</output><input id="bg-overlay" type="range" min="0" max="85" step="1" value="66"></label><button id="bg-default" type="button">Restore current GIF</button><button id="bg-plain" type="button">Use plain background</button><button id="bg-preview-button" type="button">Preview</button><div id="bg-preview" aria-label="Background preview"><div id="bg-shade"></div></div><p id="preview-error" role="status"></p><label><input id="bg-permission" type="checkbox" required> I own this media or have permission to display it publicly.</label><button type="submit">Save background for everyone</button></fieldset></form><p id="bg-status" role="status" aria-live="polite">Loading current settings…</p><a href="/studio">Back to Studio</a> · <a href="/" target="_blank" rel="noopener">View website</a></main><script>(()=>{const defaults={{ defaults|tojson }},mode=document.getElementById('bg-mode'),url=document.getElementById('bg-url'),overlay=document.getElementById('bg-overlay'),percent=document.getElementById('bg-percent'),preview=document.getElementById('bg-preview'),shade=document.getElementById('bg-shade'),error=document.getElementById('preview-error'),status=document.getElementById('bg-status'),fields=document.getElementById('bg-fields');let ticket=0;function read(){const result={mode:mode.value,url:url.value.trim(),overlay:Number(overlay.value)};if(result.mode==='image'){const parsed=new URL(result.url);if(parsed.origin!==new URL(defaults.url).origin||!['.gif','.jpg','.jpeg','.png','.webp'].some(ext=>decodeURIComponent(parsed.pathname).toLowerCase().endsWith(ext)))throw new Error('Use an image URL from your existing R2 bucket.')}return result}function show(data){mode.value=data.mode;url.value=data.url;overlay.value=data.overlay;percent.textContent=data.overlay+'%';shade.style.opacity=data.overlay/100}async function draw(){const current=++ticket;error.textContent='';preview.style.backgroundImage='none';try{const data=read();shade.style.opacity=data.overlay/100;if(data.mode==='plain')return;const image=new Image();image.onload=()=>{if(current===ticket)preview.style.backgroundImage='url('+JSON.stringify(data.url)+')'};image.onerror=()=>{if(current===ticket)error.textContent='Could not load this image. Check that the link is public and points directly to an image.'};image.src=data.url}catch(e){error.textContent=e.message}}overlay.oninput=()=>{percent.textContent=overlay.value+'%';shade.style.opacity=Number(overlay.value)/100};document.getElementById('bg-preview-button').onclick=draw;mode.onchange=draw;document.getElementById('bg-default').onclick=()=>{show(defaults);draw()};document.getElementById('bg-plain').onclick=()=>{mode.value='plain';draw()};document.getElementById('bg-form').onsubmit=async e=>{e.preventDefault();try{const data=read();data.permission=document.getElementById('bg-permission').checked;fields.disabled=true;status.textContent='Saving shared background…';const r=await fetch('/api/background-settings',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':{{ csrf|tojson }}},body:JSON.stringify(data)});let result;try{result=await r.json()}catch(e){throw new Error('Unexpected server response. Check your sign-in.')}if(!r.ok)throw new Error(result.error||'Saving failed.');status.textContent='Saved for everyone! Allow up to five seconds for other server workers, then reload the website. Preview, Restore, and Plain buttons do not save until you press Save.'}catch(e){status.textContent=e.message}finally{fields.disabled=false}};fetch('/api/background-settings',{cache:'no-store'}).then(async r=>{const data=await r.json();if(!r.ok)throw new Error(data.error||'Loading failed.');show(data);fields.disabled=false;status.textContent='Ready. Preview changes, then Save to publish them.';draw()}).catch(e=>{status.textContent=e.message+' Reload this page to retry; existing settings were not changed.'})})();</script></html>'''
