package discovery

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"os"
	"sync"

	"github.com/grandcat/zeroconf"
	"github.com/joeyperrello/saturn/saturnd/internal/agents"
)

type AgentCard struct {
	Name                string            `json:"name"`
	Description         string            `json:"description"`
	URL                 string            `json:"url"`
	Version             string            `json:"version"`
	SupportedInterfaces []Interface       `json:"supportedInterfaces"`
	Capabilities        Capabilities      `json:"capabilities"`
	Skills              []Skill           `json:"skills"`
	Authentication      AuthRequirements  `json:"authentication"`
}

type Interface struct {
	Protocol string `json:"protocol"`
	URL      string `json:"url"`
}

type Capabilities struct {
	Streaming         bool `json:"streaming"`
	PushNotifications bool `json:"pushNotifications"`
}

type Skill struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description"`
	InputModes  []string `json:"inputModes,omitempty"`
	OutputModes []string `json:"outputModes,omitempty"`
}

type AuthRequirements struct {
	Schemes []string `json:"schemes"`
}

type Advertiser struct {
	serviceType string
	domain      string
	port        int
	server      *zeroconf.Server
	agentCard   AgentCard
	mu          sync.RWMutex
}

func NewAdvertiser(serviceType, domain string, port int) *Advertiser {
	hostname, _ := os.Hostname()
	localIP := getLocalIP()

	return &Advertiser{
		serviceType: serviceType,
		domain:      domain,
		port:        port,
		agentCard: AgentCard{
			Name:        fmt.Sprintf("%s-saturn-agent", hostname),
			Description: "Saturn Agent Daemon - Zero-configuration AI service discovery",
			URL:         fmt.Sprintf("http://%s:%d", localIP, port),
			Version:     "1.0.0",
			SupportedInterfaces: []Interface{
				{Protocol: "a2a/1.0", URL: fmt.Sprintf("http://%s:%d/a2a", localIP, port)},
				{Protocol: "http", URL: fmt.Sprintf("http://%s:%d", localIP, port)},
			},
			Capabilities: Capabilities{
				Streaming:         true,
				PushNotifications: false,
			},
			Skills: []Skill{},
			Authentication: AuthRequirements{
				Schemes: []string{"none"},
			},
		},
	}
}

func (a *Advertiser) Start(ctx context.Context) error {
	hostname, _ := os.Hostname()

	txt := []string{
		"version=2.0",
		"agent=true",
		fmt.Sprintf("agent_card=http://%s:%d/.well-known/agent-card.json", getLocalIP(), a.port),
		"protocols=a2a,mcp",
		"saturn=2.0",
	}

	var err error
	a.server, err = zeroconf.Register(
		hostname+"-agent",
		a.serviceType,
		a.domain,
		a.port,
		txt,
		nil,
	)

	if err != nil {
		return fmt.Errorf("failed to register mDNS service: %w", err)
	}

	log.Printf("Registered %s-agent.%s.%s on port %d", hostname, a.serviceType, a.domain, a.port)
	return nil
}

func (a *Advertiser) Stop() {
	if a.server != nil {
		a.server.Shutdown()
	}
}

func (a *Advertiser) UpdateAgentCard(agent agents.DetectedAgent) {
	a.mu.Lock()
	defer a.mu.Unlock()

	skill := Skill{
		ID:          agent.Name,
		Name:        agent.Name,
		Description: fmt.Sprintf("Detected AI agent: %s", agent.Name),
		InputModes:  []string{"text/plain"},
		OutputModes: []string{"text/plain"},
	}

	// Check if skill already exists
	for i, s := range a.agentCard.Skills {
		if s.ID == skill.ID {
			a.agentCard.Skills[i] = skill
			return
		}
	}

	a.agentCard.Skills = append(a.agentCard.Skills, skill)
}

func (a *Advertiser) GetAgentCardJSON() ([]byte, error) {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return json.MarshalIndent(a.agentCard, "", "  ")
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
