from html import escape
from urllib.parse import urlparse
import music_controls as music

VIDEO_URL = 'https://pub-64f1c2f5cbd44dcfafc9f94b8c5f743c.r2.dev/Alien%20Stage%20_%20All%20episodes%20in%20order%20%2B%20english%20subtitles.mp4'


def install(application):
    if application.extensions.get('entrance_video_ready'):
        return
    source = music.PLAYER
    automatic = 'else play()}).catch'
    marker = '<summary>♫ Music · Spotify & entrance audio</summary>'
    if automatic not in source or marker not in source:
        raise RuntimeError('Entrance music template changed; video integration needs updating.')
    section = '<section aria-label="Entrance video"><video id="entrance-video" controls playsinline loop preload="none" src="' + escape(VIDEO_URL, quote=True) + '">Your browser does not support this video player.</video><button id="entrance-video-toggle" type="button">Enter with video & sound ♡</button><p id="entrance-video-state" role="status" aria-live="polite">Entrance video is ready.</p><p><a href="' + escape(VIDEO_URL, quote=True) + '" target="_blank" rel="noopener">Open original MP4</a></p></section>'
    source = source.replace(automatic, "else state.textContent='Optional audio is ready. Press Play music to listen.'}).catch", 1)
    source = source.replace('<details id="site-music">', '<details id="site-music" open>', 1)
    source = source.replace(marker, '<summary>♫ Entrance video & music</summary>'+section, 1)
    music.PLAYER = source + VIDEO_CONTROLS
    note = '<p>The entrance video is linked from R2. Uploads below update the optional audio-only alternative, not the video. Replace the R2 object to update the video.</p>'
    music.EDITOR = music.EDITOR.replace('<h1>Entrance music ♫</h1>', '<h1>Entrance music ♫</h1>'+note, 1)
    application.jinja_env.parse(music.PLAYER)
    origin = 'https://' + urlparse(VIDEO_URL).netloc
    def permit_video(response):
        policy = response.headers.get('Content-Security-Policy', '')
        if policy:
            directives = [part.strip() for part in policy.split(';') if part.strip()]
            for i, directive in enumerate(directives):
                if directive.split()[0] == 'media-src':
                    if origin not in directive.split()[1:]:
                        directives[i] += ' ' + origin
                    break
            else:
                directives.append("media-src 'self' https://res.cloudinary.com " + origin)
            response.headers['Content-Security-Policy'] = '; '.join(directives)
        return response
    application.after_request_funcs.setdefault(None, []).insert(0, permit_video)
    application.extensions['entrance_video_ready'] = True


VIDEO_CONTROLS = r'''<style>#site-music{max-height:85vh;overflow:auto;box-sizing:border-box}#entrance-video{display:block;width:100%;aspect-ratio:16/9;background:#111;border-radius:10px;margin-top:10px}#entrance-video-state{line-height:1.5}</style><script>(()=>{const video=document.getElementById('entrance-video'),button=document.getElementById('entrance-video-toggle'),state=document.getElementById('entrance-video-state'),audio=document.getElementById('entrance-audio'),embed=document.getElementById('music-embed');let optedOut=false;const remember=value=>{try{localStorage.setItem('luka-entrance-video-off',value?'1':'0')}catch(e){}};try{optedOut=localStorage.getItem('luka-entrance-video-off')==='1';const volume=Number(localStorage.getItem('luka-music-volume')??.35);video.volume=Number.isFinite(volume)?Math.max(0,Math.min(1,volume)):.35}catch(e){video.volume=.35}video.addEventListener('play',()=>{if(audio)audio.pause();if(embed)embed.replaceChildren();remember(false);button.textContent='Pause entrance video';state.textContent='Entrance video and its audio are playing.'});video.addEventListener('pause',()=>{remember(true);button.textContent='Play video & sound ♡';state.textContent='Entrance video paused.'});video.addEventListener('error',()=>{state.textContent='The video could not be loaded or decoded. Try Open original MP4 and check that the R2 file is public and playable in your browser.';button.textContent='Retry entrance video'});video.addEventListener('volumechange',()=>{try{localStorage.setItem('luka-music-volume',String(video.volume))}catch(e){}});if(audio)audio.addEventListener('play',()=>video.pause());const spotify=document.getElementById('music-spotify');if(spotify)spotify.addEventListener('click',()=>{video.pause();remember(true)});async function start(){try{if(video.error)video.load();await video.play()}catch(e){if(e.name==='NotAllowedError'){state.textContent='Tap Enter with video & sound to start. Your browser blocked automatic playback with sound.';button.textContent='Enter with video & sound ♡'}else{state.textContent='Playback did not start. Try again or use Open original MP4.';button.textContent='Retry entrance video'}}}button.onclick=()=>{if(video.paused)start();else video.pause()};if(optedOut)state.textContent='Entrance video is paused by your saved preference. Press Play to start.';else start()})();</script>'''
