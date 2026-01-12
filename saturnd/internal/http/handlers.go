package http

import (
	"encoding/json"
	"net/http"
)

func (s *Server) handleAgentCard(w http.ResponseWriter, r *http.Request) {
	cardJSON, err := s.advertiser.GetAgentCardJSON()
	if err != nil {
		http.Error(w, "Failed to generate agent card", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write(cardJSON)
}

func (s *Server) handleCredentials(w http.ResponseWriter, r *http.Request) {
	provider := r.URL.Query().Get("provider")

	var resp interface{}
	var ok bool

	if provider != "" {
		resp, ok = s.beaconCache.GetCredentialResponseByProvider(provider)
	} else {
		resp, ok = s.beaconCache.GetCredentialResponse()
	}

	if !ok {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(map[string]string{
			"error":   "no_credentials",
			"message": "No beacon credentials available",
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(resp)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	health := map[string]interface{}{
		"status":         "healthy",
		"service":        "saturnd",
		"version":        "1.0.0",
		"beacon_count":   s.beaconCache.Count(),
		"detected_local": len(s.agentMonitor.GetDetectedAgents()),
	}

	if s.disco != nil {
		health["discovered_services"] = len(s.disco.GetServices())
		health["discovered_agents"] = len(s.disco.GetAgents())
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(health)
}

func (s *Server) handleListAgents(w http.ResponseWriter, r *http.Request) {
	type agentInfo struct {
		Name        string   `json:"name"`
		URL         string   `json:"url"`
		Description string   `json:"description,omitempty"`
		Skills      []string `json:"skills,omitempty"`
	}

	var agents []agentInfo

	if s.disco != nil {
		for _, svc := range s.disco.GetAgents() {
			info := agentInfo{
				Name: svc.Name,
				URL:  svc.Properties["agent_card"],
			}
			if svc.AgentCard != nil {
				info.Description = svc.AgentCard.Description
				for _, skill := range svc.AgentCard.Skills {
					info.Skills = append(info.Skills, skill.Name)
				}
			}
			agents = append(agents, info)
		}
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agents": agents,
		"count":  len(agents),
	})
}

func (s *Server) handleRoot(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}

	info := map[string]interface{}{
		"service":     "Saturn Agent Daemon",
		"version":     "1.0.0",
		"description": "Zero-configuration AI agent discovery and credential injection",
		"endpoints": map[string]string{
			"agent_card":  "/.well-known/agent-card.json",
			"credentials": "/v1/credentials",
			"health":      "/v1/health",
			"agents":      "/v1/agents",
		},
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(info)
}
