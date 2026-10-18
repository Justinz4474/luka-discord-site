import animated_background as background
import design_studio


def install(application):
    if application.extensions.get('studio_background_sync_ready'):
        return
    start = "fetch('/api/background-settings',{cache:'no-store'})"
    end = '}).catch(()=>apply())})();'
    if start not in background.MARKUP or end not in background.MARKUP:
        raise RuntimeError('Background client changed; Studio sync needs updating.')
    background.MARKUP = background.MARKUP.replace(start, 'function refreshBackground(){return '+start, 1)
    background.MARKUP = background.MARKUP.replace(end, "}).catch(()=>apply())}function syncBackground(){refreshBackground();setTimeout(refreshBackground,5500)}refreshBackground();window.addEventListener('focus',syncBackground);document.addEventListener('visibilitychange',()=>{if(!document.hidden)syncBackground()});window.addEventListener('storage',event=>{if(event.key==='luka-background-updated')syncBackground()})})();", 1)
    message = "status.textContent='Saved for everyone!"
    if message not in background.EDITOR:
        raise RuntimeError('Background editor changed; save notification needs updating.')
    background.EDITOR = background.EDITOR.replace(message, "try{localStorage.setItem('luka-background-updated',String(Date.now()))}catch(e){}"+message, 1)
    old_link = '<a href="/editor/background">Background ↗</a>'
    new_link = '<a href="/editor/background" target="_blank" rel="noopener">Background ↗</a>'
    design_studio.UI = design_studio.UI.replace(old_link,new_link,1)
    original_studio = application.view_functions['studio']
    def studio():
        page = original_studio()
        marker = '<div id="s-workspace"><div class="wrap">'
        if marker not in page:
            raise RuntimeError('Studio canvas changed; shared background insertion needs updating.')
        return page.replace(marker, marker+background.markup()+CANVAS_STYLE, 1)
    application.view_functions['studio'] = studio
    application.jinja_env.parse(background.MARKUP)
    application.jinja_env.parse(background.EDITOR)
    application.jinja_env.parse(design_studio.UI)
    application.extensions['studio_background_sync_ready'] = True


CANVAS_STYLE = r'''<style>#s-workspace>.wrap{position:relative;isolation:isolate;background:transparent!important}#s-workspace #site-animated-bg{position:absolute!important;inset:0;z-index:-1}#s-workspace #background-motion{position:absolute;top:12px;right:12px}</style>'''
