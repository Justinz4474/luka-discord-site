from app import app as application


def initialize():
    if application.extensions.get('studio_bootstrap_ready'):
        return
    if 'public_settings' not in application.view_functions:
        from cms import install
        install(application)
    if 'artwork_editor' in application.view_functions:
        from crop_editor import install
        install(application)
    if not application.extensions.get('studio_bootstrap_inline'):
        import inline_editor
        inline_editor.TOOLS = inline_editor.TOOLS.replace(chr(13), r'\r').replace(chr(10) + '/g', r'\n/g').replace("'" + chr(10) + "'", r"'\n'")
        inline_editor.install(application)
        application.extensions['studio_bootstrap_inline'] = True
    if 'get_boxes' not in application.view_functions:
        from page_builder import install
        install(application)
    if 'get_styles' not in application.view_functions:
        from editor_upgrade import install
        install(application)
    if 'studio' not in application.view_functions:
        from design_studio import install
        install(application)
    rules = {rule.rule for rule in application.url_map.iter_rules()}
    required = {'/studio', '/api/page-settings', '/api/text-boxes', '/api/original-text-styles'}
    missing = required - rules
    if missing:
        raise RuntimeError('Required editor routes are missing: ' + ', '.join(sorted(missing)))
    application.extensions['studio_bootstrap_ready'] = True


initialize()


def post_worker_init(worker):
    if worker.wsgi is not application:
        raise RuntimeError('Gunicorn loaded a different application than Studio bootstrap')
    worker.log.info('Studio startup verified: /studio and all editor APIs are registered')
