import time
import logging
from datetime import datetime, timezone, timedelta

import requests

logger = logging.getLogger(__name__)

endpoint = "https://openrouter.ai/api/v1/keys"
api_base = "https://openrouter.ai/api/v1"

def payload(expiration, max_budget_usd=None):
    expires = datetime.now(timezone.utc) + timedelta(seconds=expiration)
    body = {
        "name": f"saturn-beacon-{int(time.time())}",
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if max_budget_usd is not None:
        body["limit"] = max_budget_usd
    return body

def parse(data):
    return data["key"], data["data"]["hash"]

def revoke(api_key, endpoint, handle):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        r = requests.delete(f"{endpoint}/{handle}", headers=headers)
        if r.status_code in (200, 404):
            logger.info(f"Deleted key: {handle[:8]}...")
        else:
            logger.warning(f"Failed to delete key {handle[:8]}...: {r.status_code}")
    except Exception as e:
        logger.error(f"Error deleting key: {e}")
