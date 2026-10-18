from flask import render_template_string


def install(application):
    from app import home as base_home, can_edit
    import cms, page_builder, editor_upgrade
    from frame_controls import install as install_frames
    install_frames(application)
    from deletion_controls import install as install_deletion
    install_deletion(application)
    from music_controls import install as install_music, homepage_markup
    install_music(application)
    from mp4_music_support import install as install_mp4
    install_mp4(application)
    from batch_music import install as install_batch
    install_batch(application)
    from entrance_video import install as install_video
    install_video(application)

    def home():
        page = base_home()
        page = page.replace('<a class="btn pink" href="/editor">Edit website</a> ', '')
        boxes = render_template_string(page_builder.CLIENT, admin=False, csrf='', uid='public')
        styles = render_template_string(editor_upgrade.STYLES, admin=False, csrf='', selectors=editor_upgrade.SELECTORS, fonts=editor_upgrade.FONTS)
        controls = ''
        if can_edit():
            controls = '<a href="/studio" style="position:fixed;top:12px;right:12px;z-index:1100;background:#6347cf;color:white;padding:12px 18px;border-radius:12px;font:14px Arial;text-decoration:none">Open design studio ↗</a>'
        music = homepage_markup(can_edit())
        music += '<style>#music-state,#music-background,#music-spotify,#music-embed,#site-music>p,#site-music>a,#entrance-video-state,#site-music section>p{display:none!important}</style>'
        return page.replace('</body>', cms.CLIENT + boxes + styles + controls + music + '</body>')

    application.view_functions['home'] = home
