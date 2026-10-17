import io, time, threading, secrets
from urllib.parse import urlparse
import cloudinary.api, cloudinary.uploader
from cloudinary.exceptions import Error, NotFound
from flask import session, request, abort, jsonify, render_template_string

ID = 'luka-discord-site/background-music'
LOCK = threading.Lock()
CACHE = {'until':0, 'url':None}
PLAYLIST = 'https://open.spotify.com/embed/playlist/053m37Mlzoi9kI5Nq3qHMH'


def install(application):
    if application.extensions.get('music_controls_ready'):
        return
    from app import can_edit, csrf_ok, storage
    @application.get('/api/background-music')
    def background_music():
        with LOCK:
            if time.monotonic() >= CACHE['until']:
                try:
                    storage()
                    asset = cloudinary.api.resource(ID, resource_type='video', type='upload', timeout=15)
                    url = asset['secure_url']
                    if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'res.cloudinary.com':
                        raise ValueError('Unexpected audio URL')
                    CACHE.update(url=url, until=time.monotonic()+60)
                except NotFound:
                    CACHE.update(url=None, until=time.monotonic()+60)
                except (Error, ValueError, KeyError):
                    return jsonify(error='Entrance music is unavailable.'), 503
            return jsonify(url=CACHE['url'])
    @application.get('/editor/music')
    def music_editor():
        if not can_edit():
            abort(403)
        return render_template_string(EDITOR, csrf=session.setdefault('csrf', secrets.token_urlsafe(32)))
    @application.post('/api/background-music')
    def save_music():
        if not can_edit() or not csrf_ok():
            abort(403)
        if request.form.get('permission') != 'yes':
            return jsonify(error='Confirm that you have permission to publish the audio.'), 400
        uploaded = request.files.get('music')
        if not uploaded or not uploaded.filename.lower().endswith('.mp3'):
            return jsonify(error='Choose an MP3 file under 5 MB.'), 400
        data = uploaded.stream.read(5*1024*1024+1)
        if not data or len(data)>5*1024*1024:
            return jsonify(error='Choose an MP3 file under 5 MB.'), 400
        if not (data[:3]==b'ID3' or len(data)>1 and data[0]==255 and data[1]&224==224):
            return jsonify(error='This does not appear to be an MP3 file.'), 400
        try:
            storage()
            with LOCK:
                asset = cloudinary.uploader.upload(io.BytesIO(data), public_id=ID, resource_type='video', type='upload', format='mp3', overwrite=True, invalidate=True, timeout=30)
                CACHE.update(url=asset['secure_url'], until=time.monotonic()+60)
            return jsonify(ok=True)
        except (Error, ValueError, KeyError):
            return jsonify(error='Audio validation or saving failed. Check the file and Cloudinary configuration.'), 503
    def permit_players(response):
        policy = response.headers.get('Content-Security-Policy', '')
        if policy:
            response.headers['Content-Security-Policy'] = policy + '; frame-src https://open.spotify.com; media-src \'self\' https://res.cloudinary.com'
        return response
    application.after_request_funcs.setdefault(None, []).insert(0, permit_players)
    import design_studio
    design_studio.UI = design_studio.UI.replace('<h2>Layers</h2>', '<p><a href="/editor/music">Upload / replace entrance music ↗</a></p><h2>Layers</h2>', 1)
    application.jinja_env.parse(PLAYER)
    application.jinja_env.parse(EDITOR)
    application.extensions['music_controls_ready'] = True


def homepage_markup(admin):
    return render_template_string(PLAYER, admin=admin, playlist=PLAYLIST)


