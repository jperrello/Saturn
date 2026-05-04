# Open WebUI

[Open WebUI](https://github.com/open-webui/open-webui) is a web-based chat interface for LLMs. Saturn endpoints expose OpenAI-compatible HTTP, so Open WebUI connects directly with no Saturn-specific code.

## Get a URL

```bash
$ dns-sd -B _saturn._tcp .local            # macOS / Bonjour
$ avahi-browse -rtp _saturn._tcp           # Linux / Avahi
$ saturn endpoint                          # Python helper — picks highest-priority
http://macbook.local:11434
```

Paste the result into the connection form below.

## Setup

1. Get the Saturn endpoint URL:

    ```bash
    saturn endpoint
    ```

2. In Open WebUI, go to **Settings → Connections** and add a new OpenAI-compatible connection pointing at the returned URL.

3. Models from the Saturn service will appear in the model selector.

## Helper script

The Saturn repository includes `owui_saturn.py`, a helper script that automates the connection setup between Open WebUI and Saturn services.
