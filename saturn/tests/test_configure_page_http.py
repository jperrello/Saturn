"""Saturn-hft v2 — Configure page render via HTTP+HTML (no browser).

Per CONTRACT_v2.md. Asserts the server renders the admin Configure view's required
shape without driving a headless browser. urllib.request → parse response body with
html.parser. Same five invariants as v1, expressed in DOM string form.
"""

import html.parser
import json
import os
import re
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request

import pytest

from .conftest_b3 import _free, _ping, MIN_PASSWORD


pytestmark = pytest.mark.timeout(60)


GROUP_KEYWORDS = [
    ["model filter", "budget", "general"],          # A.1 existing
    ["auth", "token", "session"],                   # A.2 authentication
    ["network", "bind", "tls", "cors"],             # A.3 network posture
    ["rate", "limit", "throughput"],                # A.4 rate limits
    ["endpoint", "public", "route"],                # A.5 endpoint policy
    ["proxy", "redact"],                            # A.6 proxy hygiene
    ["mcp"],                                        # A.7 MCP
    ["identity", "trust", "node"],                  # A.8 service identity
]


@pytest.fixture
def saturn_web(tmp_path):
    port = _free()
    token = "brutus-hft-v2-" + secrets.token_urlsafe(16)
    runner_tok = "brutus-runner-" + secrets.token_urlsafe(16)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "SATURN_ADMIN_TOKEN":    token,
        "SATURN_RUNNER_TOKEN":   runner_tok,
        "SATURN_ADMIN_PASSWORD": MIN_PASSWORD,
        "SATURN_DATA_DIR":       str(tmp_path / "data"),
        "SATURN_SERVICES_DIR":   str(tmp_path / "services"),
        "SATURN_BIND_HOST":      "127.0.0.1",
    }
    log = open(tmp_path / "saturn-web.log", "wb")
    proc = subprocess.Popen(
        ["python3", "-m", "saturn", "web", "--port", str(port)],
        env=env, stdout=log, stderr=log,
    )
    origin = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline and not _ping(origin):
        if proc.poll() is not None:
            log.close()
            pytest.fail(f"saturn web exited; tail:\n{(tmp_path / 'saturn-web.log').read_text()[-1500:]}")
        time.sleep(0.3)
    if not _ping(origin):
        proc.terminate()
        pytest.fail("saturn web never came up")
    try:
        yield {"origin": origin, "token": token}
    finally:
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill()


def _admin(token):
    return {"Authorization": f"Bearer {token}"}


def _get_text(origin, path, token):
    req = urllib.request.Request(f"{origin}{path}", headers=_admin(token), method="GET")
    return urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "replace")


def _get_json(origin, path, token):
    return json.loads(_get_text(origin, path, token))


