package beacon

import "time"

type CredentialResponse struct {
	OPENAI_API_KEY  string `json:"OPENAI_API_KEY"`
	OPENAI_BASE_URL string `json:"OPENAI_BASE_URL"`
	Provider        string `json:"provider"`
	ExpiresIn       int    `json:"expires_in,omitempty"`
}

var providerBaseURLs = map[string]string{
	"DeepInfra":   "https://api.deepinfra.com/v1/openai",
	"OpenRouter":  "https://openrouter.ai/api/v1",
	"OpenAI":      "https://api.openai.com/v1",
	"Anthropic":   "https://api.anthropic.com/v1",
	"Together":    "https://api.together.xyz/v1",
	"Groq":        "https://api.groq.com/openai/v1",
	"Fireworks":   "https://api.fireworks.ai/inference/v1",
	"Perplexity":  "https://api.perplexity.ai",
	"Mistral":     "https://api.mistral.ai/v1",
	"Cohere":      "https://api.cohere.ai/v1",
}

func ProviderBaseURL(provider string) string {
	if url, ok := providerBaseURLs[provider]; ok {
		return url
	}
	return ""
}

func SupportedProviders() []string {
	providers := make([]string, 0, len(providerBaseURLs))
	for p := range providerBaseURLs {
		providers = append(providers, p)
	}
	return providers
}

func (c *Cache) GetCredentialResponse() (CredentialResponse, bool) {
	cred, ok := c.GetBestCredential()
	if !ok {
		return CredentialResponse{}, false
	}
	return credentialToResponse(cred), true
}

func (c *Cache) GetCredentialResponseByProvider(provider string) (CredentialResponse, bool) {
	cred, ok := c.GetByProvider(provider)
	if !ok {
		return CredentialResponse{}, false
	}
	return credentialToResponse(cred), true
}

func credentialToResponse(cred Credential) CredentialResponse {
	expiresIn := 0
	if !cred.ExpiresAt.IsZero() {
		expiresIn = int(time.Until(cred.ExpiresAt).Seconds())
		if expiresIn < 0 {
			expiresIn = 0
		}
	}

	return CredentialResponse{
		OPENAI_API_KEY:  cred.APIKey,
		OPENAI_BASE_URL: cred.BaseURL,
		Provider:        cred.Provider,
		ExpiresIn:       expiresIn,
	}
}
