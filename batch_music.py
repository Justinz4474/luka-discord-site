import secrets, tempfile, threading, subprocess, time
from pathlib import Path
from urllib.parse import urlparse
from flask import request, session, abort, jsonify, render_template_string
import music_controls as music

BUSY = threading.BoundedSemaphore(1)


def combine(paths, root, encoder):
    deadline = time.monotonic()+70
    duration = 0
    normalized = []
    for i, path in enumerate(paths):
        target = root / ('track-%d.mp3' % i)
        remaining = 900-duration
        if remaining <= 0:
            raise ValueError('The combined playlist must be no longer than 15 minutes.')
        result = subprocess.run([encoder, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-protocol_whitelist', 'file,pipe', '-f', 'mp3', '-i', str(path), '-map', '0:a:0', '-vn', '-sn', '-dn', '-map_metadata', '-1', '-t', str(remaining+1), '-ac', '2', '-ar', '44100', '-c:a', 'libmp3lame', '-b:a', '128k', '-threads', '1', '-progress', 'pipe:1', str(target)], capture_output=True, text=True, timeout=max(1, min(30, deadline-time.monotonic())))
        times = [int(line.split('=',1)[1])/1000000 for line in result.stdout.splitlines() if line.startswith('out_time_us=') and line.split('=',1)[1].isdigit()]
        seconds = max(times, default=0)
        if result.returncode or seconds <= 0 or not target.exists():
            raise ValueError('One of the files is not a playable MP3. Remove it and try again.')
        duration += seconds
        if duration > 900:
            raise ValueError('The combined playlist must be no longer than 15 minutes.')
        normalized.append(target)
    listing = root / 'tracks.txt'
    listing.write_text(''.join("file '%s'\n" % p.name for p in normalized), encoding='utf-8')
    output = root / 'entrance.mp3'
    result = subprocess.run([encoder, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-protocol_whitelist', 'file,pipe', '-f', 'concat', '-safe', '1', '-i', str(listing), '-map_metadata', '-1', '-c:a', 'copy', str(output)], capture_output=True, text=True, timeout=max(1, min(15, deadline-time.monotonic())))
    if result.returncode or not output.exists() or output.stat().st_size < 1:
        raise ValueError('Could not combine the tracks.')
    return output


def install(application):
    if application.extensions.get('batch_music_ready'):
        return
    from app import can_edit, csrf_ok, storage
    @application.before_request
    def batch_limit():
        if request.path == '/api/music/combine' and request.method == 'POST':
            if not can_edit():
                abort(403)
            request.max_content_length = 26*1024*1024
    @application.get('/editor/music/batch')
    def batch_music_editor():
        if not can_edit():
            abort(403)
        return render_template_string(EDITOR, csrf=session.setdefault('csrf', secrets.token_urlsafe(32)))
    @application.post('/api/music/combine')
    def combine_music():
        if not can_edit() or not csrf_ok():
            abort(403)
        if request.form.get('permission') != 'yes':
            return jsonify(error='Confirm permission to publish all selected tracks.'), 400
        files = request.files.getlist('tracks')
        if not 1 <= len(files) <= 10:
            return jsonify(error='Choose between 1 and 10 MP3 files.'), 400
        if not BUSY.acquire(blocking=False):
            return jsonify(error='Another conversion is running. Try again shortly.'), 409
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            with tempfile.TemporaryDirectory(prefix='entrance-') as directory:
                root = Path(directory)
                paths, total = [], 0
                for i, uploaded in enumerate(files):
                    if not uploaded.filename or not uploaded.filename.lower().endswith('.mp3'):
                        raise ValueError('Only MP3 files are accepted in this multi-track tool.')
                    data = uploaded.stream.read(5*1024*1024+1)
                    total += len(data)
                    if not data or len(data)>5*1024*1024 or total>25*1024*1024:
                        raise ValueError('Each MP3 must be under 5 MB; all tracks together must be under 25 MB.')
                    path = root / ('input-%d.mp3' % i)
                    path.write_bytes(data)
                    paths.append(path)
                storage()
                output = combine(paths, root, get_ffmpeg_exe())
                with music.LOCK:
                    asset = music.cloudinary.uploader.upload(str(output), public_id=music.ID, resource_type='video', type='upload', format='mp3', overwrite=True, invalidate=True, timeout=30)
                    url = asset['secure_url']
                    if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'res.cloudinary.com':
                        raise ValueError('Storage returned an unexpected audio address.')
                    music.CACHE.update(url=url, until=time.monotonic()+60)
                return jsonify(ok=True, url=url)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        except subprocess.TimeoutExpired:
            return jsonify(error='Conversion took too long. Try fewer or shorter tracks.'), 422
        except (music.Error, OSError, RuntimeError, ImportError, KeyError):
            return jsonify(error='Conversion or saving failed. Your entrance track was not confirmed saved; check the audio files and storage, then retry.'), 503
        finally:
            BUSY.release()
    import design_studio
    link = '<p><a href="/editor/music/batch">Combine multiple MP3s ↗</a></p>'
    design_studio.UI = design_studio.UI.replace('<h2>Layers</h2>', link+'<h2>Layers</h2>', 1)
    music.EDITOR = music.EDITOR.replace('<form id="audio-form">', link+'<form id="audio-form">', 1)
    application.jinja_env.parse(EDITOR)
    application.extensions['batch_music_ready'] = True


EDITOR = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Combine entrance MP3s</title><style>body{font:16px/1.6 Arial;background:#d8eee4;color:#34564e;padding:20px}main{max-width:720px;margin:auto;background:#fffaf7;padding:25px;border-radius:20px}button{padding:8px 12px;margin:5px;border:1px solid #b97796;border-radius:10px;background:#ffdaeb;cursor:pointer}fieldset{border:0;padding:0}input[type=file]{max-width:100%}li{margin:10px 0;overflow-wrap:anywhere}label{display:block;margin:15px 0}audio{max-width:100%}[hidden]{display:none!important}</style><main><h1>Combine your MP3 playlist ♫</h1><p>Choose up to 10 MP3 files. Each must be under 5 MB, together under 25 MB, and the combined audio no longer than 15 minutes. Arrange their order below. Combining saves one MP3 as the shared entrance track and replaces the previous track for every visitor.</p><form id="batch-form"><fieldset id="batch-fields"><label>Select MP3s <input id="batch-files" type="file" accept="audio/mpeg,.mp3" multiple></label><ol id="batch-order"></ol><label><input id="batch-permission" type="checkbox" required> I own these tracks or have permission to publish them publicly.</label><button type="submit">Combine and use as entrance music</button></fieldset></form><p id="batch-status" role="status" aria-live="polite"></p><div id="batch-result" hidden><audio id="batch-preview" controls preload="none"></audio><p><a id="batch-download" target="_blank" rel="noopener">Open combined MP3</a> · <a href="/">View website</a></p></div><a href="/editor/music">Single MP3 / MP4 upload</a> · <a href="/studio">Back to Studio</a></main><script>(()=>{let tracks=[];const list=document.getElementById('batch-order'),status=document.getElementById('batch-status'),fields=document.getElementById('batch-fields');function draw(){list.replaceChildren();tracks.forEach((file,i)=>{const row=document.createElement('li'),name=document.createElement('span');name.textContent=file.name+' ('+(file.size/1048576).toFixed(2)+' MB) ';row.append(name);[['Move up',-1],['Move down',1],['Remove',0]].forEach(([label,step])=>{const b=document.createElement('button');b.type='button';b.textContent=label;b.setAttribute('aria-label',label+' '+file.name);b.disabled=step!==0&&(i+step<0||i+step>=tracks.length);b.onclick=()=>{if(step===0)tracks.splice(i,1);else [tracks[i],tracks[i+step]]=[tracks[i+step],tracks[i]];draw()};row.append(b)});list.append(row)})}document.getElementById('batch-files').onchange=e=>{tracks=Array.from(e.target.files);draw()};document.getElementById('batch-form').onsubmit=async e=>{e.preventDefault();if(!tracks.length||tracks.length>10||tracks.some(f=>!f.name.toLowerCase().endsWith('.mp3')||f.size===0||f.size>5*1048576)||tracks.reduce((sum,f)=>sum+f.size,0)>25*1048576){status.textContent='Choose 1–10 MP3 files, each under 5 MB and under 25 MB together.';return}const data=new FormData();data.append('csrf',{{ csrf|tojson }});data.append('permission',document.getElementById('batch-permission').checked?'yes':'no');tracks.forEach(f=>data.append('tracks',f));fields.disabled=true;document.getElementById('batch-result').hidden=true;document.getElementById('batch-preview').pause();status.textContent='Combining and saving… Keep this page open. This can take up to two minutes.';try{const r=await fetch('/api/music/combine',{method:'POST',body:data});let d;try{d=await r.json()}catch(e){throw new Error(r.status===413?'The upload is too large. Use fewer or smaller MP3s.':'Unexpected server response. Check your sign-in and try fewer tracks.')}if(!r.ok)throw new Error(d.error||'Conversion failed.');const url=new URL(d.url);if(url.protocol!=='https:'||url.hostname!=='res.cloudinary.com')throw new Error('Unexpected audio address.');document.getElementById('batch-preview').src=url.href;document.getElementById('batch-download').href=url.href;document.getElementById('batch-result').hidden=false;status.textContent='Saved as entrance music for everyone! You can preview the combined MP3 here. Reload the website to hear it; autoplay may require a click.'}catch(e){status.textContent=e.message}finally{fields.disabled=false}}})();</script></html>'''