def _post_json(origin, path, body, token):
    req = urllib.request.Request(
        f"{origin}{path}",
        data=json.dumps(body).encode(),
        headers={**_admin(token), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        return urllib.request.urlopen(req, timeout=10).getcode()
    except urllib.error.HTTPError as e:
        return e.code


# --- Tiny HTML inspector: collect <section>/<fieldset> with their inner text snippet,
#     and form fields (input/select/textarea) with id + current `value`/`name`. ---

class _Probe(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.sections = []        # list[dict(tag=..., heading_text=..., body_text=...)]
        self.fields   = []        # list[dict(tag, id, name, type, value, label_text)]
        self._stack = []          # current open tags (tag, attrs_dict)
        self._section_buf = None  # list of strings being collected for the current section
        self._heading_buf = None  # similar for legend/h2/h3 inside the current section
        self._label_buf = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._stack.append((tag, a))
        if tag in ("section", "fieldset"):
            self._section_buf = []
            self._heading_buf = []
            self._cur_section = {"tag": tag, "attrs": a, "heading_text": "", "body_text": ""}
        if tag in ("legend", "h1", "h2", "h3", "h4") and self._heading_buf is not None:
            # mark we're in a heading: keep buf; data goes here too
            pass
        if tag in ("input", "select", "textarea"):
            self.fields.append({
                "tag": tag,
                "id": a.get("id", ""),
                "name": a.get("name", ""),
                "type": a.get("type", ""),
                "value": a.get("value", ""),
                "label_text": "",
            })
        if tag == "label":
            self._label_buf = []

    def handle_endtag(self, tag):
        if tag in ("section", "fieldset") and getattr(self, "_cur_section", None):
            self._cur_section["heading_text"] = " ".join(self._heading_buf or []).strip()
            self._cur_section["body_text"]    = " ".join(self._section_buf or []).strip()
            self.sections.append(self._cur_section)
            self._cur_section = None
            self._section_buf = None
            self._heading_buf = None
        if tag == "label" and self._label_buf is not None:
            label_text = " ".join(self._label_buf).strip()
            # stamp the most recent field if it sits under this label
            if self.fields:
                self.fields[-1]["label_text"] = (self.fields[-1]["label_text"] + " " + label_text).strip()
            self._label_buf = None
        # Pop stack
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                self._stack.pop(i); break

    def handle_data(self, data):
        if self._section_buf is not None:
            self._section_buf.append(data)
        if self._heading_buf is not None:
            # heading buf only collects when we're inside a heading element
            for t, _ in self._stack:
                if t in ("legend", "h1", "h2", "h3", "h4"):
                    self._heading_buf.append(data)
                    break
        if self._label_buf is not None:
            self._label_buf.append(data)


def _parse(text):
    p = _Probe()
    p.feed(text)
    return p


# --- (a) 8 group sections render in HTML ---

# One admin-schema field id per CONFIG_FIELDS §A.1-A.8 group. The implementer can pick
# their own id-naming convention; this list accepts any of several common shapes
# (config-X, admin-X, admin_X, X) so the contract isn't over-specified.
GROUP_FIELD_PROBES = [
    # A.1 existing                 — model_filter
    [r"\bmodel[-_]?filter\b"],
    # A.2 authentication           — admin_token_env / runner_token_env / admin_session_ttl_s
    [r"admin[-_]?token[-_]?env", r"runner[-_]?token[-_]?env", r"admin[-_]?session[-_]?ttl"],
    # A.3 network posture          — bind_host / trusted_proxies / cors_origins / tls_cert_path
    [r"\bbind[-_]?host\b", r"trusted[-_]?proxies", r"cors[-_]?origins", r"tls[-_]?cert"],
    # A.4 rate limits              — rate_rpm / rate_tpm
    [r"rate[-_]?rpm", r"rate[-_]?tpm"],
    # A.5 endpoint policy          — public_routes / require_auth_on_v1
    [r"public[-_]?routes", r"require[-_]?auth[-_]?on[-_]?v1"],
    # A.6 proxy hygiene            — proxy_models_method / redact_proxy_keys_in_logs
    [r"proxy[-_]?models[-_]?method", r"redact[-_]?proxy[-_]?keys"],
    # A.7 MCP                      — mcp_allowed_urls
    [r"mcp[-_]?allowed[-_]?urls", r"mcp[-_]?auth[-_]?token"],
    # A.8 service identity         — trust_mode / trusted_node_ids
    [r"trust[-_]?mode", r"trusted[-_]?node[-_]?ids"],
]


def test_admin_configure_renders_eight_groups(saturn_web):
    text = _get_text(saturn_web["origin"], "/admin/configure", saturn_web["token"])

    # Inspect every form-field id/name that appears in the response.
    p = _parse(text)
    field_haystack = " ".join(
        (f.get("id", "") + " " + f.get("name", "") + " " + f.get("label_text", "")).lower()
        for f in p.fields
    )
    # Also include rendered text so a legend/heading-only group still scores once a field arrives.
    field_haystack += " " + " ".join((s.get("heading_text") or "") for s in p.sections).lower()

    missing = []
    for i, probes in enumerate(GROUP_FIELD_PROBES):
        if not any(re.search(rx, field_haystack) for rx in probes):
            missing.append(f"A.{i+1}")
    assert not missing, (
        f"GET /admin/configure does not render an admin-schema field for CONFIG_FIELDS group(s) "
        f"{missing!r}. The view must include at least one admin field per group A.1-A.8 "
        f"(probes: {[GROUP_FIELD_PROBES[int(g[2:])-1] for g in missing]}). "
        f"This rules out the SPA index.html fallback — the legacy per-service form's "
        f"`cfg-*` ids do not match these admin-schema patterns."
    )


# --- (b) form field ids populate current AdminConfig values ---

def test_section_values_populate_current_config(saturn_web):
    """Seed rate_rpm=137 via API, GET /admin/configure, find an input whose current value is '137'
    AND whose id/name/label mentions rate_rpm."""
    code = _post_json(saturn_web["origin"], "/api/admin/config", {"rate_rpm": 137}, saturn_web["token"])
    assert code == 200
    text = _get_text(saturn_web["origin"], "/admin/configure", saturn_web["token"])
    p = _parse(text)

    found = None
    for f in p.fields:
        ctx = (f.get("id", "") + " " + f.get("name", "") + " " + f.get("label_text", "")).lower()
        if str(f.get("value", "")).strip() == "137" and re.search(r"rate.?rpm|requests.*minute|\brpm\b", ctx):
            found = f
            break
    assert found is not None, (
        "no form field renders rate_rpm=137 in its `value` attribute. The server must inline the "
        "current AdminConfig values into the rendered HTML so the page reads as 'configured' "
        "without an extra fetch round-trip."
    )


# --- (c) POST round-trips ---

def test_post_admin_config_roundtrips(saturn_web):
    target = 271
    code = _post_json(saturn_web["origin"], "/api/admin/config",
                      {"rate_rpm": target}, saturn_web["token"])
    assert code == 200, f"POST returned {code}"
    after = _get_json(saturn_web["origin"], "/api/admin/config", saturn_web["token"])
    assert after.get("rate_rpm") == target, (
        f"POST /api/admin/config did not round-trip rate_rpm={target}; GET returned {after.get('rate_rpm')!r}"
    )


# --- (d) api_key inputs are env-var NAMES only, never plaintext ---

def test_api_key_inputs_are_env_var_names_only(saturn_web):
    """Across the rendered admin Configure page, every input/select whose id|name|label_text
    matches /api[-_]?key/ MUST also match /api[-_]?key[-_]?env|env[-_]?var/. No raw key inputs."""
    text = _get_text(saturn_web["origin"], "/admin/configure", saturn_web["token"])
    p = _parse(text)
    bad = []
    for f in p.fields:
        ctx = (f.get("id", "") + " " + f.get("name", "") + " " + f.get("label_text", "")).lower()
        if re.search(r"api[-_\s]?key", ctx) and not re.search(r"api[-_\s]?key[-_\s]?env|env[-_\s]?var", ctx):
            bad.append({"id": f.get("id"), "name": f.get("name"),
                        "label": f.get("label_text", "").strip()[:80]})
    assert not bad, (
        f"raw api_key input(s) on admin Configure page: {bad!r}. "
        f"Saturn invariant (saturn/web.py:1213): configs hold env-var NAMES, not values. "
        f"Label/id/name must say api_key_env or 'env var name', not 'api key'."
    )


# --- (e) qj5.2 chat-tab Settings popup separation regression guard ---

def test_chat_index_html_does_not_carry_admin_schema_ids(saturn_web):
    """The shipped chat tab (Web-UI/index.html served at /) must NOT carry server-wide
    admin schema input ids. qj5.2's per-chat popup is for response-style + model override
    + current service ONLY. This is a structural guard against the eight admin fields
    leaking into the chat surface during a future refactor."""
    text = _get_text(saturn_web["origin"], "/", saturn_web["token"])
    leaks = []
    forbidden_ids = [
        "config-rate-rpm", "config-rate_rpm", "config-rate-tpm", "config-rate_tpm",
        "config-trusted-proxies", "config-trusted_proxies",
        "config-cors-origins", "config-cors_origins",
        "config-admin-token-env", "config-admin_token_env",
        "config-public-routes", "config-public_routes",
        "config-tls-cert-path", "config-tls_cert_path",
        "config-mcp-allowed-urls", "config-mcp_allowed_urls",
    ]
    for fid in forbidden_ids:
        if f'id="{fid}"' in text or f"id='{fid}'" in text:
            leaks.append(fid)
    assert not leaks, (
        f"chat index.html carries admin-schema input ids: {leaks!r}. "
        f"qj5.2 popup must remain scoped to per-chat controls."
    )


# --- (f) qj5.13.7: /admin/configure must require admin auth ---

def test_admin_configure_requires_auth(saturn_web):
    """GET /admin/configure WITHOUT Authorization → 401. Saturn-6sb regression
    (commit b38b4af) ungated this route; SSR pre-fill bakes admin posture
    (trusted_proxies CIDRs, cors_origins, rate_*, admin_token_env, etc.) into
    HTML, so the response must require the admin token even though no secret
    VALUES traverse this path."""
    origin = saturn_web["origin"]
    for path in ("/admin/configure", "/configure", "/admin/services"):
        req = urllib.request.Request(f"{origin}{path}", method="GET")
        try:
            urllib.request.urlopen(req, timeout=5).read()
            pytest.fail(f"{path} returned 200 with no Authorization header — admin posture leak")
        except urllib.error.HTTPError as e:
            assert e.code == 401, (
                f"{path} no-auth must return 401 (got {e.code}). qj5.13.7: route must "
                f"require admin token before SSR pre-fill renders trusted_proxies / cors_origins / "
                f"rate_rpm / *_token_env into the HTML."
            )
        # With token: 200
        req = urllib.request.Request(
            f"{origin}{path}",
            headers={"Authorization": f"Bearer {saturn_web['token']}"},
            method="GET",
        )
        resp = urllib.request.urlopen(req, timeout=5)
        assert resp.getcode() == 200, f"{path} with admin token must return 200 (got {resp.getcode()})"
