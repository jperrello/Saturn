package agents

import (
	"context"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/shirou/gopsutil/v3/process"
)

var knownAgents = map[string]AgentInfo{
	"claude":      {Name: "Claude Code", Type: "claude-code", MCPCapable: true},
	"claude-code": {Name: "Claude Code", Type: "claude-code", MCPCapable: true},
	"aider":       {Name: "Aider", Type: "aider", MCPCapable: false},
	"cursor":      {Name: "Cursor", Type: "cursor", MCPCapable: true},
	"code":        {Name: "VS Code", Type: "vscode", MCPCapable: true},
	"codex":       {Name: "OpenAI Codex", Type: "codex", MCPCapable: false},
	"amp":         {Name: "Sourcegraph Amp", Type: "amp", MCPCapable: false},
	"opencode":    {Name: "OpenCode", Type: "opencode", MCPCapable: false},
}

type AgentInfo struct {
	Name       string
	Type       string
	MCPCapable bool
}

type DetectedAgent struct {
	Name       string
	Type       string
	PID        int32
	MCPCapable bool
	StartTime  time.Time
}

type Monitor struct {
	detected map[int32]DetectedAgent
	mu       sync.RWMutex
}

func NewMonitor() *Monitor {
	return &Monitor{
		detected: make(map[int32]DetectedAgent),
	}
}

func (m *Monitor) Run(ctx context.Context, onDetect func(DetectedAgent)) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			m.scan(onDetect)
		}
	}
}

func (m *Monitor) scan(onDetect func(DetectedAgent)) {
	procs, err := process.Processes()
	if err != nil {
		log.Printf("Failed to get processes: %v", err)
		return
	}

	currentPIDs := make(map[int32]bool)

	for _, p := range procs {
		name, err := p.Name()
		if err != nil {
			continue
		}

		nameLower := strings.ToLower(name)

		for pattern, info := range knownAgents {
			if strings.Contains(nameLower, pattern) {
				currentPIDs[p.Pid] = true

				m.mu.RLock()
				_, exists := m.detected[p.Pid]
				m.mu.RUnlock()

				if !exists {
					createTime, _ := p.CreateTime()
					agent := DetectedAgent{
						Name:       info.Name,
						Type:       info.Type,
						PID:        p.Pid,
						MCPCapable: info.MCPCapable,
						StartTime:  time.UnixMilli(createTime),
					}

					m.mu.Lock()
					m.detected[p.Pid] = agent
					m.mu.Unlock()

					onDetect(agent)
				}
				break
			}
		}
	}

	// Clean up dead processes
	m.mu.Lock()
	for pid := range m.detected {
		if !currentPIDs[pid] {
			delete(m.detected, pid)
		}
	}
	m.mu.Unlock()
}

func (m *Monitor) GetDetectedAgents() []DetectedAgent {
	m.mu.RLock()
	defer m.mu.RUnlock()

	result := make([]DetectedAgent, 0, len(m.detected))
	for _, agent := range m.detected {
		result = append(result, agent)
	}
	return result
}

func (m *Monitor) IsAgentRunning(agentType string) bool {
	m.mu.RLock()
	defer m.mu.RUnlock()

	for _, agent := range m.detected {
		if agent.Type == agentType {
			return true
		}
	}
	return false
}
