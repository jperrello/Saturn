# Jan

[Jan](https://jan.ai) is a local-first AI client. Saturn services expose OpenAI-compatible endpoints, so Jan can connect without any Saturn-specific code or library — point it at a discovered URL and you're done.

## Get a URL

```bash
$ dns-sd -B _saturn._tcp .local            # macOS / Bonjour
$ avahi-browse -rtp _saturn._tcp           # Linux / Avahi
$ saturn endpoint                          # Python helper — picks highest-priority
http://macbook.local:11434
```

Any of the above works. The result is what you paste into Jan.

## Setup

1. Get the Saturn endpoint URL:

    ```bash
    saturn endpoint
    ```

2. In Jan, go to **Settings → Model Providers → OpenAI** (or add a new OpenAI-compatible provider).

3. Set the **API Base URL** to the endpoint returned by `saturn endpoint`.

4. Set the **API Key** to `saturn` (for local services) or the ephemeral key shown by `saturn endpoint` (for beacon services).

5. Models available on the Saturn network will appear in Jan's model selector.
