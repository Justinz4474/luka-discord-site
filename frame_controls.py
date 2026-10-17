import json

FRAMES = {'hero': ('.hero', 'Main outer card'), 'photo': ('.photo', 'Artwork frame')}
CSS = '''html[data-hero-frame="hide"] .hero{background:transparent!important;border:0!important;border-radius:0!important;box-shadow:none!important}html[data-photo-frame="hide"] .photo{background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important}'''


def install(application):
    if application.extensions.get('frame_controls_ready'):
        return
    import cms, design_studio
    for name in FRAMES:
        cms.DEFAULT.setdefault(name + '_frame', 'show')
    cms.CACHE['until'] = 0
    apply_public = "for(const name of ['hero','photo'])document.documentElement.setAttribute('data-'+name+'-frame',d[name+'_frame']==='hide'?'hide':'show');css.textContent+=" + json.dumps(CSS) + ";"
    target = 'document.head.append(css)'
    if target not in cms.CLIENT:
        raise RuntimeError('Public page frame-rendering target changed')
    cms.CLIENT = cms.CLIENT.replace(target, apply_public + target, 1)
    design_studio.UI += '<style>' + CSS + '</style>'
    patches = [
        ('el=item(),locked=!doc', "el=item(),isFrame=Boolean(selected?.startsWith('frame:')),locked=!doc"),
        ("$(id).disabled=locked||!el;", "$(id).disabled=locked||!el||(isFrame&&id!=='delete');"),
        ("$('show').disabled=locked||!key||!s?.hidden;", "$('show').disabled=locked||(isFrame?doc.settings[selected.slice(6)+'_frame']!=='hide':!key||!s?.hidden);"),
        ("$('name').textContent=b?'Text box':key?key.replaceAll('_',' '):'Select an element';", "$('name').textContent=isFrame?(selected==='frame:hero'?'Main outer card':'Artwork frame'):b?'Text box':key?key.replaceAll('_',' '):'Select an element';"),
        ("if(el){if(document.activeElement!==$('font'))", "if(el&&!isFrame){if(document.activeElement!==$('font'))"),
        ('host.append(el)}}', 'host.append(el)}appendFrameLayers(host)}'),
        ('const d=doc.settings;', 'const d=doc.settings;renderFrames(d);'),
        ("function enter(el){if(preview||busy||!el)return;", "function enter(el){if(preview||busy||!el||el.dataset.studio?.startsWith('frame:'))return;"),
        ("function remove(){if(!selected||preview||busy)return;change", "function remove(){if(!selected||preview||busy)return;if(selected.startsWith('frame:')){change(()=>{doc.settings[selected.slice(6)+'_frame']='hide'});message('Frame styling removed. Text and artwork are unchanged; Publish to save.');return}change"),
        ("$('show').onclick=()=>change(()=>{const key=originalKey();", "$('show').onclick=()=>change(()=>{if(selected?.startsWith('frame:')){doc.settings[selected.slice(6)+'_frame']='show';return}const key=originalKey();"),
        ('})();</script>', HELPERS + '})();</script>')
    ]
    for old, new in patches:
        if design_studio.SCRIPT.count(old) != 1:
            raise RuntimeError('Studio frame-control target changed: ' + old[:80])
        design_studio.SCRIPT = design_studio.SCRIPT.replace(old, new, 1)
    design_studio.UI = design_studio.UI.replace('{#', '{ #')
    application.jinja_env.parse(design_studio.UI)
    application.jinja_env.parse(design_studio.SCRIPT)
    application.extensions['frame_controls_ready'] = True


HELPERS = r'''function renderFrames(settings){for(const [name,selector]of [['hero','.hero'],['photo','.photo']]){document.documentElement.setAttribute('data-'+name+'-frame',settings[name+'_frame']==='hide'?'hide':'show');const el=wrap.querySelector(selector);if(el){el.dataset.studio='frame:'+name;el.classList.add('s-item');el.tabIndex=preview?-1:0;el.setAttribute('aria-label',name==='hero'?'Main outer card frame':'Artwork frame');el.title='Select the frame and press Delete to remove its border, background, and shadow without deleting its content.'}}}
function appendFrameLayers(host){const heading=document.createElement('div');heading.textContent='Frames · decoration only';heading.style.cssText='font-weight:700;margin:16px 0 8px';host.append(heading);for(const [name,label]of [['hero','Main outer card'],['photo','Artwork frame']]){const id='frame:'+name,removed=doc.settings[name+'_frame']==='hide',button=document.createElement('button');button.className='layer'+(selected===id?' selected':'');button.textContent=(removed?'◌ ':'▢ ')+label+(removed?' (removed)':'');button.disabled=busy;button.onclick=()=>{selected=id;sync();item()?.scrollIntoView({block:'center',inline:'nearest'});if(!preview)item()?.focus();message('Frame selected. Delete removes only the surrounding styling; Restore hidden brings it back. Use Publish to save.')};host.append(button)}}
'''
