package a2a

type Task struct {
	ID      string   `json:"id"`
	Message Message  `json:"message"`
	Context string   `json:"context,omitempty"`
}

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type TaskResult struct {
	ID      string  `json:"id"`
	Status  string  `json:"status"`
	Result  *Result `json:"result,omitempty"`
	Error   *Error  `json:"error,omitempty"`
}

type Result struct {
	Message Message `json:"message"`
}

type Error struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

const (
	StatusCompleted = "completed"
	StatusFailed    = "failed"
	StatusPending   = "pending"
)
