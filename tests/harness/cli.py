import argparse
import json
import sys

from . import chat, ollama, openrouter, service


def _print(obj):
    print(json.dumps(obj, default=str, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser("saturn-harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    s_install = sub.add_parser("install")
    s_install.add_argument("name")
    s_install.add_argument("--priority", type=int, default=50)
    s_install.add_argument("--api-type", default="ollama")
    s_install.add_argument("--upstream", default="http://localhost:11434/v1")

    s_edit = sub.add_parser("edit")
    s_edit.add_argument("name")
    s_edit.add_argument("--priority", type=int)
    s_edit.add_argument("--upstream")

    sub.add_parser("delete").add_argument("name")
    sub.add_parser("start").add_argument("name")
    sub.add_parser("stop").add_argument("name")
    sub.add_parser("discover")
    sub.add_parser("endpoint")

    s_chat = sub.add_parser("chat")
    s_chat.add_argument("--endpoint", required=True)
    s_chat.add_argument("--model", required=True)
    s_chat.add_argument("--prompt", required=True)
    s_chat.add_argument("--max-tokens", type=int, default=64)
    s_chat.add_argument("--temperature", type=float, default=None)

    s_or = sub.add_parser("openrouter")
    s_or_sub = s_or.add_subparsers(dest="op", required=True)
    s_or_sub.add_parser("list")
    s_or_create = s_or_sub.add_parser("create")
    s_or_create.add_argument("name")
    s_or_create.add_argument("--limit", type=float, default=0.10)
    s_or_sub.add_parser("revoke").add_argument("hash")

    s_oll = sub.add_parser("ollama")
    s_oll_sub = s_oll.add_subparsers(dest="op", required=True)
    s_oll_sub.add_parser("ensure").add_argument("--model", default=ollama.DEFAULT)

    a = p.parse_args(argv)

    if a.cmd == "install":
        path = service.install(a.name, priority=a.priority, api_type=a.api_type,
                               upstream={"base_url": a.upstream})
        return _print({"installed": str(path)})
    if a.cmd == "edit":
        fields = {k: v for k, v in vars(a).items()
                  if k in ("priority",) and v is not None}
        if a.upstream: fields["upstream"] = {"base_url": a.upstream}
        return _print({"edited": str(service.edit(a.name, **fields))})
    if a.cmd == "delete":
        service.delete(a.name); return _print({"deleted": a.name})
    if a.cmd == "start":
        return _print(service.start(a.name))
    if a.cmd == "stop":
        service.stop(a.name); return _print({"stopped": a.name})
    if a.cmd == "discover":
        return _print(service.discover())
    if a.cmd == "endpoint":
        return _print({"endpoint": service.endpoint()})
    if a.cmd == "chat":
        kwargs = {"max_tokens": a.max_tokens}
        if a.temperature is not None: kwargs["temperature"] = a.temperature
        text, usage, _ = chat.reply(a.endpoint, a.model, a.prompt, **kwargs)
        return _print({"reply": text, "usage": usage})
    if a.cmd == "openrouter":
        if a.op == "list": return _print(openrouter.list())
        if a.op == "create": return _print(openrouter.create(a.name, limit=a.limit))
        if a.op == "revoke": return _print(openrouter.revoke(a.hash))
    if a.cmd == "ollama":
        if a.op == "ensure": return _print({"model": ollama.ensure(a.model)})


if __name__ == "__main__":
    sys.exit(main() or 0)
