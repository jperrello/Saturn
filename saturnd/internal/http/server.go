package http

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/joeyperrello/saturn/saturnd/internal/a2a"
	"github.com/joeyperrello/saturn/saturnd/internal/agents"
	"github.com/joeyperrello/saturn/saturnd/internal/beacon"
	"github.com/joeyperrello/saturn/saturnd/internal/discovery"
)

type Server struct {
	httpServer   *http.Server
	advertiser   *discovery.Advertiser
	beaconCache  *beacon.Cache
	agentMonitor *agents.Monitor
	disco        *discovery.Discovery
	taskHandler  *a2a.TaskHandler
}

func NewServer(port int, advertiser *discovery.Advertiser, beaconCache *beacon.Cache, agentMonitor *agents.Monitor, disco *discovery.Discovery) *Server {
	executor := a2a.NewExecutor(5 * time.Minute)
	taskHandler := a2a.NewTaskHandler(executor)

	s := &Server{
		advertiser:   advertiser,
		beaconCache:  beaconCache,
		agentMonitor: agentMonitor,
		disco:        disco,
		taskHandler:  taskHandler,
	}

	mux := http.NewServeMux()

	mux.HandleFunc("GET /.well-known/agent-card.json", s.handleAgentCard)
	mux.HandleFunc("GET /v1/credentials", s.handleCredentials)
	mux.HandleFunc("GET /v1/health", s.handleHealth)
	mux.HandleFunc("GET /v1/agents", s.handleListAgents)

	mux.HandleFunc("POST /a2a/tasks", taskHandler.HandleTask)
	mux.HandleFunc("POST /a2a/tasks/async", taskHandler.HandleAsyncTask)
	mux.HandleFunc("GET /a2a/tasks", taskHandler.HandleGetTask)

	mux.HandleFunc("GET /", s.handleRoot)

	s.httpServer = &http.Server{
		Addr:         fmt.Sprintf(":%d", port),
		Handler:      corsMiddleware(loggingMiddleware(mux)),
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Minute,
		IdleTimeout:  60 * time.Second,
	}

	return s
}

func (s *Server) Start(ctx context.Context) error {
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		s.httpServer.Shutdown(shutdownCtx)
	}()

	log.Printf("HTTP server listening on %s", s.httpServer.Addr)
	if err := s.httpServer.ListenAndServe(); err != http.ErrServerClosed {
		return err
	}
	return nil
}

func (s *Server) Shutdown(ctx context.Context) error {
	return s.httpServer.Shutdown(ctx)
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("%s %s %s", r.Method, r.URL.Path, time.Since(start))
	})
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}
