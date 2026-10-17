import json

GROUPS = {'page': ('.wrap', 'Entire page content'), 'header': ('header', 'Header'), 'hero': ('.hero', 'Main section and its contents'), 'heading': ('.hero h1', 'Full main heading'), 'hero_buttons': ('.hero .buttons', 'Main button group'), 'artwork': ('.frame', 'Artwork group and caption'), 'photo': ('.photo', 'Photo container and contents'), 'image': ('.artbox', 'Artwork image area'), 'heart': ('.heart', 'Heart decoration'), 'tape': ('.tape', 'Tape decoration'), 'invitation': ('.community', 'Invitation section and contents'), 'invite_buttons': ('.community .buttons', 'Invitation button group'), 'invite': ('.invite', 'Visible invite link')}


def install(application):
    if application.extensions.get('deletion_controls_ready'):
        return
    import cms, design_studio
    cms.DEFAULT.setdefault('removed_elements', '')
    cms.CACHE['until'] = 0
    selectors = {key: value[0] for key, value in GROUPS.items()}
    public = 'const removed=new Set((d.removed_elements||"").split(","));for(const [key,selector]of Object.entries(' + json.dumps(selectors) + ')){const el=document.querySelector(selector);if(el)el.classList.toggle("site-deleted",removed.has(key))}css.textContent+=".site-deleted{display:none!important}";'
    target = 'document.head.append(css)'
    if target not in cms.CLIENT:
        raise RuntimeError('Public deletion rendering target changed')
    cms.CLIENT = cms.CLIENT.replace(target, public + target, 1)
    design_studio.UI = design_studio.UI.replace('body.s-edit .s-hidden{display:revert!important;opacity:.3}', '')
    design_studio.UI += '<style>.s-removed{display:none!important}</style>'
    patches = [
        ("Boolean(selected?.startsWith('frame:'))", "Boolean(selected?.startsWith('frame:')||selected?.startsWith('element:'))"),
        ("function item(){return selected?", "function item(){if(selected?.startsWith('element:'))return removableNode(selected.slice(8));if(selected?.startsWith('frame:'))return wrap.querySelector(selected==='frame:hero'?'.hero':'.photo');return selected?"),
        ("isFrame?doc.settings[selected.slice(6)+'_frame']!=='hide':!key||!s?.hidden", "isFrame?(selected.startsWith('element:') ? !removedSet().has(selected.slice(8)) : doc.settings[selected.slice(6)+'_frame']!=='hide'):!key||!s?.hidden"),
        ("isFrame?(selected==='frame:hero'?'Main outer card':'Artwork frame'):", "isFrame?(selected.startsWith('element:')?REMOVABLE[selected.slice(8)][1]:selected==='frame:hero'?'Main outer card':'Artwork frame'):"),
        ('appendFrameLayers(host)}', 'appendFrameLayers(host);appendRemovableLayers(host)}'),
        ('renderFrames(d);', 'renderFrames(d);renderRemoved(d);'),
        ("||el.dataset.studio?.startsWith('frame:'))return;", "||el.dataset.studio?.startsWith('frame:')||el.dataset.studio?.startsWith('element:'))return;"),
        ("if(selected.startsWith('frame:')){change", "if(selected.startsWith('element:')){deleteElement(selected.slice(8));return}if(selected.startsWith('frame:')){change"),
        ("if(selected?.startsWith('frame:')){doc.settings", "if(selected?.startsWith('element:')){setRemoved(selected.slice(8),false);return}if(selected?.startsWith('frame:')){doc.settings"),
        ('})();</script>', 'const REMOVABLE=' + json.dumps(GROUPS) + ';' + HELPERS + '})();</script>')
    ]
    for old, new in patches:
        if design_studio.SCRIPT.count(old) != 1:
            raise RuntimeError('Studio deletion target changed: ' + old[:80])
        design_studio.SCRIPT = design_studio.SCRIPT.replace(old, new, 1)
    application.jinja_env.parse(design_studio.UI)
    application.jinja_env.parse(design_studio.SCRIPT)
    application.extensions['deletion_controls_ready'] = True


HELPERS = r'''function removedSet(){return new Set((doc.settings.removed_elements||'').split(',').filter(key=>Object.hasOwn(REMOVABLE,key)))}
function removableNode(key){const selector=REMOVABLE[key]?.[0];return selector==='.wrap'?wrap:selector?wrap.querySelector(selector):null}
function setRemoved(key,value){const removed=removedSet();if(value)removed.add(key);else removed.delete(key);doc.settings.removed_elements=[...removed].join(',')}
function renderRemoved(settings){const removed=removedSet();for(const key of Object.keys(REMOVABLE)){const el=removableNode(key);if(el){el.dataset.studio='element:'+key;el.classList.add('s-item');el.classList.toggle('s-removed',removed.has(key));el.tabIndex=preview?-1:0;el.title='Select this page element; Delete removes it from the canvas. Undo or Restore brings it back.'}}}
function deleteElement(key){const el=removableNode(key);if(!el)return;if(el.querySelector('[data-studio]')&&!confirm('Remove '+REMOVABLE[key][1]+' and everything inside it from the page? Undo or Restore can bring it back.'))return;change(()=>{setRemoved(key,true);selected=null});message('Element removed from the canvas. Publish saves the deletion for visitors. Undo restores it.')}
function appendRemovableLayers(host){const title=document.createElement('div');title.textContent='Page elements / restore deleted groups';title.style.cssText='font-weight:700;margin:16px 0 8px';host.append(title);const removed=removedSet();for(const [key,entry]of Object.entries(REMOVABLE)){const button=document.createElement('button');button.className='layer'+(selected==='element:'+key?' selected':'');button.textContent=(removed.has(key)?'◌ Deleted: ':'▢ ')+entry[1];button.disabled=busy;button.onclick=()=>{selected='element:'+key;sync();if(!removed.has(key)){item()?.scrollIntoView({block:'center',inline:'nearest'});if(!preview)item()?.focus()}message(removed.has(key)?'This element is gone from the canvas. Restore hidden or Undo brings it back.':'Element selected. Delete removes the whole element; frame-only layers remove decoration without deleting contents.')};host.append(button)}}
'''
