# Start Page

Server management page. Three sub-views toggled by hiding/showing panels.

## Sub-view 1: Password Gate
Shown by default. Contains:
- Warning icon (⚠)
- Heading: "Enter Admin Password"
- Password input field
- Submit button

Any non-empty password is accepted (mock auth). On submit, gate hides and server panel shows.

## Sub-view 2: Server Panel
Shows after authentication. Contains:
- Heading: "Current Running Servers"
- Checklist of servers with checkboxes (pre-checked = running)
- "Configure New Service" button — transitions to config view

### Mock Servers
| Name | Checked |
|---|---|
| derrickLLM_buffet | yes |
| OpenRouter | no |
| OLLAMA | yes |
| DO_NOT_PICK | no |

## Sub-view 3: Configuration Page (Two-Column Layout)

Reached via "Configure New Service" from server panel. Uses the same two-column layout as the Discover page.

### Left Column
- Space background only — no Saturn planet, no rings, no moons
- Stars with sine-wave brightness (same star field as Discover)
- "Configure New Service" button centered in the middle of the space

### Right Column — Config Form
Takes inspiration from the LuCI router admin panel (`saturn-router/openwrt/luci-app-saturn`). The form fields mirror what a Saturn server operator would configure:

#### Fields
| Field | Type | Notes |
|---|---|---|
| Name | text input | Alphanumeric, hyphens, underscores only. Placeholder: `my-service` |
| Deployment | dropdown | `Cloud (remote API)` or `Network (local/LAN)` |
| API Type | dropdown | `OpenAI-compatible` or `Ollama-native` |
| Enabled | toggle/checkbox | Default: on |
| Priority | number input | 0–100, default 10. Lower = higher priority |
| Base URL | text input | Required. Placeholder: `https://api.example.com/v1` |
| Advertise Port | number input | Port for mDNS. Placeholder: `8400`. Only shown for Cloud deployment |
| API Key | password input | Only shown for Cloud deployment |
| Host | text input | Hostname or IP. Placeholder: `192.168.1.50`. Only shown for Network deployment |
| Port | number input | Only shown for Network deployment |

#### Conditional Fields (Ephemeral Keys)
Shown only when Deployment = Cloud and "Ephemeral Keys" toggle is enabled:
| Field | Type | Notes |
|---|---|---|
| Ephemeral Keys | toggle/checkbox | Default: off |
| Key Generation Endpoint | text input | Placeholder: `https://openrouter.ai/api/v1/keys` |
| Spending Limit | number input | USD per key. Default: 0 (no limit) |
| Rotation Interval | number input | Seconds. Default: 300 |
| Expiration Interval | number input | Seconds. Default: 600. Must be > rotation interval |

#### Status Badges
Each configured service shows a status badge:
- `● UP` (green) — healthy
- `● DOWN` (red) — unreachable
- `DISABLED` (gray) — not enabled
- `? UNKNOWN` (yellow) — not yet checked

#### Buttons
- **Test Connection** — validates connectivity to the configured endpoint (Network deployment only)
- **Save** — adds the service to the server list, returns to server panel
- **Back** — returns to server panel without saving

## Interaction Flow
1. User enters password -> server panel appears
2. User can toggle server checkboxes
3. User clicks "Configure New Service" -> two-column config view appears
4. Left side shows space background with centered button, right side shows config form
5. Deployment dropdown controls which fields are visible (Cloud vs Network)
6. Save or Back -> returns to server panel

## Reference Images
- `references/02-start.jpeg` (password gate)
- `references/03-config.png` (config form)
