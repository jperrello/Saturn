package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/joeyperrello/saturn/saturnd/internal/agents"
	"github.com/joeyperrello/saturn/saturnd/internal/beacon"
	"github.com/joeyperrello/saturn/saturnd/internal/discovery"
)

const (
	DefaultPort       = 7827
	DefaultMCPPort    = 7828
	ServiceType       = "_saturn._tcp"
	Domain            = "local."
	DiscoveryInterval = 5 // seconds
)

func main() {
	port := flag.Int("port", DefaultPort, "HTTP server port for Agent Card and A2A endpoints")
	mcpPort := flag.Int("mcp-port", DefaultMCPPort, "MCP server port (stdio by default)")
	verbose := flag.Bool("verbose", false, "Enable verbose logging")
	flag.Parse()

	if *verbose {
		log.SetFlags(log.LstdFlags | log.Lshortfile)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Handle graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// Initialize components
	disco := discovery.New(ServiceType, Domain)
	beaconCache := beacon.NewCache()
	agentMonitor := agents.NewMonitor()

	// Start discovery loop (finds beacons and other Saturn services)
	go disco.Run(ctx, func(svc discovery.Service) {
		log.Printf("Discovered: %s at %s:%d", svc.Name, svc.Host, svc.Port)

		// Cache beacon credentials
		if svc.Properties["features"] == "ephemeral_auth" {
			beaconCache.Update(svc.Name, beacon.Credential{
				APIKey:   svc.Properties["ephemeral_key"],
				Provider: svc.Properties["api"],
				Priority: svc.Priority,
			})
			log.Printf("Cached beacon credential from %s", svc.Name)
		}
	})

	// Start agent advertisement (announces this machine's agents)
	advertiser := discovery.NewAdvertiser(ServiceType, Domain, *port)
	if err := advertiser.Start(ctx); err != nil {
		log.Fatalf("Failed to start advertiser: %v", err)
	}

	// Start process monitor (detects AI agents starting)
	go agentMonitor.Run(ctx, func(agent agents.DetectedAgent) {
		log.Printf("Detected agent: %s (PID: %d)", agent.Name, agent.PID)
		// Update Agent Card with detected agent info
		advertiser.UpdateAgentCard(agent)
	})

	// Start HTTP server for Agent Card and A2A
	go startHTTPServer(ctx, *port, beaconCache, agentMonitor)

	// Start MCP server for Claude Code integration (optional, stdio mode)
	if os.Getenv("SATURN_MCP_MODE") == "1" {
		go startMCPServer(ctx, beaconCache, disco)
	}

	log.Printf("Saturn daemon started on port %d", *port)
	log.Printf("Agent Card available at: http://localhost:%d/.well-known/agent-card.json", *port)

	// Wait for shutdown signal
	<-sigChan
	log.Println("Shutting down...")
	cancel()
	advertiser.Stop()
}

func startHTTPServer(ctx context.Context, port int, beaconCache *beacon.Cache, agentMonitor *agents.Monitor) {
	// Implementation in internal/http/server.go
	log.Printf("HTTP server would start on port %d", port)
}

func startMCPServer(ctx context.Context, beaconCache *beacon.Cache, disco *discovery.Discovery) {
	// Implementation in internal/mcp/server.go
	log.Println("MCP server would start on stdio")
}
