from flask import render_template_string

ORIGIN = 'https://pub-64f1c2f5cbd44dcfafc9f94b8c5f743c.r2.dev'
GIF = ORIGIN + '/20a10dab0077e41f9e6ff4bbda0d6815.gif'


def install(application):
    if application.extensions.get('animated_background_ready'):
        return
    def allow_background(response):
        policy = response.headers.get('Content-Security-Policy', '')
        if policy:
            parts = [part.strip() for part in policy.split(';') if part.strip()]
            for i, part in enumerate(parts):
                if part.split()[0] == 'img-src':
                    if ORIGIN not in part.split()[1:]:
                        parts[i] += ' ' + ORIGIN
                    break
            else:
                parts.append("img-src 'self' https://res.cloudinary.com " + ORIGIN)
            response.headers['Content-Security-Policy'] = '; '.join(parts)
        return response
    application.after_request_funcs.setdefault(None, []).insert(0, allow_background)
    application.jinja_env.parse(MARKUP)
    application.extensions['animated_background_ready'] = True


def markup():
    return render_template_string(MARKUP, gif=GIF)


MARKUP = r'''<style>body{isolation:isolate}#site-animated-bg{position:fixed;inset:0;z-index:-1;pointer-events:none;background-color:#211332;background-image:linear-gradient(#130d29aa,#130d29aa);background-position:center;background-repeat:no-repeat;background-size:cover}#background-motion{position:fixed;top:64px;right:12px;z-index:1190;padding:8px 12px;border:1px solid #b991d1;border-radius:12px;background:#241534ed;color:#fff;font:12px Arial;cursor:pointer}.wrap>header,.wrap>footer,.wrap>.ribbon{color:#fff;text-shadow:0 1px 4px #000}@media print{ #site-animated-bg,#background-motion{display:none}}</style><div id="site-animated-bg" aria-hidden="true"></div><button id="background-motion" type="button" hidden>Pause background</button><script>(()=>{const layer=document.getElementById('site-animated-bg'),button=document.getElementById('background-motion'),preference=matchMedia('(prefers-reduced-motion: reduce)'),url={{ gif|tojson }};let paused=false;try{paused=localStorage.getItem('luka-background-paused')==='1'}catch(e){}function apply(){const running=!paused&&!preference.matches;layer.style.backgroundImage=running?'linear-gradient(#130d29aa,#130d29aa),url("'+url+'")':'linear-gradient(#130d29aa,#130d29aa)';button.hidden=preference.matches;button.textContent=running?'Pause background':'Play background';button.setAttribute('aria-label',running?'Pause animated background and use a plain background':'Play animated background')}button.onclick=()=>{paused=!paused;try{localStorage.setItem('luka-background-paused',paused?'1':'0')}catch(e){}apply()};if(preference.addEventListener)preference.addEventListener('change',apply);else if(preference.addListener)preference.addListener(apply);apply()})();</script>'''
