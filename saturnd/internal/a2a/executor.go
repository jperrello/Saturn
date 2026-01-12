package a2a

import (
	"context"
	"fmt"
	"os/exec"
	"strings"
	"time"
)

type Executor struct {
	timeout time.Duration
}

func NewExecutor(timeout time.Duration) *Executor {
	if timeout == 0 {
		timeout = 5 * time.Minute
	}
	return &Executor{timeout: timeout}
}

func (e *Executor) Execute(ctx context.Context, task Task) TaskResult {
	ctx, cancel := context.WithTimeout(ctx, e.timeout)
	defer cancel()

	taskContent := task.Message.Content
	if task.Context != "" {
		taskContent = fmt.Sprintf("Context:\n%s\n\nTask:\n%s", task.Context, task.Message.Content)
	}

	cmd := exec.CommandContext(ctx, "claude", "-p", taskContent, "--output-format", "text")
	output, err := cmd.CombinedOutput()

	if ctx.Err() == context.DeadlineExceeded {
		return TaskResult{
			ID:     task.ID,
			Status: StatusFailed,
			Error:  &Error{Code: "timeout", Message: "Task execution timed out"},
		}
	}

	if err != nil {
		exitErr, ok := err.(*exec.ExitError)
		if ok {
			return TaskResult{
				ID:     task.ID,
				Status: StatusFailed,
				Error: &Error{
					Code:    "execution_error",
					Message: fmt.Sprintf("Claude exited with code %d: %s", exitErr.ExitCode(), string(output)),
				},
			}
		}

		if strings.Contains(err.Error(), "executable file not found") {
			return TaskResult{
				ID:     task.ID,
				Status: StatusFailed,
				Error:  &Error{Code: "not_found", Message: "Claude Code not found in PATH"},
			}
		}

		return TaskResult{
			ID:     task.ID,
			Status: StatusFailed,
			Error:  &Error{Code: "execution_error", Message: err.Error()},
		}
	}

	return TaskResult{
		ID:     task.ID,
		Status: StatusCompleted,
		Result: &Result{
			Message: Message{
				Role:    "assistant",
				Content: string(output),
			},
		},
	}
}
