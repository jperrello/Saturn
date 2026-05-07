import argparse
import logging
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)


def build(share=False, root=None):
    from fastapi import FastAPI
    from starlette.responses import PlainTextResponse

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/")
    def home():
        return {"saturn": True, "share_claude": bool(share)}

    if not share:
        return app

    share_root = Path(root).expanduser().resolve()
    share_root.mkdir(parents=True, exist_ok=True)

    writes = {"PUT", "DELETE", "MKCOL", "MOVE", "COPY", "PROPPATCH", "POST", "PATCH", "LOCK", "UNLOCK"}

    @app.middleware("http")
    async def guard(request, call_next):
        decoded = urllib.parse.unquote(urllib.parse.unquote(request.url.path))
        if "/share/claude" in decoded:
            if request.method.upper() in writes:
                return PlainTextResponse("forbidden", status_code=403)
            tail = decoded.split("/share/claude/", 1)[-1] if "/share/claude/" in decoded else ""
            if ".." in tail.split("/"):
                return PlainTextResponse("forbidden", status_code=403)
        return await call_next(request)

    from a2wsgi import WSGIMiddleware
    from .dav import make_app

    dav = make_app(share_root)
    app.mount("/share/claude", WSGIMiddleware(dav))
    return app


def serve(host, port, share=False, root=None, name=None):
    import uvicorn
    from .discovery import SaturnAdvertiser

    app = build(share=share, root=root)
    advertiser_name = name or f"saturn-serve-{port}"
    adv = SaturnAdvertiser(name=advertiser_name, port=port, kind=("claude" if share else "openai"))
    try:
        adv.register()
    except Exception as e:
        logger.warning(f"mDNS register failed: {e}")

    if share:
        logger.info(f"saturn serve: share-claude=ON path={Path(root).expanduser().resolve()}")
    else:
        logger.info("saturn serve: share-claude=OFF")

    try:
        uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)
    finally:
        try:
            adv.unregister()
        except Exception:
            pass


def main(argv=None):
    p = argparse.ArgumentParser(prog="saturn serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--share-claude", action="store_true", dest="share")
    p.add_argument("--share-claude-path", default=str(Path.home() / ".claude"), dest="root")
    p.add_argument("--name", default=None)
    args = p.parse_args(argv)
    serve(args.host, args.port, share=args.share, root=args.root, name=args.name)
    return 0