PLAYER = r'''<style>#site-music{position:fixed;bottom:12px;left:12px;z-index:1200;width:min(350px,calc(100vw - 24px));background:#fffaf7;color:#34564e;border:1px solid #ba7999;border-radius:15px;padding:10px 13px;box-shadow:0 4px 16px #34564e22;font:13px/1.6 Arial}#site-music summary{cursor:pointer;font-weight:bold}#site-music button{margin:5px 4px 5px 0;padding:7px 10px;border:1px solid #b96c8d;border-radius:9px;background:#ffdeeb;color:#63354c;font:13px Arial;cursor:pointer}#site-music button:disabled{opacity:.5;cursor:default}#site-music iframe{width:100%;height:352px;border:0;border-radius:12px;margin-top:8px}#site-music p{margin:5px 0}#site-music [hidden]{display:none!important}</style><details id="site-music"><summary>♫ Music · Spotify & entrance audio</summary><p id="music-state" role="status" aria-live="polite">Checking entrance music…</p><div id="music-background" hidden><audio id="entrance-audio" preload="none" loop></audio><button id="music-toggle" type="button">Enter with music ♡</button><button id="music-mute" type="button">Mute</button><label>Volume <input id="music-volume" type="range" min="0" max="1" step="0.05" value="0.35" aria-label="Entrance music volume"></label></div><button id="music-spotify" type="button">Open Spotify playlist</button><div id="music-embed"></div><p>Spotify needs its own Play action. Switching to Spotify pauses entrance music; starting entrance music closes the Spotify player.</p>{% if admin %}<a href="/editor/music">Upload / replace entrance MP3 ↗</a>{% endif %}</details><script>(()=>{
const audio=document.getElementById('entrance-audio'),toggle=document.getElementById('music-toggle'),state=document.getElementById('music-state'),volume=document.getElementById('music-volume'),embed=document.getElementById('music-embed');let available=false,optedOut=false;try{optedOut=localStorage.getItem('luka-music-off')==='1';const v=Number(localStorage.getItem('luka-music-volume')??.35);audio.volume=Number.isFinite(v)?Math.max(0,Math.min(1,v)):.35}catch(e){audio.volume=.35}volume.value=audio.volume;const rememberOff=value=>{try{localStorage.setItem('luka-music-off',value?'1':'0')}catch(e){}};
audio.onplay=()=>{document.getElementById('site-music').open=true;toggle.textContent='Pause music';state.textContent='Entrance music is playing.'};audio.onpause=()=>{toggle.textContent='Play music ♡'};audio.onerror=()=>{state.textContent='Entrance audio could not be played. The Spotify playlist is still available.'};
async function play(){if(!available)return;embed.replaceChildren();try{await audio.play();rememberOff(false)}catch(e){toggle.textContent='Enter with music ♡';state.textContent='Tap Enter with music to start audio. Your browser may block automatic playback.'}}
toggle.onclick=()=>{if(audio.paused)play();else{audio.pause();rememberOff(true);state.textContent='Entrance music paused.'}};document.getElementById('music-mute').onclick=e=>{audio.muted=!audio.muted;e.currentTarget.textContent=audio.muted?'Unmute':'Mute'};volume.oninput=()=>{audio.volume=Number(volume.value);try{localStorage.setItem('luka-music-volume',String(audio.volume))}catch(e){}};
document.getElementById('music-spotify').onclick=()=>{audio.pause();rememberOff(true);embed.replaceChildren();const frame=document.createElement('iframe');frame.src={{ playlist|tojson }};frame.title='Spotify playlist music player';frame.allow='autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture';frame.loading='lazy';frame.allowFullscreen=true;embed.append(frame);state.textContent='Press Play in the Spotify player to listen.'};
fetch('/api/background-music').then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.error||'Entrance music is unavailable.');if(!d.url){state.textContent='Spotify playlist is ready. No entrance audio has been uploaded yet.';return}const u=new URL(d.url);if(u.protocol!=='https:'||u.hostname!=='res.cloudinary.com')throw new Error('Unexpected audio address.');available=true;audio.src=u.href;document.getElementById('music-background').hidden=false;if(optedOut)state.textContent='Entrance music is paused by your saved preference.';else play()}).catch(e=>{state.textContent=e.message+' You can still open the Spotify playlist.'});
})();</script>'''

EDITOR = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Entrance music</title><style>body{font:16px/1.7 Arial;background:#d8eee4;color:#34564e;padding:25px}main{max-width:650px;margin:auto;background:#fffaf7;padding:28px;border-radius:20px}label{display:block;margin:20px 0}button{padding:12px 16px;border:1px solid #b97796;border-radius:10px;background:#ffdaeb;cursor:pointer}input[type=file]{max-width:100%}</style><main><h1>Entrance music ♫</h1><p>Upload an MP3 under 5 MB that you own or have permission to publish. Saving replaces the shared entrance track for every visitor. The site attempts autoplay, but browser restrictions may require a click. This does not download music from Spotify.</p><form id="audio-form"><input type="hidden" name="csrf" value="{{ csrf }}"><label>MP3 file <input name="music" type="file" accept="audio/mpeg,.mp3" required></label><label><input type="checkbox" name="permission" value="yes" required> I own this audio or have permission to publish it publicly.</label><button id="audio-save">Save entrance music for everyone</button></form><p id="audio-status" role="status" aria-live="polite"></p><a href="/studio">Back to Studio</a> · <a href="/">View website</a></main><script>document.getElementById('audio-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,b=document.getElementById('audio-save'),s=document.getElementById('audio-status'),f=form.elements.music.files[0];if(!f||f.size>5*1024*1024){s.textContent='Choose an MP3 under 5 MB.';return}b.disabled=true;s.textContent='Validating and saving audio…';try{const r=await fetch('/api/background-music',{method:'POST',body:new FormData(form)});let d;try{d=await r.json()}catch(e){throw new Error('Unexpected response. Check your sign-in.')}if(!r.ok)throw new Error(d.error||'Saving failed.');s.textContent='Saved! Reload the public website to load the new entrance track.'}catch(e){s.textContent=e.message}finally{b.disabled=false}};</script></html>'''
