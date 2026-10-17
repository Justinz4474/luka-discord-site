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
    import design_studio
    # Whitespace prevents CSS ID selectors from opening a Jinja comment.
    design_studio.UI = design_studio.UI.replace('{#', '{ #')
    application.jinja_env.parse(design_studio.UI)
    application.jinja_env.parse(design_studio.SCRIPT)
    if 'studio' not in application.view_functions:
        design_studio.install(application)
    rules = {rule.rule for rule in application.url_map.iter_rules()}
    required = {'/studio', '/api/page-settings', '/api/text-boxes', '/api/original-text-styles'}
    missing = required - rules
    if missing:
        raise RuntimeError('Required editor routes are missing: ' + ', '.join(sorted(missing)))
    from app import OWNER
    with application.test_client() as client:
        response = client.get('/studio', base_url='https://localhost')
        if response.status_code != 403:
            raise RuntimeError('Studio access restriction check failed')
        with client.session_transaction(base_url='https://localhost') as test_session:
            test_session['uid'] = OWNER
            test_session['csrf'] = 'startup-render-check-only'
        response = client.get('/studio', base_url='https://localhost')
        body = response.get_data(as_text=True)
        if response.status_code != 200 or 'id="s-workspace"' not in body or 'id="s-publish"' not in body:
            raise RuntimeError('Approved-editor Studio rendering check failed')
    application.extensions['studio_bootstrap_ready'] = True


initialize()


def post_worker_init(worker):
    if worker.wsgi is not application:
        raise RuntimeError('Gunicorn loaded a different application than Studio bootstrap')
    worker.log.info('Studio verified: routes registered, unauthorized access blocked, approved-editor page renders HTTP 200')
