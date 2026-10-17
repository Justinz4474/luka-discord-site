from flask import render_template_string


def install(application):
    from app import home as base_home, can_edit
    import cms, page_builder, editor_upgrade
    from frame_controls import install as install_frames
    install_frames(application)

    def home():
        page = base_home()
        page = page.replace('<a class="btn pink" href="/editor">Edit website</a> ', '')
        boxes = render_template_string(page_builder.CLIENT, admin=False, csrf='', uid='public')
        styles = render_template_string(editor_upgrade.STYLES, admin=False, csrf='', selectors=editor_upgrade.SELECTORS, fonts=editor_upgrade.FONTS)
        controls = ''
        if can_edit():
            controls = '<a href="/studio" style="position:fixed;top:12px;right:12px;z-index:1100;background:#6347cf;color:white;padding:12px 18px;border-radius:12px;font:14px Arial;text-decoration:none">Open design studio ↗</a>'
        return page.replace('</body>', cms.CLIENT + boxes + styles + controls + '</body>')

    application.view_functions['home'] = home
