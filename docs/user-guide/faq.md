# FAQ

## Can I use Saturn without internet?

Yes. With local models (Ollama), everything runs on your machine. Saturn discovery is entirely local network — no internet required.

## Is my data private?

For local services, prompts never leave the LAN. For cloud services (OpenRouter, DeepInfra), data is sent to the cloud provider. The administrator controls which services are available.

## How does Saturn pick which service to use?

Priority routing. Each service has a priority number — lower number means preferred. If the preferred service is down, Saturn automatically fails over to the next one.

## Does it cost money?

Saturn itself is free. Cloud AI services (OpenRouter, DeepInfra) require the administrator to have API keys and may incur costs. Local models via Ollama are free.

## Can multiple people use it at once?

Yes. Rate limiting prevents any single user from monopolizing the service. Limits are configurable per IP address.

## What models are available?

Whatever the administrator has configured. Could be local Ollama models, cloud models via OpenRouter or DeepInfra, or both.

## Do I need to install anything?

For the Web UI, no — just open a browser. For CLI or Python usage, install with `pip install saturn-ai`.

## What if the AI gives bad responses?

Try a different model if one is available. You can also adjust the response style or check whether you are hitting a fallback service instead of the preferred one.
