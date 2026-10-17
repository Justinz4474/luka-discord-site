def post_worker_init(worker):
    from cms import install
    install(worker.wsgi)
