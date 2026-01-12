package providers

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"sync"
	"time"
)

const (
	deepInfraJWTEndpoint = "https://api.deepinfra.com/v1/scoped-jwt"
	deepInfraAPIBase     = "https://api.deepinfra.com/v1/openai"
)

type DeepInfraProvider struct {
	config Config

	mu            sync.RWMutex
	currentToken  string
	expiresAt     time.Time
	lastRotation  time.Time
}

func NewDeepInfraProvider(cfg Config) *DeepInfraProvider {
	if cfg.RotationSeconds <= 0 {
		cfg.RotationSeconds = 300
	}
	if cfg.ExpiresSeconds <= 0 {
		cfg.ExpiresSeconds = 600
	}
	return &DeepInfraProvider{config: cfg}
}

func (p *DeepInfraProvider) Name() string {
	return "DeepInfra"
}

func (p *DeepInfraProvider) Enabled() bool {
	return p.config.Enabled && p.config.APIKey != ""
}

func (p *DeepInfraProvider) RotationInterval() time.Duration {
	return time.Duration(p.config.RotationSeconds) * time.Second
}

func (p *DeepInfraProvider) GenerateCredential() (Credential, error) {
	if p.config.APIKey == "" {
		return Credential{}, errors.New("deepinfra: API key not configured")
	}

	payload := map[string]interface{}{
		"api_key_name":  "auto",
		"expires_delta": p.config.ExpiresSeconds,
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return Credential{}, fmt.Errorf("deepinfra: failed to marshal request: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, deepInfraJWTEndpoint, bytes.NewReader(body))
	if err != nil {
		return Credential{}, fmt.Errorf("deepinfra: failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+p.config.APIKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return Credential{}, fmt.Errorf("deepinfra: request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return Credential{}, fmt.Errorf("deepinfra: API returned status %d", resp.StatusCode)
	}

	var result struct {
		Token string `json:"token"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return Credential{}, fmt.Errorf("deepinfra: failed to decode response: %w", err)
	}

	if result.Token == "" {
		return Credential{}, errors.New("deepinfra: empty token in response")
	}

	expiresAt := time.Now().Add(time.Duration(p.config.ExpiresSeconds) * time.Second)

	p.mu.Lock()
	p.currentToken = result.Token
	p.expiresAt = expiresAt
	p.lastRotation = time.Now()
	p.mu.Unlock()

	return Credential{
		Key:       result.Token,
		BaseURL:   deepInfraAPIBase,
		ExpiresAt: expiresAt,
	}, nil
}

func (p *DeepInfraProvider) TXTRecords() map[string]string {
	p.mu.RLock()
	token := p.currentToken
	p.mu.RUnlock()

	return map[string]string{
		"version":           "1.0",
		"api":               "DeepInfra",
		"api_base":          deepInfraAPIBase,
		"priority":          strconv.Itoa(p.config.Priority),
		"ephemeral_key":     token,
		"rotation_interval": strconv.Itoa(p.config.RotationSeconds),
		"features":          "ephemeral_auth",
	}
}

func (p *DeepInfraProvider) NeedsRotation() bool {
	p.mu.RLock()
	defer p.mu.RUnlock()

	if p.lastRotation.IsZero() {
		return true
	}
	return time.Since(p.lastRotation) >= p.RotationInterval()
}

func (p *DeepInfraProvider) CurrentToken() string {
	p.mu.RLock()
	defer p.mu.RUnlock()
	return p.currentToken
}
