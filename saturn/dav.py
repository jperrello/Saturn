from pathlib import Path


def make_app(root):
    from wsgidav.wsgidav_app import WsgiDAVApp
    return WsgiDAVApp({
        "host": "127.0.0.1",
        "port": 0,
        "mount_path": "/share/claude",
        "provider_mapping": {"/": {"root": str(Path(root).expanduser().resolve()), "readonly": True}},
        "simple_dc": {"user_mapping": {"*": True}},
        "http_authenticator": {"accept_basic": False, "accept_digest": False, "default_to_digest": False, "domain_controller": None},
        "verbose": 0,
        "logging": {"enable": False, "enable_loggers": []},
        "dir_browser": {"enable": True},
        "lock_storage": False,
        "property_manager": False,
    })
