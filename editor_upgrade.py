import io, json, math, time, threading, secrets
from urllib.parse import urlparse
import requests
import cloudinary.api, cloudinary.uploader
from cloudinary.exceptions import Error, NotFound
from flask import session, request, jsonify, abort, render_template_string

SELECTORS = {'site_name':'header a[href="#"]','badge':'.pill','headline_top':'#inline-headline-top','headline_bottom':'.hero h1 span:last-child','subtitle':'.subtitle','description':'.description','caption':'.caption','ribbon':'.ribbon','community_heading':'.community h2','join_top':'.hero .btn.pink','join_bottom':'.community .btn.pink','navigation':'a[href="#community"]','nav_discord':'header a[target]','copy_text':'#copy','placeholder':'.placeholder p','footer':'footer'}
FONTS = ['Arial','Georgia','Verdana','Courier New','Trebuchet MS','Times New Roman']
ASSET = 'luka-discord-site/original-text-styles.json'
LOCK = threading.Lock()
CACHE = {'until':0,'data':{}}

def clean(data):
    if not isinstance(data,dict) or set(data)-set(SELECTORS):
        raise ValueError('Invalid text style targets.')
    for value in data.values():
        if not isinstance(value,dict) or set(value)!={'font','size','hidden'}:
            raise ValueError('Invalid text style.')
        if value['font'] not in FONTS+[''] or type(value['hidden']) is not bool:
            raise ValueError('Invalid font or visibility.')
        n=value['size']
        if n is not None and (type(n) not in (int,float) or not math.isfinite(n) or not 8<=n<=200):
            raise ValueError('Use a font size from 8 to 200 pixels.')
    return data

def load():
    from app import storage
    with LOCK:
        if time.monotonic()<CACHE['until']:
            return json.loads(json.dumps(CACHE['data']))
        storage()
        try:
            asset=cloudinary.api.resource(ASSET,resource_type='raw',type='upload',timeout=15)
        except NotFound:
            data={}
        else:
            url=asset['secure_url']
            if urlparse(url).scheme!='https' or urlparse(url).hostname!='res.cloudinary.com':
                raise ValueError('Unexpected storage URL.')
            r=requests.get(url,timeout=15,allow_redirects=False)
            r.raise_for_status()
            if len(r.content)>20000:
                raise ValueError('Styles too large.')
            data=clean(r.json())
        CACHE.update(data=data,until=time.monotonic()+60)
        return json.loads(json.dumps(data))

def install(application):
    import page_builder
    from app import can_edit,csrf_ok,storage
    replacements=[
        ("$('size').value=b.size;","if(document.activeElement!==$('size'))$('size').value=b.size;"),
        ("content.contentEditable=admin&&editing&&!busy?'true':'false';","content.contentEditable='false';el.tabIndex=admin&&editing?0:-1;content.ondblclick=()=>{if(admin&&editing&&!busy){content.contentEditable='true';content.focus()}};"),
        ("el.onfocusin=el.onclick=()=>{selected=b.id;sync()};","el.onfocusin=()=>{selected=b.id;sync()};el.onclick=e=>{selected=b.id;sync();if(!e.target.isContentEditable)el.focus()};"),
        ("if(!confirm('Delete the selected text box? Publish to make the deletion public.'))return;","boxUndo.push(clone(boxes));"),
        ("<button id=\"builder-delete\">Delete selected box</button>","<button id=\"builder-delete\">Delete selected box</button><button id=\"builder-undo\">Undo box deletion</button>"),
        ("let boxes=[],saved=[]","let boxUndo=[],boxes=[],saved=[]"),
        ("document.querySelector('[data-id=\"'+b.id+'\"] .box-content').focus();","document.querySelector('[data-id=\"'+b.id+'\"]').focus();"),
        ("window.addEventListener('beforeunload',e=>{if(dirty())",BOX_KEYS+"window.addEventListener('beforeunload',e=>{if(dirty())")
    ]
    for old,new in replacements:
        if old not in page_builder.CLIENT:
            raise RuntimeError('Text-box upgrade target changed: '+old[:70])
        page_builder.CLIENT=page_builder.CLIENT.replace(old,new,1)
    original=application.view_functions['home']
    def home():
        page=original()
        return page.replace('</body>',render_template_string(STYLES,admin=can_edit(),csrf=session.setdefault('csrf',secrets.token_urlsafe(32)) if can_edit() else '',selectors=SELECTORS,fonts=FONTS)+'</body>')
    application.view_functions['home']=home
    @application.get('/api/original-text-styles')
    def get_styles():
        try:
            return jsonify(styles=load())
        except (Error,ValueError,KeyError,requests.RequestException):
            return jsonify(error='Original-text styles could not be loaded.'),503
    @application.post('/api/original-text-styles')
    def save_styles():
        if not can_edit() or not csrf_ok():
            abort(403)
        if request.content_length is None or request.content_length>20000:
            return jsonify(error='Style request too large.'),400
        try:
            data=clean(request.get_json())
        except (ValueError,TypeError) as e:
            return jsonify(error=str(e)),400
        try:
            storage()
            with LOCK:
                cloudinary.uploader.upload(io.BytesIO(json.dumps(data).encode()),resource_type='raw',type='upload',public_id=ASSET,overwrite=True,invalidate=True,timeout=30)
                CACHE.update(data=data,until=time.monotonic()+60)
            return jsonify(ok=True)
        except (Error,ValueError):
            return jsonify(error='Saving text styles failed.'),503

