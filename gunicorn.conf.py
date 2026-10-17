def post_worker_init(worker):
    from cms import install
    install(worker.wsgi)
    from crop_editor import install as install_crop
    install_crop(worker.wsgi)
    import inline_editor
    inline_editor.TOOLS = inline_editor.TOOLS.replace(chr(13), r'\r').replace(chr(10) + '/g', r'\n/g').replace("'" + chr(10) + "'", r"'\n'")
    inline_editor.install(worker.wsgi)
    from page_builder import install as install_builder
    install_builder(worker.wsgi)
