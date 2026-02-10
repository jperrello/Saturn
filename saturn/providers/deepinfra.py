endpoint = "https://api.deepinfra.com/v1/scoped-jwt"
api_base = "https://api.deepinfra.com/v1/openai"

def payload(expiration):
    return {"api_key_name": "auto", "expires_delta": expiration}

def parse(data):
    return data["token"], None

def revoke(api_key, endpoint, handle):
    pass