BOX_KEYS = r'''$('size').oninput=()=>{const b=find(),input=$('size'),n=input.valueAsNumber;if(!b||busy||!editing||!Number.isFinite(n)||n<8||n>120)return;b.size=n;const el=document.querySelector('.custom-box[data-id="'+b.id+'"]');if(el)el.style.fontSize=n+'px';sync();extent()};
$('undo').onclick=()=>{if(busy||!boxUndo.length)return;boxes=boxUndo.pop();selected=null;render();say('Box deletion undone. Publish to keep it.')};
document.addEventListener('keydown',e=>{if(!editing||busy||e.target.closest('input,textarea,select')||e.target.isContentEditable)return;const el=e.target.closest('.custom-box');if(!el)return;selected=el.dataset.id;if(e.key==='Delete'||e.key==='Backspace'){e.preventDefault();boxUndo.push(clone(boxes));boxes=boxes.filter(b=>b.id!==selected);selected=null;render();say('Box removed locally. Undo box deletion restores it; publish when ready.')}else if(e.key==='Enter'){e.preventDefault();const content=el.querySelector('.box-content');content.contentEditable='true';content.focus()}});
'''

STYLES = r'''<style>.original-selected{outline:3px solid #456dba!important}body.inline-editing .original-hidden{display:revert!important;opacity:.35;outline:2px dashed #bd4e70!important}.original-hidden{display:none!important}#original-controls{margin-top:8px;border-top:1px solid #dbafc3;padding-top:7px}#original-controls input{width:80px;padding:6px}#original-controls select{padding:6px;max-width:180px}#original-message{font:12px/1.5 Arial;margin:4px 0}body:has(#original-controls){padding-bottom:500px}</style><script>(()=>{
const admin={{ admin|tojson }},token={{ csrf|tojson }},selectors={{ selectors|tojson }},fonts={{ fonts|tojson }};
let styles={},saved={},loaded=false,busy=false,selected=null,panel=null;const $=id=>document.getElementById('original-'+id),editing=()=>document.body.classList.contains('inline-editing'),copy=v=>JSON.parse(JSON.stringify(v)),dirty=()=>JSON.stringify(styles)!==JSON.stringify(saved),say=t=>{if($('message'))$('message').textContent=t};
function element(k){if(k==='headline_top'){let el=document.querySelector('#inline-headline-top');if(!el){const h=document.querySelector('.hero h1');if(h?.firstChild?.nodeType===Node.TEXT_NODE){el=document.createElement('span');el.id='inline-headline-top';el.style.color='inherit';el.textContent=h.firstChild.textContent;h.replaceChild(el,h.firstChild)}}return el}return document.querySelector(selectors[k])}
function apply(){for(const k of Object.keys(selectors)){const el=element(k);if(!el)continue;el.dataset.originalKey=k;const s=styles[k]||{font:'',size:null,hidden:false};if(!el.dataset.originalDefaults){el.dataset.originalDefaults=JSON.stringify({font:el.style.fontFamily,size:el.style.fontSize})}const d=JSON.parse(el.dataset.originalDefaults);el.style.fontFamily=s.font||d.font;el.style.fontSize=s.size===null?d.size:s.size+'px';el.classList.toggle('original-hidden',s.hidden);el.classList.toggle('original-selected',admin&&editing()&&selected===k);if(admin&&editing()){el.contentEditable='false';el.tabIndex=0;el.title='Click to select. Double-click or press Enter to type.'}}sync()}
function sync(){if(!admin||!panel)return;const el=selected&&element(selected),disabled=!loaded||busy||!editing()||!el;for(const k of ['font','size','hide','reset'])$(k).disabled=disabled;$('save').disabled=!loaded||busy||!dirty();$('discard').disabled=!loaded||busy||!dirty();$('target').disabled=!loaded||busy;if(el){const s=styles[selected]||{font:'',size:null,hidden:false};$('target').value=selected;$('font').value=s.font;if(document.activeElement!==$('size'))$('size').value=s.size===null?parseFloat(getComputedStyle(el).fontSize):s.size;$('hide').textContent=s.hidden?'Restore selected text':'Hide selected text'}$('state').textContent=dirty()?'Unsaved original-text styles':'Original-text styles saved'}
function update(patch){if(!selected||!loaded||busy||!editing())return;styles[selected]={font:'',size:null,hidden:false,...styles[selected],...patch};apply()}
if(admin){panel=document.createElement('details');panel.id='original-controls';panel.open=true;panel.innerHTML='<summary>Original page text · <span id="original-state"></span></summary><label>Select original text <select id="original-target"><option value="">Choose an element</option></select></label><label>Font <select id="original-font"><option value="">Original font</option></select></label><label>Font size (px) <input id="original-size" type="number" min="8" max="200" step="1" inputmode="numeric"></label><button id="original-hide">Hide selected text</button><button id="original-reset">Reset selected style</button><button id="original-save">Save original-text styles for everyone</button><button id="original-discard">Discard style edits</button><p id="original-message" role="status" aria-live="polite"></p>';const bar=document.getElementById('inline-toolbar');if(!bar)return;bar.append(panel);for(const k of Object.keys(selectors)){const o=document.createElement('option');o.value=k;o.textContent=k.replaceAll('_',' ');$('target').append(o)}for(const font of fonts){const o=document.createElement('option');o.value=o.textContent=font;$('font').append(o)}
$('target').onchange=()=>{selected=$('target').value||null;apply()};$('font').onchange=()=>update({font:$('font').value});$('size').oninput=()=>{const n=$('size').valueAsNumber;if(Number.isFinite(n)&&n>=8&&n<=200)update({size:n})};$('size').onblur=()=>sync();$('hide').onclick=()=>update({hidden:!(styles[selected]?.hidden||false)});$('reset').onclick=()=>{if(!selected||busy)return;delete styles[selected];apply()};$('discard').onclick=()=>{if(!confirm('Discard unpublished original-text style changes?'))return;styles=copy(saved);apply()};
document.addEventListener('click',e=>{if(!editing()||busy)return;const el=e.target.closest('[data-original-key]');if(!el)return;e.preventDefault();selected=el.dataset.originalKey;if(!el.isContentEditable)el.focus();apply()});document.addEventListener('dblclick',e=>{if(!editing()||busy)return;const el=e.target.closest('[data-original-key]');if(el){e.preventDefault();el.contentEditable='true';el.focus()}});document.addEventListener('keydown',e=>{if(!editing()||busy||e.target.isContentEditable||e.target.closest('input,textarea,select'))return;const el=e.target.closest('[data-original-key]');if(!el)return;selected=el.dataset.originalKey;if(e.key==='Enter'){e.preventDefault();el.contentEditable='true';el.focus()}else if(e.key==='Delete'||e.key==='Backspace'){e.preventDefault();update({hidden:true})}});
new MutationObserver(()=>{if(!editing())document.querySelectorAll('[data-original-key]').forEach(el=>el.classList.remove('original-selected'));else apply()}).observe(document.body,{attributes:true,attributeFilter:['class']});
$('save').onclick=async()=>{if(busy||!loaded)return;busy=true;sync();say('Saving original-text styles…');try{const r=await fetch('/api/original-text-styles',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':token},body:JSON.stringify(styles)});let d;try{d=await r.json()}catch(e){throw new Error('Unexpected response. Check your sign-in.')}if(!r.ok)throw new Error(d.error||'Saving failed.');saved=copy(styles);say('Original-text fonts, sizes, and visibility saved for everyone.')}catch(e){say(e.message)}finally{busy=false;sync()}};window.addEventListener('beforeunload',e=>{if(dirty()){e.preventDefault();e.returnValue=''}});sync()}
window.addEventListener('inline-settings-ready',()=>setTimeout(apply,0));fetch('/api/original-text-styles').then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.error||'Style loading failed.');styles=d.styles;saved=copy(styles);loaded=true;apply();say('Click to select; double-click or Enter to type. Type font sizes directly. Delete hides selected original text; Restore brings it back. Save styles separately from page wording and custom boxes.')}).catch(e=>say(e.message));
})();</script>'''
