def post_worker_init(worker):
    from cms import install
    install(worker.wsgi)
    from crop_editor import install as install_crop
    install_crop(worker.wsgi)
