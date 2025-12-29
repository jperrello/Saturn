# DeepInfra Scoped JWT Research Findings

## API Endpoint
**URL**: `https://api.deepinfra.com/v1/scoped-jwt`
**Method**: POST
**Auth**: Bearer token (DEEPINFRA_API_KEY)

## Request Format
```json
{
  "api_key_name": "auto",
  "models": ["meta-llama/Meta-Llama-3.1-8B-Instruct"],
  "expires_delta": 300,
  "spending_limit": 1.0
}
```

### Parameters
- `api_key_name`: Set to "auto" for automatic naming
- `models`: Array of model identifiers that the JWT can access
- `expires_delta`: Token lifetime in seconds (300 = 5 minutes)
- `spending_limit`: Maximum spending allowed in USD (1.0 = $1.00)

## Response Format
```json
{
  "token": "jwt:eyJhbGciOiJIUzI1NiIsImtpZCI6ImdoOjk4NzE0MjExOllYVjBidz09IiwidHlwIjoiSldUIn0..."
}
```

## Token Characteristics

### Format
- **Prefix**: Always starts with `jwt:`
- **Structure**: Standard JWT format (header.payload.signature)
- **Total Length**: ~266 characters (varies slightly)
- **Length without prefix**: ~262 characters

### Critical for mDNS Implementation
**Token length is well under the 255-character limit for mDNS TXT records!**
- Full token with `jwt:` prefix fits in a single TXT record
- No need for chunking or special handling

### Token Validation
Token successfully tested with DeepInfra inference API:
- **Endpoint**: `https://api.deepinfra.com/v1/chat/completions`
- **Usage**: Same as regular API key - use in `Authorization: Bearer <token>` header
- **Scoping Works**: Token only grants access to models specified in creation request
  - Attempting to use non-scoped model returns: `{"detail":{"error":"model access denied"}}`
- **Successful Test**: `meta-llama/Meta-Llama-3.1-8B-Instruct` worked when included in scope

## Implementation Notes

### For BeaconAnnouncer
- Can safely include full JWT token in TXT record
- No length concerns for mDNS broadcasts
- Token should be refreshed before expiration (monitor `expires_delta`)

### For JWTManager
- Simple API call - single POST request
- Response contains ready-to-use token
- Token includes `jwt:` prefix - use as-is, no modification needed
- Model scoping is enforced server-side
- Spending limits are enforced server-side

### Security Characteristics
- Tokens are ephemeral (configurable expiration)
- Model access is restricted to specified models only
- Spending is capped at specified limit
- No access to account management or other API keys
- Ideal for broadcasting to untrusted clients on local network

## Recommended Parameters for Saturn Beacon
```json
{
  "api_key_name": "auto",
  "models": ["*"],  // Or specific model list
  "expires_delta": 600,  // 10 minutes (refresh at 8 minutes)
  "spending_limit": 5.0  // $5 per token
}
```

## References
- [DeepInfra Scoped JWT Documentation](https://deepinfra.com/docs/advanced/scoped_jwt)

## Date
2025-12-28
