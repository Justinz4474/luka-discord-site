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
    editor = replace(background.EDITOR,'<option value="image">','<option value="starfield">Emerald aurora &amp; fireflies</option><option value="image">')
    editor = replace(editor,"preview.style.backgroundImage='none';", "preview.classList.remove('starfield-active');preview.style.backgroundImage='none';")
    editor = replace(editor,"if(data.mode==='plain')return;", "if(data.mode==='plain')return;if(data.mode==='starfield'){preview.classList.add('starfield-active');return;}")
    editor = replace(editor,'show(defaults);draw()',"show({...defaults,mode:'image',overlay:66});draw()")
    editor = replace(editor,'<h1>Background ♡</h1>','<h1>Background ♡</h1><p>The built-in emerald, jade, and mint aurora includes drifting firefly lights and needs no image URL. Choose Image / animated GIF or Restore current GIF to return to your R2 artwork. Preview changes, then Save to publish them.</p>')
    background.EDITOR = editor + STYLE
    application.jinja_env.parse(background.MARKUP)
    application.jinja_env.parse(background.EDITOR)
    application.extensions['starfield_background_ready'] = True


STYLE = r'''<style>#site-animated-bg.starfield-active,#bg-preview.starfield-active{overflow:hidden;background-color:#061c17;background-image:linear-gradient(rgba(2,18,13,var(--starfield-overlay,.45)),rgba(2,18,13,var(--starfield-overlay,.45))),radial-gradient(ellipse at 18% 28%,#278d65aa 0%,transparent 65%),radial-gradient(ellipse at 85% 75%,#50c99a66 0%,transparent 62%),linear-gradient(135deg,#061c17,#123e2d)!important}#site-animated-bg.starfield-active::before,#bg-preview.starfield-active::before{content:"";position:absolute;inset:-25%;pointer-events:none;background-image:radial-gradient(circle,#f0ffdacc 0 1.2px,#a9ffc940 2px,transparent 5px),radial-gradient(circle,#bbffdbb3 0 .9px,transparent 3px),radial-gradient(circle,#f5ffc799 0 1.5px,#bbffad22 3px,transparent 7px),radial-gradient(circle,#7deac280 0 .8px,transparent 2px);background-size:137px 173px,211px 229px,347px 281px,89px 113px;background-position:9px 21px,71px 91px,149px 47px,33px 57px;animation:luka-firefly-drift 26s ease-in-out infinite alternate;will-change:transform;opacity:.65}#site-animated-bg.starfield-active::after,#bg-preview.starfield-active::after{content:"";position:absolute;inset:-30%;pointer-events:none;background-image:radial-gradient(ellipse at 20% 70%,#68ffc133 0%,transparent 48%),radial-gradient(ellipse at 80% 25%,#a7f2c926 0%,transparent 42%),linear-gradient(125deg,transparent 20%,#3bdb931a 35%,#bcffe224 43%,transparent 56%,#47b7831a 70%,transparent 83%);filter:blur(28px);opacity:calc(1 - var(--starfield-overlay,.45));animation:luka-emerald-aurora 32s ease-in-out infinite alternate;will-change:transform}#bg-preview.starfield-active #bg-shade{z-index:1;background:#02120d}@keyframes luka-firefly-drift{0%{transform:translate3d(-2%,3%,0);opacity:.5}50%{transform:translate3d(1%,0,0);opacity:.75}100%{transform:translate3d(3%,-4%,0);opacity:.6}}@keyframes luka-emerald-aurora{from{transform:translate3d(-5%,-3%,0) rotate(-5deg) scale(1)}to{transform:translate3d(5%,4%,0) rotate(7deg) scale(1.08)}}@media(prefers-reduced-motion:reduce){ .starfield-active::before,.starfield-active::after{animation:none!important;will-change:auto}}</style>'''
