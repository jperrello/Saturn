package providers

import "time"

type Credential struct {
	Key       string
	BaseURL   string
	ExpiresAt time.Time
}

type Provider interface {
	Name() string
	Enabled() bool
	GenerateCredential() (Credential, error)
	RotationInterval() time.Duration
	TXTRecords() map[string]string
}

type Config struct {
	APIKey           string
	Priority         int
	RotationSeconds  int
	ExpiresSeconds   int
	Enabled          bool
}

func DefaultConfig() Config {
	return Config{
		Priority:        10,
		RotationSeconds: 300,
		ExpiresSeconds:  600,
		Enabled:         true,
	}
}
