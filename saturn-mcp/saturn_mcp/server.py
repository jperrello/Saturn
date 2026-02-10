from dataclasses import asdict
from typing import Optional
import asyncio
import logging
import sys
import httpx

from mcp.server.fastmcp import FastMCP
from saturn.discovery import discover, SaturnService, select_best_service

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("saturn-mcp")

mcp = FastMCP("saturn")


async def _async_discover(timeout: float = 5.0, settle_time: float = 1.0) -> list[SaturnService]:
    return await asyncio.to_thread(discover, timeout, settle_time)


def service_to_dict(service: SaturnService) -> dict:
    data = asdict(service)
    data["endpoint"] = service.endpoint
    data["effective_endpoint"] = service.effective_endpoint
    data["is_beacon"] = service.is_beacon
    data["is_cloud"] = service.is_cloud
    data["is_network"] = service.is_network
    return data


@mcp.tool()
async def discover_saturn_services(timeout: float = 5.0, settle_time: float = 1.0) -> list[dict]:
    """Discover Saturn AI services on the local network via mDNS.

    Returns a list of services with their metadata including:
    - name, host, port
    - models available
    - capabilities (chat, code, vision, etc.)
    - api_type (openai or ollama)
    - deployment type (cloud beacon or network)
    - priority (lower = preferred)

    Args:
        timeout: Maximum time to wait for discovery (seconds)
        settle_time: Wait for network to settle after last discovery (seconds)
    """
    logger.info(f"Discovering Saturn services (timeout={timeout}s)")
    services = await _async_discover(timeout=timeout, settle_time=settle_time)
    logger.info(f"Found {len(services)} services")
    return [service_to_dict(s) for s in services]


@mcp.tool()
async def list_available_models(service_name: Optional[str] = None) -> dict:
    """List all AI models available across Saturn services.

    Args:
        service_name: Optional - filter to models from a specific service

    Returns a dict mapping service names to their available models.
    """
    services = await _async_discover(timeout=5.0, settle_time=1.0)

    if service_name:
        services = [s for s in services if service_name.lower() in s.name.lower()]

    result = {}
    for service in services:
        endpoint = service.effective_endpoint
        models_url = f"{endpoint.rstrip('/')}/models"
        
        headers = {}
        if service.is_beacon and service.ephemeral_key:
            headers["Authorization"] = f"Bearer {service.ephemeral_key}"
        
        fetched_models = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(models_url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    model_list = data.get("data", [])
                    fetched_models = [m.get("id") for m in model_list if m.get("id")]
        except Exception as e:
            logger.warning(f"Failed to fetch models from {service.name}: {e}")
            fetched_models = service.models or []
        
        if not fetched_models:
            fetched_models = service.models or []
        
        if fetched_models:
            result[service.name] = {
                "models": fetched_models,
                "api_type": service.api_type,
                "endpoint": endpoint,
                "is_beacon": service.is_beacon,
            }

    return result


@mcp.tool()
async def find_service_for_model(model: str) -> Optional[dict]:
    """Find the best Saturn service that offers a specific model.

    Args:
        model: The model name to search for (e.g., "llama3.2", "gpt-4")

    Returns service details if found, None otherwise.
    """
    services = await _async_discover(timeout=5.0, settle_time=1.0)

    matching = [s for s in services if s.has_model(model)]
    if not matching:
        return None

    best = select_best_service(matching)
    return service_to_dict(best) if best else None


@mcp.tool()
async def find_service_with_capabilities(capabilities: list[str]) -> Optional[dict]:
    """Find the best Saturn service that has all requested capabilities.

    Args:
        capabilities: List of required capabilities (e.g., ["chat", "vision"])

    Returns service details if found, None otherwise.
    """
    services = await _async_discover(timeout=5.0, settle_time=1.0)

    matching = [s for s in services if s.has_all_capabilities(capabilities)]
    if not matching:
        return None

    best = select_best_service(matching)
    return service_to_dict(best) if best else None


@mcp.tool()
async def chat_completion(
    prompt: str,
    model: Optional[str] = None,
    service_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> str | dict:
    """Send a chat completion request to a Saturn service.

    Args:
        prompt: The user message to send
        model: Optional model to use (will use service default if not specified)
        service_name: Optional specific service to use (will auto-select if not specified)
        system_prompt: Optional system prompt to set context

    Returns the completion response or error details.
    """
    services = await _async_discover(timeout=5.0, settle_time=1.0)

    if not services:
        return {"error": "No Saturn services found on the network"}

    target_service = None
    if service_name:
        for s in services:
            if service_name.lower() in s.name.lower():
                target_service = s
                break
        if not target_service:
            return {"error": f"Service '{service_name}' not found"}
    elif model:
        matching = [s for s in services if s.has_model(model)]
        if matching:
            target_service = select_best_service(matching)
        else:
            target_service = select_best_service(services)
    else:
        target_service = select_best_service(services)

    if not target_service:
        return {"error": "No suitable service found"}

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    use_model = model
    if not use_model and target_service.models:
        use_model = target_service.models[0]
    if not use_model:
        use_model = "default"

    endpoint = target_service.effective_endpoint
    url = f"{endpoint.rstrip('/')}/chat/completions"

    headers = {"Content-Type": "application/json"}
    if target_service.is_beacon and target_service.ephemeral_key:
        headers["Authorization"] = f"Bearer {target_service.ephemeral_key}"

    payload = {
        "model": use_model,
        "messages": messages,
    }

    logger.info(f"Sending chat completion to {target_service.name} ({url})")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                return {
                    "error": f"API error: {response.status_code}",
                    "details": response.text[:500],
                    "service": target_service.name,
                }
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        return {
            "error": str(e),
            "service": target_service.name,
        }


@mcp.tool()
async def get_service_details(service_name: str) -> Optional[dict]:
    """Get detailed information about a specific Saturn service.

    Args:
        service_name: Name or partial name of the service

    Returns full service details if found.
    """
    services = await _async_discover(timeout=5.0, settle_time=1.0)

    for service in services:
        if service_name.lower() in service.name.lower():
            return service_to_dict(service)

    return None


@mcp.resource("saturn://services")
def get_all_services() -> str:
    """Get all currently discoverable Saturn services as JSON."""
    import json
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(discover, 5.0, 1.0)
        services = future.result()
    return json.dumps([service_to_dict(s) for s in services], indent=2)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
