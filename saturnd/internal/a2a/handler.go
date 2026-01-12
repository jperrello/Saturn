package a2a

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"sync"
)

type TaskHandler struct {
	executor    *Executor
	activeTasks sync.Map
}

func NewTaskHandler(executor *Executor) *TaskHandler {
	return &TaskHandler{
		executor: executor,
	}
}

func (h *TaskHandler) HandleTask(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var task Task
	if err := json.NewDecoder(r.Body).Decode(&task); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error":   "invalid_request",
			"message": "Failed to parse task: " + err.Error(),
		})
		return
	}

	if task.ID == "" {
		task.ID = GenerateTaskID()
	}

	if task.Message.Content == "" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error":   "invalid_task",
			"message": "Task message content is required",
		})
		return
	}

	log.Printf("Received A2A task %s: %s", task.ID, truncate(task.Message.Content, 100))

	ctx := r.Context()
	result := h.executor.Execute(ctx, task)

	log.Printf("Task %s completed with status: %s", task.ID, result.Status)

	w.Header().Set("Content-Type", "application/json")
	if result.Status == StatusCompleted {
		w.WriteHeader(http.StatusOK)
	} else {
		w.WriteHeader(http.StatusInternalServerError)
	}
	json.NewEncoder(w).Encode(result)
}

func (h *TaskHandler) HandleAsyncTask(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var task Task
	if err := json.NewDecoder(r.Body).Decode(&task); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error":   "invalid_request",
			"message": "Failed to parse task: " + err.Error(),
		})
		return
	}

	if task.ID == "" {
		task.ID = GenerateTaskID()
	}

	h.activeTasks.Store(task.ID, TaskResult{
		ID:     task.ID,
		Status: StatusPending,
	})

	go func() {
		ctx := context.Background()
		result := h.executor.Execute(ctx, task)
		h.activeTasks.Store(task.ID, result)
	}()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]string{
		"id":     task.ID,
		"status": StatusPending,
	})
}

func (h *TaskHandler) HandleGetTask(w http.ResponseWriter, r *http.Request) {
	taskID := r.URL.Query().Get("id")
	if taskID == "" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error":   "missing_id",
			"message": "Task ID is required",
		})
		return
	}

	result, ok := h.activeTasks.Load(taskID)
	if !ok {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(map[string]string{
			"error":   "not_found",
			"message": "Task not found",
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(result)
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}
