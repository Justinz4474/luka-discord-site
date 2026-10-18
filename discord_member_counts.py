import re
import threading
import time
import requests
from flask import jsonify
import cms


def install(application):
    if application.extensions.get('discord_member_counts_ready'):
        return
    cache = {'until': 0, 'payload': None, 'status': 503}
    lock = threading.Lock()

    @application.get('/api/discord-member-counts')
    def discord_member_counts():
        with lock:
            if time.monotonic() >= cache['until']:
                payload = {'available': False, 'error': 'Temporarily unavailable'}
                status, lifetime = 503, 60
                try:
                    invite = cms.load()['invite']
                    match = re.fullmatch(r'https://discord\.gg/([A-Za-z0-9-]+)', invite)
                    if not match:
                        raise ValueError('Invalid saved invite')
                    response = requests.get(
                        'https://discord.com/api/v10/invites/' + match.group(1),
                        params={'with_counts': 'true'}, timeout=(3, 7),
                        allow_redirects=False)
                    if response.status_code == 429:
                        try:
                            lifetime = min(3600, max(60, int(float(response.headers.get('Retry-After', 60)))))
                        except (TypeError, ValueError, OverflowError):
                            lifetime = 60
                    else:
                        response.raise_for_status()
                        data = response.json()
                        members = data.get('approximate_member_count')
                        online = data.get('approximate_presence_count')
                        if any(type(value) is not int or value < 0 for value in (members, online)):
                            raise ValueError('Missing Discord counts')
                        payload = {'available': True, 'members': members, 'online': online,
                                   'approximate': True, 'updated_at': int(time.time())}
                        status = 200
                except Exception:
                    application.logger.warning('Discord member counts temporarily unavailable')
                cache.update(payload=payload, status=status, until=time.monotonic() + lifetime)
            response = jsonify(cache['payload'])
            response.status_code = cache['status']
            response.headers['Cache-Control'] = 'no-store'
            if cache['status'] != 200:
                response.headers['Retry-After'] = str(max(1, int(cache['until'] - time.monotonic()) + 1))
            return response

    original_studio = application.view_functions['studio']
    def studio():
        page = original_studio()
        return page.replace('</body>', CLIENT + '</body>', 1)
    application.view_functions['studio'] = studio
    application.extensions['discord_member_counts_ready'] = True


CLIENT = r'''<style>
.discord-counts{margin:12px 0 18px;max-width:100%;font:12px/1.5 system-ui,sans-serif;letter-spacing:normal;white-space:normal}.discord-counts-row{display:flex;gap:9px;flex-wrap:wrap}.community .discord-counts-row{justify-content:center}.discord-count-badge{display:inline-flex;align-items:center;gap:7px;max-width:100%;padding:9px 12px;border:1px solid #70b39a;border-radius:999px;background:#e3f8ec;color:#214e3c;box-shadow:0 2px 6px #214e3c12}.discord-count-dot{width:7px;height:7px;border-radius:50%;background:#338c60;flex:none}.discord-counts small{display:block;margin-top:7px;color:#416451;font:10px/1.5 system-ui,sans-serif}.discord-counts[data-unavailable] .discord-count-dot{background:#82978a}
</style><script>(()=>{
'use strict';
if(window.lukaDiscordCountsLoaded)return;window.lukaDiscordCountsLoaded=true;
const root=document.querySelector('#s-workspace>.wrap')||document.querySelector('body>.wrap');
if(!root)return;
const groups=[];
for(const section of ['.hero','.community']){
 const buttons=root.querySelector(section+' .buttons');if(!buttons)continue;
 const group=document.createElement('div');group.className='discord-counts';group.setAttribute('role','group');group.setAttribute('aria-label','Discord server member counts');
 group.innerHTML='<div class="discord-counts-row"><span class="discord-count-badge"><span class="discord-count-dot" aria-hidden="true"></span><span data-members>Loading members…</span></span><span class="discord-count-badge"><span class="discord-count-dot" aria-hidden="true"></span><span data-online>Loading online…</span></span></div><small>Discord estimates · refreshes every minute</small>';
 buttons.after(group);groups.push(group);
}
let pending=false,lastAttempt=0;
const format=new Intl.NumberFormat();
async function refresh(){
 if(pending||document.hidden||Date.now()-lastAttempt<60000)return;
 pending=true;lastAttempt=Date.now();
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),12000);
 try{
  const response=await fetch('/api/discord-member-counts',{cache:'no-store',signal:controller.signal});
  if(!response.ok)throw new Error('Unavailable');
  const data=await response.json();
  if(!data.available||!Number.isInteger(data.members)||data.members<0||!Number.isInteger(data.online)||data.online<0)throw new Error('Invalid counts');
  for(const group of groups){
   group.removeAttribute('data-unavailable');
   group.querySelector('[data-members]').textContent=format.format(data.members)+' members';
   group.querySelector('[data-online]').textContent=format.format(data.online)+' online';
   group.querySelector('small').textContent='Discord estimates · refreshes every minute'+(document.getElementById('s-workspace')?' · uses your published invite':'');
   group.title='Last fetched: '+new Date(data.updated_at*1000).toLocaleTimeString();
  }
 }catch(error){
  for(const group of groups){group.setAttribute('data-unavailable','');group.removeAttribute('title');group.querySelector('[data-members]').textContent='Members: temporarily unavailable';group.querySelector('[data-online]').textContent='Online: temporarily unavailable';group.querySelector('small').textContent='Unable to load Discord counts · retrying automatically';}
 }finally{clearTimeout(timeout);pending=false;}
}
refresh();setInterval(refresh,60000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
window.addEventListener('focus',refresh);
})();</script>'''
