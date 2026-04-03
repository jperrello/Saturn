# Open WebUI

[Open WebUI](https://github.com/open-webui/open-webui) is a web-based chat interface for LLMs. Saturn endpoints are OpenAI-compatible, so Open WebUI can connect directly.

## Setup

1. Get the Saturn endpoint URL:

    ```bash
    saturn endpoint
    ```

2. In Open WebUI, go to **Settings → Connections** and add a new OpenAI-compatible connection pointing at the returned URL.

3. Models from the Saturn service will appear in the model selector.

## Helper script

The Saturn repository includes `owui_saturn.py`, a helper script that automates the connection setup between Open WebUI and Saturn services.
