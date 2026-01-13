package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/grandcat/zeroconf"
	"github.com/joeyperrello/saturn/saturnd/internal/providers"
)

const (
	ServiceType = "_saturn._tcp"
	Domain      = "local."
)

type BeaconConfig struct {
	Name     string         `json:"name"`
	Priority int            `json:"priority"`
	Provider ProviderConfig `json:"provider"`
}

type ProviderConfig struct {
	Type            string `json:"type"`
	APIKey          string `json:"api_key"`
	RotationSeconds int    `json:"rotation_seconds"`
	ExpiresSeconds  int    `json:"expires_seconds"`
}

func loadConfig(path string) (*BeaconConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read config: %w", err)
	}

	var cfg BeaconConfig
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config: %w", err)
	}

	if cfg.Priority == 0 {
		cfg.Priority = 10
	}
	if cfg.Provider.RotationSeconds == 0 {
		cfg.Provider.RotationSeconds = 300
	}
	if cfg.Provider.ExpiresSeconds == 0 {
		cfg.Provider.ExpiresSeconds = 600
	}
	if cfg.Name == "" {
		hostname, _ := os.Hostname()
		cfg.Name = hostname + "-beacon"
	}

	return &cfg, nil
}

func getLocalIP() string {
	addrs, err := net.InterfaceAddrs()
	if err != nil {
		return "127.0.0.1"
	}

	for _, addr := range addrs {
		if ipnet, ok := addr.(*net.IPNet); ok && !ipnet.IP.IsLoopback() {
			if ipnet.IP.To4() != nil {
				return ipnet.IP.String()
			}
		}
	}
	return "127.0.0.1"
}

func main() {
	configPath := flag.String("config", "/etc/saturn/beacon.json", "path to config file")
	envAPIKey := flag.String("api-key", "", "API key (overrides config, can also use DEEPINFRA_API_KEY env)")
	priority := flag.Int("priority", 0, "priority (overrides config, lower = higher priority)")
	flag.Parse()

	cfg, err := loadConfig(*configPath)
	if err != nil {
		if *envAPIKey == "" && os.Getenv("DEEPINFRA_API_KEY") == "" {
			log.Fatalf("Config error: %v (and no --api-key or DEEPINFRA_API_KEY provided)", err)
		}
		cfg = &BeaconConfig{
			Priority: 10,
			Provider: ProviderConfig{
				Type:            "deepinfra",
				RotationSeconds: 300,
				ExpiresSeconds:  600,
			},
		}
		hostname, _ := os.Hostname()
		cfg.Name = hostname + "-beacon"
	}

	if *envAPIKey != "" {
		cfg.Provider.APIKey = *envAPIKey
	} else if envKey := os.Getenv("DEEPINFRA_API_KEY"); envKey != "" {
		cfg.Provider.APIKey = envKey
	}
	if *priority > 0 {
		cfg.Priority = *priority
	}

	if cfg.Provider.APIKey == "" {
		log.Fatal("No API key configured. Use --api-key flag or DEEPINFRA_API_KEY env")
	}

	providerCfg := providers.Config{
		APIKey:          cfg.Provider.APIKey,
		Priority:        cfg.Priority,
		RotationSeconds: cfg.Provider.RotationSeconds,
		ExpiresSeconds:  cfg.Provider.ExpiresSeconds,
		Enabled:         true,
	}

	provider := providers.NewDeepInfraProvider(providerCfg)
	log.Printf("Starting Saturn beacon: %s (priority %d)", cfg.Name, cfg.Priority)
	log.Printf("Provider: %s, rotation: %ds, expires: %ds",
		provider.Name(),
		cfg.Provider.RotationSeconds,
		cfg.Provider.ExpiresSeconds)

	cred, err := provider.GenerateCredential()
	if err != nil {
		log.Fatalf("Failed to generate initial credential: %v", err)
	}
	log.Printf("Initial credential generated, expires at %s", cred.ExpiresAt.Format(time.RFC3339))

	var server *zeroconf.Server
	localIP := getLocalIP()

	registerService := func() error {
		if server != nil {
			server.Shutdown()
		}

		txtRecords := provider.TXTRecords()
		txt := make([]string, 0, len(txtRecords))
		for k, v := range txtRecords {
			txt = append(txt, k+"="+v)
		}

		var err error
		server, err = zeroconf.Register(
			cfg.Name,
			ServiceType,
			Domain,
			5354, // Port for SRV record (beacon doesn't serve HTTP, but mDNS requires a port)
			txt,
			nil,
		)
		if err != nil {
			return fmt.Errorf("mDNS registration failed: %w", err)
		}

		log.Printf("Registered %s.%s.%s with ephemeral key (first 20 chars: %s...)",
			cfg.Name, ServiceType, Domain, truncate(txtRecords["ephemeral_key"], 20))
		return nil
	}

	if err := registerService(); err != nil {
		log.Fatalf("Failed to register mDNS service: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	rotationTicker := time.NewTicker(provider.RotationInterval())
	defer rotationTicker.Stop()

	statusTicker := time.NewTicker(60 * time.Second)
	defer statusTicker.Stop()

	log.Printf("Beacon running. IP: %s, will rotate every %s", localIP, provider.RotationInterval())

	for {
		select {
		case <-ctx.Done():
			return

		case sig := <-sigChan:
			log.Printf("Received signal %v, shutting down...", sig)
			if server != nil {
				server.Shutdown()
			}
			return

		case <-rotationTicker.C:
			log.Printf("Rotating credential...")
			if _, err := provider.GenerateCredential(); err != nil {
				log.Printf("WARNING: Credential rotation failed: %v", err)
				continue
			}
			if err := registerService(); err != nil {
				log.Printf("WARNING: Failed to re-register mDNS: %v", err)
			}

		case <-statusTicker.C:
			txtRecords := provider.TXTRecords()
			log.Printf("Status: provider=%s, priority=%s, key_len=%d",
				txtRecords["api"],
				txtRecords["priority"],
				len(txtRecords["ephemeral_key"]))
		}
	}
}

func truncate(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max]
}
