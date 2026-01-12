package mcp

import (
	"bufio"
	"context"
	"encoding/json"
	"io"
	"log"
	"os"

	"github.com/joeyperrello/saturn/saturnd/internal/beacon"
	"github.com/joeyperrello/saturn/saturnd/internal/discovery"
)

const (
	ServerName    = "saturn"
	ServerVersion = "1.0.0"
	ProtocolVersion = "2024-11-05"
)

type Server struct {
	toolHandler *ToolHandler
	reader      *bufio.Reader
	writer      io.Writer
	initialized bool
}

func NewServer(disco *discovery.Discovery, beaconCache *beacon.Cache, advertiser *discovery.Advertiser) *Server {
	return &Server{
		toolHandler: NewToolHandler(disco, beaconCache, advertiser),
		reader:      bufio.NewReader(os.Stdin),
		writer:      os.Stdout,
	}
}

func (s *Server) Run(ctx context.Context) error {
	log.SetOutput(os.Stderr)
	log.Println("MCP server starting...")

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		line, err := s.reader.ReadString('\n')
		if err != nil {
			if err == io.EOF {
				return nil
			}
			return err
		}

		if line == "" || line == "\n" {
			continue
		}

		var request JSONRPCRequest
		if err := json.Unmarshal([]byte(line), &request); err != nil {
			s.sendError(nil, ParseError, "Parse error")
			continue
		}

		response := s.handleRequest(request)
		s.sendResponse(response)
	}
}

func (s *Server) handleRequest(req JSONRPCRequest) JSONRPCResponse {
	switch req.Method {
	case "initialize":
		return s.handleInitialize(req)
	case "initialized":
		return JSONRPCResponse{JSONRPC: "2.0", ID: req.ID}
	case "tools/list":
		return s.handleToolsList(req)
	case "tools/call":
		return s.handleToolsCall(req)
	case "ping":
		return JSONRPCResponse{JSONRPC: "2.0", ID: req.ID, Result: map[string]interface{}{}}
	default:
		return JSONRPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Error:   NewError(MethodNotFound, "Method not found: "+req.Method),
		}
	}
}

func (s *Server) handleInitialize(req JSONRPCRequest) JSONRPCResponse {
	s.initialized = true

	result := InitializeResult{
		ProtocolVersion: ProtocolVersion,
		Capabilities: Capabilities{
			Tools: &ToolsCapability{},
		},
		ServerInfo: ServerInfo{
			Name:    ServerName,
			Version: ServerVersion,
		},
	}

	return JSONRPCResponse{
		JSONRPC: "2.0",
		ID:      req.ID,
		Result:  result,
	}
}

func (s *Server) handleToolsList(req JSONRPCRequest) JSONRPCResponse {
	return JSONRPCResponse{
		JSONRPC: "2.0",
		ID:      req.ID,
		Result:  ToolsListResult{Tools: ToolDefinitions},
	}
}

func (s *Server) handleToolsCall(req JSONRPCRequest) JSONRPCResponse {
	paramsBytes, err := json.Marshal(req.Params)
	if err != nil {
		return JSONRPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Error:   NewError(InvalidParams, "Invalid params"),
		}
	}

	var params ToolCallParams
	if err := json.Unmarshal(paramsBytes, &params); err != nil {
		return JSONRPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Error:   NewError(InvalidParams, "Invalid tool call params"),
		}
	}

	result := s.toolHandler.Call(params.Name, params.Arguments)

	return JSONRPCResponse{
		JSONRPC: "2.0",
		ID:      req.ID,
		Result:  result,
	}
}

func (s *Server) sendResponse(resp JSONRPCResponse) {
	data, err := json.Marshal(resp)
	if err != nil {
		log.Printf("Failed to marshal response: %v", err)
		return
	}
	s.writer.Write(data)
	s.writer.Write([]byte("\n"))
}

func (s *Server) sendError(id interface{}, code int, message string) {
	resp := JSONRPCResponse{
		JSONRPC: "2.0",
		ID:      id,
		Error:   NewError(code, message),
	}
	s.sendResponse(resp)
}
