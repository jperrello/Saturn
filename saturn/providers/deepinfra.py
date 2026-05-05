import logging

import requests

logger = logging.getLogger(__name__)

endpoint = "https://api.deepinfra.com/v1/scoped-jwt"
api_base = "https://api.deepinfra.com/v1/openai"


def payload(expiration, max_budget_usd=None):
    body = {"api_key_name": "auto", "expires_delta": expiration}
    if max_budget_usd is not None:
        body["max_budget_usd"] = max_budget_usd
    return body


def parse(data):
    return data["token"], data.get("token")


def revoke(api_key, endpoint, handle):
    if not handle:
        return
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        r = requests.delete(f"{endpoint}/{handle}", headers=headers, timeout=10)
        if r.status_code in (200, 204, 404):
            logger.info(f"Revoked deepinfra scoped JWT")
        else:
            logger.warning(f"Failed to revoke deepinfra scoped JWT: {r.status_code}")
    except Exception as e:
        logger.error(f"Error revoking deepinfra scoped JWT: {e}")
