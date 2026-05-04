import json
import urllib.request


def send(endpoint, model, messages, **kwargs):
    body = {"model": model, "messages": messages, "stream": False, **kwargs}
    req = urllib.request.Request(
        f"{endpoint.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def reply(endpoint, model, prompt, **kwargs):
    r = send(endpoint, model, [{"role": "user", "content": prompt}], **kwargs)
    return r["choices"][0]["message"]["content"], r.get("usage", {}), r
