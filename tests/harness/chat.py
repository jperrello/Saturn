import json
import urllib.request


def send(endpoint, model, messages, token=None, **kwargs):
    body = {"model": model, "messages": messages, "stream": False, **kwargs}
    headers = {"content-type": "application/json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{endpoint.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def reply(endpoint, model, prompt, token=None, **kwargs):
    r = send(endpoint, model, [{"role": "user", "content": prompt}],
             token=token, **kwargs)
    return r["choices"][0]["message"]["content"], r.get("usage", {}), r


def health(endpoint, token=None):
    headers = {}
    if token: headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{endpoint.rstrip('/')}/v1/health",
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.load(r)
