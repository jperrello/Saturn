package mcp

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/joeyperrello/saturn/saturnd/internal/a2a"
	"github.com/joeyperrello/saturn/saturnd/internal/beacon"
	"github.com/joeyperrello/saturn/saturnd/internal/discovery"
)

var ToolDefinitions = []Tool{
	{
		Name:        "discover_agents",
		Description: "Discover AI agents on the local network via Saturn mDNS",
		InputSchema: InputSchema{
			Type: "object",
			Properties: map[string]Property{
				"skill_filter": {
					Type:        "string",
					Description: "Optional skill to filter agents by (e.g., 'research', 'code_review')",
				},
			},
		},
	},
	{
		Name:        "delegate_task",
		Description: "Delegate a task to a remote agent discovered via Saturn",
		InputSchema: InputSchema{
			Type: "object",
			Properties: map[string]Property{
				"agent_name": {
					Type:        "string",
					Description: "Name of the target agent (from discover_agents)",
				},
				"task": {
					Type:        "string",
					Description: "Description of the task to delegate",
				},
				"context": {
					Type:        "string",
					Description: "Optional context or files to include",
				},
			},
			Required: []string{"agent_name", "task"},
		},
	},
	{
		Name:        "get_credentials",
		Description: "Get API credentials from Saturn beacons on the network",
		InputSchema: InputSchema{
			Type: "object",
			Properties: map[string]Property{
				"provider": {
					Type:        "string",
					Description: "Optional provider filter (e.g., 'DeepInfra', 'OpenRouter')",
				},
			},
		},
	},
	{
		Name:        "get_agent_status",
		Description: "Get status of the local Saturn daemon and detected agents",
		InputSchema: InputSchema{
			Type:       "object",
			Properties: map[string]Property{},
		},
	},
}

type ToolHandler struct {
	disco       *discovery.Discovery
	beaconCache *beacon.Cache
	advertiser  *discovery.Advertiser
	a2aClient   *a2a.Client
}

func NewToolHandler(disco *discovery.Discovery, beaconCache *beacon.Cache, advertiser *discovery.Advertiser) *ToolHandler {
	return &ToolHandler{
		disco:       disco,
		beaconCache: beaconCache,
		advertiser:  advertiser,
		a2aClient:   a2a.NewClient(5 * time.Minute),
	}
}

func (h *ToolHandler) Call(name string, args map[string]interface{}) ToolCallResult {
	switch name {
	case "discover_agents":
		return h.discoverAgents(args)
	case "delegate_task":
		return h.delegateTask(args)
	case "get_credentials":
		return h.getCredentials(args)
	case "get_agent_status":
		return h.getAgentStatus(args)
	default:
		return errorResult(fmt.Sprintf("Unknown tool: %s", name))
	}
}

func (h *ToolHandler) discoverAgents(args map[string]interface{}) ToolCallResult {
	skillFilter, _ := args["skill_filter"].(string)

	agents := h.disco.GetAgents()
	var result []map[string]interface{}

	for _, svc := range agents {
		agent := map[string]interface{}{
			"name": svc.Name,
			"ip":   svc.IP,
			"port": svc.Port,
		}

		if svc.AgentCard != nil {
			agent["description"] = svc.AgentCard.Description
			agent["version"] = svc.AgentCard.Version

			var skills []string
			for _, skill := range svc.AgentCard.Skills {
				skills = append(skills, skill.Name)
			}
			agent["skills"] = skills

			if skillFilter != "" {
				hasSkill := false
				for _, skill := range svc.AgentCard.Skills {
					if skill.ID == skillFilter || skill.Name == skillFilter {
						hasSkill = true
						break
					}
				}
				if !hasSkill {
					continue
				}
			}
		}

		result = append(result, agent)
	}

	return jsonResult(map[string]interface{}{
		"agents": result,
		"count":  len(result),
	})
}

func (h *ToolHandler) delegateTask(args map[string]interface{}) ToolCallResult {
	agentName, ok := args["agent_name"].(string)
	if !ok || agentName == "" {
		return errorResult("agent_name is required")
	}

	taskContent, ok := args["task"].(string)
	if !ok || taskContent == "" {
		return errorResult("task is required")
	}

	taskContext, _ := args["context"].(string)

	agentURL, found := h.disco.GetAgentURL(agentName)
	if !found {
		return errorResult(fmt.Sprintf("Agent '%s' not found. Use discover_agents first.", agentName))
	}

	task := a2a.Task{
		ID: a2a.GenerateTaskID(),
		Message: a2a.Message{
			Role:    "user",
			Content: taskContent,
		},
		Context: taskContext,
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	result, err := h.a2aClient.SendTask(ctx, agentURL, task)
	if err != nil {
		return jsonResult(map[string]interface{}{
			"status":    "failed",
			"agent":     agentName,
			"agent_url": agentURL,
			"error":     err.Error(),
		})
	}

	response := map[string]interface{}{
		"status":    result.Status,
		"agent":     agentName,
		"agent_url": agentURL,
		"task_id":   result.ID,
	}

	if result.Result != nil {
		response["result"] = result.Result.Message.Content
	}
	if result.Error != nil {
		response["error"] = result.Error.Message
	}

	return jsonResult(response)
}

func (h *ToolHandler) getCredentials(args map[string]interface{}) ToolCallResult {
	provider, _ := args["provider"].(string)

	var resp beacon.CredentialResponse
	var ok bool

	if provider != "" {
		resp, ok = h.beaconCache.GetCredentialResponseByProvider(provider)
	} else {
		resp, ok = h.beaconCache.GetCredentialResponse()
	}

	if !ok {
		return jsonResult(map[string]interface{}{
			"available": false,
			"message":   "No beacon credentials available on the network",
		})
	}

	return jsonResult(map[string]interface{}{
		"available":          true,
		"api_key":            resp.OPENAI_API_KEY,
		"base_url":           resp.OPENAI_BASE_URL,
		"provider":           resp.Provider,
		"expires_in_seconds": resp.ExpiresIn,
	})
}

func (h *ToolHandler) getAgentStatus(args map[string]interface{}) ToolCallResult {
	card := h.advertiser.GetAgentCard()

	var skills []string
	for _, s := range card.Skills {
		skills = append(skills, s.Name)
	}

	discoveredAgents := h.disco.GetAgents()
	discoveredBeacons := h.disco.GetBeacons()

	return jsonResult(map[string]interface{}{
		"daemon": map[string]interface{}{
			"name":    card.Name,
			"version": card.Version,
			"url":     card.URL,
			"skills":  skills,
		},
		"network": map[string]interface{}{
			"discovered_agents":  len(discoveredAgents),
			"discovered_beacons": len(discoveredBeacons),
			"cached_credentials": h.beaconCache.Count(),
		},
	})
}

func jsonResult(data interface{}) ToolCallResult {
	jsonBytes, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return errorResult(fmt.Sprintf("Failed to serialize result: %v", err))
	}
	return ToolCallResult{
		Content: []ContentBlock{{Type: "text", Text: string(jsonBytes)}},
	}
}

func errorResult(message string) ToolCallResult {
	return ToolCallResult{
		Content: []ContentBlock{{Type: "text", Text: message}},
		IsError: true,
	}
}
