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
    from animated_background import install as install_background, markup as background_markup
    install_background(application)
    from starfield_background import install as install_starfield
    install_starfield(application)
    from studio_background_sync import install as install_background_sync
    install_background_sync(application)
    from discord_member_counts import install as install_counts, CLIENT as counts_markup
    install_counts(application)

    def home():
        page = base_home()
        page = page.replace('<a class="btn pink" href="/editor">Edit website</a> ', '')
        boxes = render_template_string(page_builder.CLIENT, admin=False, csrf='', uid='public')
        styles = render_template_string(editor_upgrade.STYLES, admin=False, csrf='', selectors=editor_upgrade.SELECTORS, fonts=editor_upgrade.FONTS)
        controls = ''
        if can_edit():
            controls = '<a href="/studio" style="position:fixed;top:12px;right:12px;z-index:1100;background:#6347cf;color:white;padding:12px 18px;border-radius:12px;font:14px Arial;text-decoration:none">Open design studio ↗</a>'
        music = homepage_markup(can_edit())
        music = music.replace('<summary>♫ Entrance video & music</summary>', '<summary>Alien Stage Music</summary>', 1)
        music += '<style>#site-music{left:12px!important;right:auto!important;width:min(240px,calc(100vw - 24px));padding:7px 9px;border-radius:12px;font-size:11px;line-height:1.4}#site-music summary{font-size:12px}#site-music button{font-size:11px;padding:5px 7px;margin:4px 3px 2px 0}#site-music #entrance-video{width:100%;height:auto;aspect-ratio:16/9;object-fit:contain;margin-top:7px;border-radius:7px}#music-state,#music-background,#music-spotify,#music-embed,#site-music>p,#site-music>a,#entrance-video-state,#site-music section>p{display:none!important}</style>'
        return page.replace('</body>', cms.CLIENT + boxes + styles + controls + music + background_markup() + counts_markup + '</body>')

    application.view_functions['home'] = home
