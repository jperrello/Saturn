# Jan

[Jan](https://jan.ai) is a local-first AI client. Saturn services appear as OpenAI-compatible endpoints, so Jan can connect without any Saturn-specific configuration.

## Setup

1. Get the Saturn endpoint URL:

    ```bash
    saturn endpoint
    ```

2. In Jan, go to **Settings → Model Providers → OpenAI** (or add a new OpenAI-compatible provider).

3. Set the **API Base URL** to the endpoint returned by `saturn endpoint`.

4. Set the **API Key** to `saturn` (for local services) or the ephemeral key shown by `saturn endpoint` (for beacon services).

5. Models available on the Saturn network will appear in Jan's model selector.
