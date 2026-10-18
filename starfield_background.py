import animated_background as background


def install(application):
    if application.extensions.get('starfield_background_ready'):
        return
    original_clean = background.clean
    def clean(data):
        if isinstance(data,dict) and data.get('mode')=='starfield':
            candidate = dict(data)
            candidate['mode'] = 'plain'
            result = original_clean(candidate)
            result['mode'] = 'starfield'
            return result
        return original_clean(data)
    background.clean = clean
    background.ID = 'luka-discord-site/background-settings-v2.json'
    background.DEFAULT.update(mode='starfield', overlay=45)
    background.CACHE.update(data=None, until=0)
    def replace(source, old, new):
        if old not in source:
            raise RuntimeError('Background template changed; starfield integration needs updating.')
        return source.replace(old,new,1)
    public = replace(background.MARKUP,"active=settings.mode==='image'&&settings.url", "active=(settings.mode==='starfield'||settings.mode==='image'&&settings.url)")
    public = replace(public,'layer.style.backgroundImage=running?',"layer.classList.toggle('starfield-active',running&&settings.mode==='starfield');layer.style.setProperty('--starfield-overlay',String(settings.overlay/100));layer.style.backgroundImage=running&&settings.mode==='image'?")
    public = replace(public,"['image','plain'].includes(data.mode)","['image','plain','starfield'].includes(data.mode)")
    background.MARKUP = public + STYLE
    editor = replace(background.EDITOR,'<option value="image">','<option value="starfield">Blue-purple drifting stars</option><option value="image">')
    editor = replace(editor,"preview.style.backgroundImage='none';", "preview.classList.remove('starfield-active');preview.style.backgroundImage='none';")
    editor = replace(editor,"if(data.mode==='plain')return;", "if(data.mode==='plain')return;if(data.mode==='starfield'){preview.classList.add('starfield-active');return;}")
    editor = replace(editor,'show(defaults);draw()',"show({...defaults,mode:'image',overlay:66});draw()")
    editor = replace(editor,'<h1>Background ♡</h1>','<h1>Background ♡</h1><p>The built-in blue-purple starfield is ready to use without an image URL. Choose Image / animated GIF or Restore current GIF to return to your R2 artwork. Preview changes, then Save to publish them.</p>')
    background.EDITOR = editor + STYLE
    application.jinja_env.parse(background.MARKUP)
    application.jinja_env.parse(background.EDITOR)
    application.extensions['starfield_background_ready'] = True


STYLE = r'''<style>#site-animated-bg.starfield-active,#bg-preview.starfield-active{overflow:hidden;background-color:#100d26;background-image:radial-gradient(ellipse at 18% 30%,#254b82aa 0%,transparent 58%),radial-gradient(ellipse at 85% 70%,#733d92aa 0%,transparent 60%),linear-gradient(135deg,#100d26,#20183e)!important}#site-animated-bg.starfield-active::before,#bg-preview.starfield-active::before{content:"";position:absolute;inset:-30%;pointer-events:none;background-image:radial-gradient(circle,#eef7ffcc 0 1px,transparent 1.8px),radial-gradient(circle,#b9c9ff99 0 .8px,transparent 1.6px),radial-gradient(circle,#e8c7ffbb 0 1.3px,transparent 2px);background-size:109px 137px,173px 193px,251px 227px;background-position:7px 19px,61px 83px,137px 41px;animation:luka-star-drift 38s ease-in-out infinite alternate;will-change:transform}#site-animated-bg.starfield-active::after{content:"";position:absolute;inset:0;background:rgba(19,13,41,var(--starfield-overlay,.45));pointer-events:none}#bg-preview.starfield-active #bg-shade{z-index:1}@keyframes luka-star-drift{from{transform:translate3d(-2%,-2%,0);opacity:.55}to{transform:translate3d(2%,4%,0);opacity:.85}}@media(prefers-reduced-motion:reduce){ .starfield-active::before{animation:none!important;will-change:auto}}</style>'''
