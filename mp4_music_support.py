import io, time
import music_controls as music
from flask import request, abort, jsonify


def install(application):
    if application.extensions.get('mp4_music_ready'):
        return
    from app import can_edit, csrf_ok, storage
    original_save = application.view_functions['save_music']

    def save_music():
        if not can_edit() or not csrf_ok():
            abort(403)
        uploaded = request.files.get('music')
        if not uploaded or not uploaded.filename.lower().endswith('.mp4'):
            return original_save()
        if request.form.get('permission') != 'yes':
            return jsonify(error='Confirm that you have permission to publish the audio.'), 400
        data = uploaded.stream.read(5*1024*1024+1)
        if not data or len(data)>5*1024*1024:
            return jsonify(error='Choose an MP3 or MP4 file under 5 MB.'), 400
        if len(data)<12 or data[4:8]!=b'ftyp':
            return jsonify(error='This does not appear to be an MP4 file.'), 400
        try:
            storage()
            with music.LOCK:
                asset = music.cloudinary.uploader.upload(io.BytesIO(data), public_id=music.ID, resource_type='video', type='upload', format='mp3', overwrite=True, invalidate=True, timeout=30)
                music.CACHE.update(url=asset['secure_url'], until=time.monotonic()+60)
            return jsonify(ok=True)
        except (music.Error, ValueError, KeyError):
            return jsonify(error='Could not extract audio. Make sure the MP4 contains a playable audio track and try again.'), 503

    application.view_functions['save_music'] = save_music
    music.PLAYER = music.PLAYER.replace('Upload / replace entrance MP3', 'Upload / replace entrance audio')
    music.EDITOR = music.EDITOR.replace('Upload an MP3 under 5 MB', 'Upload an MP3 or MP4 under 5 MB').replace('MP3 file <input', 'MP3 or MP4 file <input').replace('accept="audio/mpeg,.mp3"', 'accept="audio/mpeg,video/mp4,.mp3,.mp4"').replace('Choose an MP3 under 5 MB.', 'Choose an MP3 or MP4 under 5 MB.').replace('Validating and saving audio…', 'Validating and converting audio…').replace('This does not download music from Spotify.', 'MP4 uploads are converted to audio only; no video is displayed. The MP4 must contain an audio track. This does not download music from Spotify.')
    application.jinja_env.parse(music.PLAYER)
    application.jinja_env.parse(music.EDITOR)
    application.extensions['mp4_music_ready'] = True
