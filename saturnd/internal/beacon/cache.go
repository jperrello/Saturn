package beacon

import (
	"sort"
	"sync"
	"time"
)

type Credential struct {
	APIKey     string
	Provider   string
	Priority   int
	BaseURL    string
	ExpiresAt  time.Time
	LastSeen   time.Time
}

type Cache struct {
	credentials map[string]Credential
	mu          sync.RWMutex
}

func NewCache() *Cache {
	return &Cache{
		credentials: make(map[string]Credential),
	}
}

func (c *Cache) Update(name string, cred Credential) {
	c.mu.Lock()
	defer c.mu.Unlock()

	cred.LastSeen = time.Now()

	// Set BaseURL based on provider if not already set
	if cred.BaseURL == "" {
		switch cred.Provider {
		case "DeepInfra":
			cred.BaseURL = "https://api.deepinfra.com/v1/openai"
		case "OpenRouter":
			cred.BaseURL = "https://openrouter.ai/api/v1"
		}
	}

	c.credentials[name] = cred
}

func (c *Cache) Get(name string) (Credential, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	cred, ok := c.credentials[name]
	return cred, ok
}

func (c *Cache) GetBestCredential() (Credential, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	if len(c.credentials) == 0 {
		return Credential{}, false
	}

	// Sort by priority (lower is better)
	type namedCred struct {
		name string
		cred Credential
	}

	var creds []namedCred
	for name, cred := range c.credentials {
		// Skip expired credentials
		if !cred.ExpiresAt.IsZero() && time.Now().After(cred.ExpiresAt) {
			continue
		}
		creds = append(creds, namedCred{name, cred})
	}

	if len(creds) == 0 {
		return Credential{}, false
	}

	sort.Slice(creds, func(i, j int) bool {
		return creds[i].cred.Priority < creds[j].cred.Priority
	})

	return creds[0].cred, true
}

func (c *Cache) GetAll() map[string]Credential {
	c.mu.RLock()
	defer c.mu.RUnlock()

	result := make(map[string]Credential, len(c.credentials))
	for k, v := range c.credentials {
		result[k] = v
	}
	return result
}

func (c *Cache) Remove(name string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.credentials, name)
}

func (c *Cache) Cleanup(maxAge time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()

	now := time.Now()
	for name, cred := range c.credentials {
		if now.Sub(cred.LastSeen) > maxAge {
			delete(c.credentials, name)
		}
	}
}

func (c *Cache) GetByProvider(provider string) (Credential, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	for _, cred := range c.credentials {
		if cred.Provider == provider {
			if !cred.ExpiresAt.IsZero() && time.Now().After(cred.ExpiresAt) {
				continue
			}
			return cred, true
		}
	}
	return Credential{}, false
}
