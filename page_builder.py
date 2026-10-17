import io, json, re, math, time, secrets, threading
from urllib.parse import urlparse
import requests
import cloudinary.api, cloudinary.uploader
from cloudinary.exceptions import Error, NotFound
from flask import request, session, abort, jsonify, render_template_string

ASSET = 'luka-discord-site/text-boxes.json'
FONTS = ['Arial', 'Georgia', 'Verdana', 'Courier New', 'Trebuchet MS', 'Times New Roman']
CACHE = {'until': 0, 'data': []}
LOCK = threading.Lock()

def validate(data):
    if not isinstance(data, list) or len(data) > 30:
        raise ValueError('Use at most 30 text boxes.')
    result, ids = [], set()
    expected = {'id','text','font','size','mode','section','x','y','width'}
    for box in data:
        if not isinstance(box, dict) or set(box) != expected:
            raise ValueError('Invalid text box.')
        if not isinstance(box['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', box['id']) or box['id'] in ids:
            raise ValueError('Invalid box identifier.')
        ids.add(box['id'])
        if not isinstance(box['text'], str) or len(box['text']) > 2000:
            raise ValueError('Each text box allows 2,000 characters.')
        if box['font'] not in FONTS or box['mode'] not in ['flow','free'] or box['section'] not in ['hero','community','below']:
            raise ValueError('Invalid font or placement.')
        for key, low, high in [('size',8,120),('x',0,90),('y',0,10000),('width',10,100)]:
            value = box[key]
            if type(value) not in (int,float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError('Invalid size or position.')
        if box['x'] + box['width'] > 100.01:
            raise ValueError('Text box extends beyond the page width.')
        result.append(dict(box))
    return result

def load():
    from app import storage
    with LOCK:
        if time.monotonic() < CACHE['until']:
            return [dict(b) for b in CACHE['data']]
        storage()
        try:
            asset = cloudinary.api.resource(ASSET, resource_type='raw', type='upload', timeout=15)
        except NotFound:
            data = []
        else:
            url = asset['secure_url']
            if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'res.cloudinary.com':
                raise ValueError('Unexpected storage URL.')
            response = requests.get(url, timeout=15, allow_redirects=False)
            response.raise_for_status()
            if len(response.content) > 300000:
                raise ValueError('Stored layout is too large.')
            data = validate(response.json())
        CACHE.update(data=data, until=time.monotonic()+60)
        return [dict(b) for b in data]

def install(application):
    from app import can_edit, csrf_ok, storage
    original = application.view_functions['home']
    def home():
        page = original()
        script = render_template_string(CLIENT, admin=can_edit(), csrf=session.setdefault('csrf', secrets.token_urlsafe(32)) if can_edit() else '', uid=session.get('uid','public'))
        return page.replace('</body>', script+'</body>')
    application.view_functions['home'] = home
    @application.get('/api/text-boxes')
    def get_boxes():
        try:
            return jsonify(boxes=load())
        except (Error, ValueError, KeyError, requests.RequestException):
            return jsonify(error='Text boxes could not be loaded. Reload before editing.'), 503
    @application.post('/api/text-boxes')
    def save_boxes():
        if not can_edit() or not csrf_ok():
            abort(403)
        if request.content_length is None or request.content_length > 300000:
            return jsonify(error='Layout is too large.'), 400
        try:
            data = validate(request.get_json())
        except (TypeError, ValueError) as error:
            return jsonify(error=str(error)), 400
        try:
            storage()
            with LOCK:
                cloudinary.uploader.upload(io.BytesIO(json.dumps(data,ensure_ascii=False).encode('utf-8')), resource_type='raw', type='upload', public_id=ASSET, overwrite=True, invalidate=True, timeout=30)
                CACHE.update(data=data, until=time.monotonic()+60)
            return jsonify(ok=True)
        except (Error, ValueError):
            return jsonify(error='Publishing failed. Your layout was not confirmed saved.'), 503

CLIENT = r'''<style>.builder-wrap{position:relative}.box-layer{position:absolute;inset:0;pointer-events:none;z-index:5}.custom-box{color:inherit;line-height:1.4;white-space:pre-wrap;overflow-wrap:anywhere;pointer-events:auto;min-height:1em}.custom-box.flow-box{margin:14px 0}.custom-box.free-box{position:absolute}.box-content{min-height:1em}.box-handle{display:none}body.inline-editing .custom-box{outline:1px dashed #ad5a80;outline-offset:3px}body.inline-editing .custom-box.selected{outline:3px solid #a24b78}body.inline-editing .box-handle{display:block;font:12px Arial;background:#ffe2ef;border:1px solid #b46d8e;cursor:grab;touch-action:none;padding:4px}#builder-controls{border-top:1px solid #dfb2c6;margin-top:8px;padding-top:6px}#builder-controls label{display:inline-block;margin:4px;font:12px Arial}#builder-controls input,#builder-controls select{max-width:160px;padding:5px;font:13px Arial}#builder-controls input[type=number]{width:68px}#builder-message{margin:4px 0;font:12px/1.5 Arial}body:has(#builder-controls){padding-bottom:380px}#builder-controls [hidden]{display:none!important}</style><script>(()=>{
const admin={{ admin|tojson }},token={{ csrf|tojson }},draftKey='luka-boxes-v1:'+{{ uid|tojson }},fonts=['Arial','Georgia','Verdana','Courier New','Trebuchet MS','Times New Roman'];
const wrap=document.querySelector('.wrap');if(!wrap)return;wrap.classList.add('builder-wrap');
const layer=document.createElement('div');layer.className='box-layer';wrap.append(layer);const zones={};for(const name of ['hero','community','below']){const z=document.createElement('div');z.className='box-zone';zones[name]=z;const host=name==='hero'?document.querySelector('.hero>div:first-child'):name==='community'?document.querySelector('.community'):document.querySelector('main');if(host)host.append(z)}
let boxes=[],saved=[],selected=null,loaded=false,busy=false,editing=false,drag=null,panel=null;const clone=v=>JSON.parse(JSON.stringify(v)),dirty=()=>JSON.stringify(boxes)!==JSON.stringify(saved),find=()=>boxes.find(b=>b.id===selected),$=id=>document.getElementById('builder-'+id),say=t=>{if($('message'))$('message').textContent=t};
function limits(b){b.size=Math.max(8,Math.min(120,b.size));b.width=Math.max(10,Math.min(100,b.width));b.x=Math.max(0,Math.min(100-b.width,b.x));b.y=Math.max(0,Math.min(10000,b.y))}
function extent(){let bottom=0;for(const el of layer.children)bottom=Math.max(bottom,el.offsetTop+el.offsetHeight);wrap.style.minHeight=bottom?bottom+40+'px':''}
function sync(){if(!admin||!panel)return;const b=find();for(const id of ['font','size','placement','width','x','y','delete','up','down'])$(id).disabled=busy||!editing||!b;$('add').disabled=busy||!loaded||boxes.length>=30;$('save').disabled=busy||!loaded||!dirty();$('draft').disabled=busy||!loaded;$('restore').disabled=busy||!loaded;$('discard').disabled=busy||!loaded||!dirty();if(b){$('font').value=b.font;$('size').value=b.size;$('placement').value=b.mode==='free'?'free':b.section;$('width').value=b.width;$('x').value=Math.round(b.x*100)/100;$('y').value=Math.round(b.y);$('x').disabled=$('y').disabled=busy||!editing||b.mode!=='free';$('up').disabled=$('down').disabled=busy||!editing||b.mode!=='flow'}$('state').textContent=dirty()?'Unsaved text-box changes':'Text boxes saved';document.querySelectorAll('.custom-box').forEach(el=>el.classList.toggle('selected',editing&&el.dataset.id===selected))}
function render(){layer.replaceChildren();for(const z of Object.values(zones))z.replaceChildren();for(const b of boxes){const el=document.createElement('div');el.className='custom-box '+(b.mode==='free'?'free-box':'flow-box');el.dataset.id=b.id;el.style.fontFamily=b.font;el.style.fontSize=b.size+'px';el.style.width=b.width+'%';if(b.mode==='free'){el.style.left=b.x+'%';el.style.top=b.y+'px'}const handle=document.createElement('button');handle.type='button';handle.className='box-handle';handle.textContent=b.mode==='free'?'Drag to move ↔':'Select box · use Move up / Move down';handle.disabled=busy;const content=document.createElement('div');content.className='box-content';content.textContent=b.text;content.contentEditable=admin&&editing&&!busy?'true':'false';if(admin&&editing){content.setAttribute('role','textbox');content.setAttribute('aria-label','Custom text box');content.setAttribute('aria-multiline','true')}el.append(handle,content);(b.mode==='free'?layer:zones[b.section]).append(el);if(admin){el.onfocusin=el.onclick=()=>{selected=b.id;sync()};content.oninput=()=>{b.text=content.innerText;selected=b.id;sync();extent()};content.onpaste=e=>{e.preventDefault();const s=window.getSelection();if(!s||!s.rangeCount)return;const r=s.getRangeAt(0);if(!content.contains(r.commonAncestorContainer))return;r.deleteContents();const n=document.createTextNode((e.clipboardData?.getData('text/plain')||'').slice(0,2000));r.insertNode(n);r.setStartAfter(n);r.collapse(true);s.removeAllRanges();s.addRange(r);b.text=content.innerText;sync();extent()};content.ondrop=e=>e.preventDefault();handle.onpointerdown=e=>{if(!editing||busy)return;selected=b.id;sync();if(b.mode!=='free')return;e.preventDefault();handle.setPointerCapture(e.pointerId);drag={id:b.id,px:e.clientX,py:e.clientY,x:b.x,y:b.y};};handle.onpointermove=e=>{if(!drag||drag.id!==b.id)return;e.preventDefault();b.x=drag.x+(e.clientX-drag.px)/wrap.getBoundingClientRect().width*100;b.y=drag.y+e.clientY-drag.py;limits(b);el.style.left=b.x+'%';el.style.top=b.y+'px';sync();extent()};handle.onpointerup=handle.onpointercancel=()=>{drag=null}}}sync();extent()}
if(admin){panel=document.createElement('details');panel.id='builder-controls';panel.open=true;panel.innerHTML='<summary>Text-box builder · <span id="builder-state"></span></summary><button id="builder-add">＋ Add text box</button><label>Font <select id="builder-font"></select></label><label>Size (px) <input id="builder-size" type="number" min="8" max="120"></label><label>Placement <select id="builder-placement"><option value="hero">Stack in main card</option><option value="community">Stack in invitation</option><option value="below">Stack below invitation</option><option value="free">Free placement / drag</option></select></label><label>Width (%) <input id="builder-width" type="number" min="10" max="100"></label><label>Left (%) <input id="builder-x" type="number" min="0" max="90" step="0.1"></label><label>Top (px) <input id="builder-y" type="number" min="0" max="10000"></label><button id="builder-up">Move up</button><button id="builder-down">Move down</button><button id="builder-delete">Delete selected box</button><button id="builder-save">Save text boxes for everyone</button><button id="builder-draft">Save box draft locally</button><button id="builder-restore">Restore box draft</button><button id="builder-discard">Discard box edits</button><p id="builder-message" role="status" aria-live="polite">Loading text boxes…</p>';const toolbar=document.getElementById('inline-toolbar');if(!toolbar)return;toolbar.append(panel);for(const font of fonts){const o=document.createElement('option');o.value=o.textContent=font;$('font').append(o)}
new MutationObserver(()=>{const next=document.body.classList.contains('inline-editing');if(next!==editing){editing=next;render()}}).observe(document.body,{attributes:true,attributeFilter:['class']});editing=document.body.classList.contains('inline-editing');
$('add').onclick=()=>{if(!loaded||busy||boxes.length>=30)return;if(!editing){document.getElementById('inline-toggle').click();editing=document.body.classList.contains('inline-editing');if(!editing){say('Wait for page settings to load, then enable Edit text.');return}}const b={id:crypto.randomUUID(),text:'Click here and type your text',font:'Arial',size:20,mode:'flow',section:'hero',x:10,y:150,width:80};boxes.push(b);selected=b.id;render();document.querySelector('[data-id="'+b.id+'"] .box-content').focus();say('Select a placement: stack in a section, or free placement to drag anywhere within the page.')} ;
for(const name of ['font','size','width','x','y','placement'])$(name).onchange=()=>{const b=find();if(!b||busy||!editing)return;if(name==='font')b.font=$('font').value;else if(name==='placement'){const v=$('placement').value;b.mode=v==='free'?'free':'flow';if(v!=='free')b.section=v}else{const n=Number($(name).value);if(!Number.isFinite(n))return;b[name]=n}limits(b);render()};
for(const [name,step]of [['up',-1],['down',1]])$(name).onclick=()=>{const b=find();if(!b||busy||b.mode!=='flow')return;const indices=boxes.map((v,i)=>v.mode==='flow'&&v.section===b.section?i:-1).filter(i=>i>=0),p=indices.indexOf(boxes.indexOf(b)),q=p+step;if(q>=0&&q<indices.length){const a=indices[p],c=indices[q];[boxes[a],boxes[c]]=[boxes[c],boxes[a]];render()}};
$('delete').onclick=()=>{if(busy||!find())return;if(!confirm('Delete the selected text box? Publish to make the deletion public.'))return;boxes=boxes.filter(b=>b.id!==selected);selected=null;render()};
$('discard').onclick=()=>{if(!confirm('Discard unpublished text-box changes?'))return;boxes=clone(saved);selected=null;render();say('Restored the last loaded or published text boxes.')};
function validDraft(data){return Array.isArray(data)&&data.length<=30&&data.every(b=>b&&typeof b.id==='string'&&/^[A-Za-z0-9_-]{1,60}$/.test(b.id)&&typeof b.text==='string'&&b.text.length<=2000&&fonts.includes(b.font)&&['flow','free'].includes(b.mode)&&['hero','community','below'].includes(b.section)&&['size','x','y','width'].every(k=>typeof b[k]==='number'&&Number.isFinite(b[k]))&&b.size>=8&&b.size<=120&&b.x>=0&&b.y>=0&&b.y<=10000&&b.width>=10&&b.width<=100&&b.x+b.width<=100.01)&&new Set(data.map(b=>b.id)).size===data.length}
$('draft').onclick=()=>{if(!validDraft(boxes)){say('Cannot save: each box allows 2,000 characters; check sizes and positions.');return}try{localStorage.setItem(draftKey,JSON.stringify(boxes));say('Box draft saved only in this browser.')}catch(e){say('Local storage unavailable. Draft was not saved.')}};
$('restore').onclick=()=>{try{const raw=localStorage.getItem(draftKey);if(!raw){say('No box draft was found.');return}const d=JSON.parse(raw);if(!validDraft(d))throw new Error('Invalid draft');if(dirty()&&!confirm('Replace unpublished box edits with the local draft?'))return;boxes=d;selected=null;render();say('Draft restored. Enable Edit text to change it, or publish when ready.')}catch(e){say('Could not restore a valid box draft.')}};
$('save').onclick=async()=>{if(busy||!loaded)return;if(!validDraft(boxes)){say('Cannot publish: each box allows 2,000 characters; check sizes and positions.');return}busy=true;render();say('Publishing text boxes…');try{const r=await fetch('/api/text-boxes',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':token},body:JSON.stringify(boxes)});let d;try{d=await r.json()}catch(e){throw new Error('Unexpected response. Check your sign-in.')}if(!r.ok)throw new Error(d.error||'Publishing failed.');saved=clone(boxes);say('Text boxes saved for everyone. Visitors see them on reload.')}catch(e){say(e.message+' Your changes remain on screen.')}finally{busy=false;render()}};
window.addEventListener('beforeunload',e=>{if(dirty()){e.preventDefault();e.returnValue=''}});sync()}
fetch('/api/text-boxes').then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.error||'Loading failed.');boxes=d.boxes;saved=clone(boxes);loaded=true;render();say('Use Edit text to add/select boxes. Free placement may overlap on smaller screens; stacked boxes follow the section layout. Text boxes publish separately from the original page text; last publisher wins.')}).catch(e=>say(e.message));window.addEventListener('resize',extent);
})();</script>'''
