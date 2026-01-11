# Saturn Codebase History

This document chronicles the evolution of the Saturn project from December 2025 through January 2026, tracing the journey from initial beacon implementation to a fully-packaged Python module with unified CLI tooling.

---

## Starting Point: f32ddac

**Date:** December 28, 2025
**Message:** "Added anchors, and legacy code move"

This commit established the foundation for the Winter quarter development sprint.

**Created:**
- `anchors/Saturn_Winter_Memo.md` — Project vision document outlining the goals for Winter quarter
- `anchors/Sprint1_Implementation_Plan.md` — Detailed implementation plan for the first sprint
- `.gitattributes` — Configuration for beads issue tracker

**Moved:**
- All files from `references/` → `legacy_code/` (C++ attempts, old client/server files, Jan.ai notes)

**Purpose:** This commit organized the project for a focused development sprint. The anchors provided strategic direction while legacy code was properly archived to reduce clutter in the active codebase.

---

## Phase 1: Beacon Foundation (Dec 28, 2025)

### b5a026d — Gitignore Housekeeping

**Message:** "chore: update gitignore for local development files"

**Edited:**
- `.gitignore` — Added `.env.example` and `CLAUDE.md` to keep local configs private

**Purpose:** Standard development hygiene before beginning feature work.

---

### f43d606 — JWT Manager Implementation

**Message:** "feat(beacon): implement JWT manager for DeepInfra ephemeral credentials"

**Created:**
- `beacons/jwt_manager.py` — JWTManager class for generating and managing scoped JWT tokens from DeepInfra API
- `beacons/jwt_research_findings.md` — API research documentation on DeepInfra's ephemeral key system
- `beacons/test_jwt_manager.py` — Comprehensive test suite

**Purpose:** This was the core innovation of Saturn's beacon system. DeepInfra's API allows generating short-lived (10-minute) JWT tokens that can be safely broadcast via mDNS. The JWTManager handles:
- Thread-safe token generation with locks
- Configurable expiration and rotation intervals
- Model scoping and spending limits
- Tokens small enough (175-266 chars) to fit in mDNS TXT records

---

### 3dbf7bd — Beacon Announcer

**Message:** "feat(beacon): implement BeaconAnnouncer class with zeroconf mDNS registration"

**Created:**
- `beacons/beacon_announcer.py` — BeaconAnnouncer class for mDNS service advertisement
- `beacons/test_beacon_announcer.py` — Test suite for announcer

**Purpose:** The second component of the beacon system. BeaconAnnouncer wraps the zeroconf library to advertise Saturn beacon services via mDNS, including the ephemeral JWT credentials in TXT records. Supports register/unregister and re-registration for key rotation.

---

### 92317db — Key Rotation Loop

**Message:** "feat(beacon): implement key rotation background thread"

**Created:**
- `beacons/key_rotation.py` — `rotation_loop()` function for daemon thread that automatically rotates JWT credentials every 5 minutes

**Deleted:**
- `beacons/test_beacon_announcer.py` — Tests moved or refactored

**Purpose:** This completed the beacon's automatic credential rotation system. The background thread:
- Checks every 60 seconds if rotation is needed
- Generates new tokens via JWTManager
- Updates mDNS announcements via BeaconAnnouncer
- Handles HTTP 429 rate limits gracefully

---

## Phase 2: Consolidation (Dec 28-30, 2025)

### 0f506c2 — Single-File Architecture

**Message:** "refactor(beacon): consolidate split files into single-file architecture"

**Deleted:**
- `beacons/jwt_manager.py`
- `beacons/beacon_announcer.py`
- `beacons/key_rotation.py`
- `beacons/jwt_research_findings.md`
- `beacons/test_jwt_manager.py`

**Purpose:** Merged all beacon server components into `beacons/deepinfra_beacon.py` and client components into `clients/beacon_client.py`. This followed Saturn's established single-file server pattern (like `openrouter_server.py` and `ollama_server.py`). All functionality was preserved—the split architecture was overly complex for what amounted to a single cohesive service.

---

### 01781f8 — Documentation Push

**Message:** "docs(beacon): add comprehensive documentation for ephemeral credentials"

**Created:**
- `beacons/README.md` — Setup, architecture, and troubleshooting guide
- `beacons/DEMO.md` — Demo script and walkthrough

**Edited:**
- `README.md` — Added Saturn Beacons section explaining Layer 1 architecture
- `beacons/deepinfra_beacon.py` — Added code comments for rotation logic
- `clients/beacon_client.py` — Added comments for ServiceListener callback behavior

**Purpose:** Comprehensive documentation push to make the beacon system understandable to others. Explained thread safety, mDNS patterns, and the overall architecture.

---

### c5af6b4 — Beacon Stripped to Pure Announcer

**Message:** "refactor(beacon): strip beacon to pure mDNS announcer script"

**Edited:**
- `beacons/deepinfra_beacon.py` — Removed FastAPI server infrastructure (286 → 264 lines)
- `beacons/README.md` — Updated to reflect announcer architecture
- `README.md` — Updated descriptions
- `clients/simple_chat_client.py` — Refactored significantly

**Created:**
- `legacy_code/README.md` — Documentation for archived code

**Moved:**
- `clients/beacon_client.py` → `legacy_code/beacon_client.py`

**Purpose:** Key architectural insight: the beacon doesn't need to be a server. Clients extract credentials directly from mDNS TXT records and call DeepInfra directly. The beacon is literally "a script that announces how to access some other service." Removed FastAPI, uvicorn dependencies, HTTP endpoints (`/v1/health`, `/v1/models`), and unused methods. The main() now uses `signal.pause()` instead of `uvicorn.run()`.

---

### 504ade0 — Security Improvement

**Message:** "refactor(simple_chat_client): use SHA256 fingerprints for JWT token logging"

**Edited:**
- `clients/simple_chat_client.py` — Replaced raw token logging with SHA256 fingerprints

**Purpose:** Security best practice. Instead of potentially exposing full JWT tokens in logs, the client now logs only fingerprints (first 12 characters of SHA256 hash). Allows tracking token changes without revealing credentials.

---

## Phase 3: Documentation and Client Refactor (Dec 30, 2025)

### 535cacc — Documentation Overhaul

**Message:** "docs: rewrite documentation with technical focus and use case explanations"

**Created:**
- `clients/README.md` — Client implementation documentation
- `servers/README.md` — Server documentation
- `fiction/README.md` — Design fiction context
- `fiction/BEACON_DESIGN_FICTION.md` — Narrative design document
- `requirements.txt` — Project dependencies

**Edited:**
- `README.md` — Major rewrite with technical focus (402 lines significantly reduced and restructured)

**Purpose:** Complete documentation reorganization. Split monolithic README into focused component docs. Added design fiction to explain the project vision through narrative.

---

### 786d629 — Client Discovery Refactor

**Message:** "refactor(clients): switch simple_chat_client to dns-sd subprocess and add beacon support"

**Edited:**
- `clients/simple_chat_client.py` — Switched from zeroconf library to dns-sd subprocess
- `clients/file_upload_client.py` — Major refactor for beacon support

**Deleted:**
- `tests/test_beacon_flow.py` — Removed obsolete tests

**Purpose:** Architectural consistency. The dns-sd subprocess approach proved more reliable cross-platform than the Python zeroconf library for client-side discovery. Also added beacon credential extraction support to both clients.

---

## Phase 4: Layer 2 Vision (Jan 3, 2026)

### 0c57f4c — Awareness Service and Winter Plan

**Message:** "Add Saturn Layer 2 awareness service, update docs, and new winter plan"

**Created:**
- `beacons/saturn_awareness_service.py` — MCP server for Claude Code agent awareness (incomplete)
- `beacons/ss/beacon_key_change.png`, `beacon_key_change2.png` — Screenshots
- `research/rings/SATURN_RINGS_INTEGRATION.md` — Integration plan for new architecture
- `research/rings/design_fiction_adam.md` — Design fiction for Adam persona
- `research/rings/design_fiction_steve.md` — Design fiction for Steve persona
- `research/transcripts/first_pod.txt`, `second_pod.txt`, `no_ide.txt` — Research transcripts
- `reports/Fall25 Saturn Report.pdf` — Fall quarter report
- `legacy_code/winter_anchors_folder/SATURN_LAYER2_VISION.md` — Layer 2 vision document

**Renamed:**
- `beacons/deepinfra_beacon.py` → `beacons/winter_beacon.py`

**Moved:**
- `anchors/Saturn_Winter_Memo.md` → `legacy_code/winter_anchors_folder/`
- `anchors/Sprint1_Implementation_Plan.md` → `legacy_code/winter_anchors_folder/`

**Deleted:**
- `beacons/DEMO.md` — Obsolete demo script

**Edited:**
- `.gitignore`, `README.md`, `beacons/README.md`, `servers/ollama_server.py`

**Purpose:** Major strategic pivot. The "rings" concept emerged—a new service type (`_rings._tcp`) for MCP-compatible AI services. The awareness service (Layer 2) would provide Claude Code agents with model cost, usage, and network presence information. The design fictions explored different user personas (Adam: network admin, Steve: enterprise user) to validate the architecture.

---

## Phase 5: Rings Module (Jan 3, 2026)

### ac6f826 — Saturn Rings Implementation

**Message:** "feat(rings): add Saturn Rings module with dual mDNS registration"

**Created:**
- `rings/README.md` — Documentation for rings module
- `rings/__init__.py` — Package initialization
- `rings/saturn_rings.py` — Core discovery and advertisement classes (RingsService, RingsDiscovery, RingsAdvertiser)
- `rings/ollama_server.py` — Ollama server with dual mDNS registration
- `rings/openrouter_server.py` — OpenRouter server with dual mDNS registration

**Purpose:** Implementation of the `_rings._tcp.local.` service type. The key innovation is dual-registration: servers announce on both `_saturn._tcp` (backward compatibility) and `_rings._tcp` (new MCP-aware protocol). The module provides:
- `RingsService` dataclass with TXT record fields
- `RingsDiscovery` for background service discovery
- `RingsAdvertiser` for server-side registration

---

## Phase 6: Package Restructure (Jan 5, 2026)

### 75eb8e5 — Housekeeping

**Message:** "chore: move deprecated awareness service to legacy, add pyproject.toml"

**Moved:**
- `beacons/saturn_awareness_service.py` → `legacy_code/`

**Created:**
- `pyproject.toml` — Python package configuration

**Edited:**
- `research/rings/design_fiction_adam.md` — Minor fix

**Purpose:** The awareness service was incomplete and not on the critical path. Moving it to legacy cleaned up the active codebase while preserving the work. The pyproject.toml began the transition to proper Python packaging.

---

### 8ab0be2 — Major Restructure

**Message:** "refactor: restructure package from rings to saturn, move legacy servers"

**Created:**
- `saturn/__main__.py` — Unified CLI dispatcher with subcommands
- `saturn/aider_saturn.py` — Zero-config Aider integration
- `saturn/beacon.py` — Ephemeral JWT credential distribution (port of winter_beacon)
- `saturn/fallback_server.py` — Testing/failover mock server

**Edited:**
- `saturn/README.md` — Updated for new package structure
- `saturn/__init__.py` — Updated exports
- `saturn/discovery.py` — Refactored to use zeroconf with SaturnService dataclass
- `saturn/ollama_server.py` — Simplified, uses new discovery module
- `saturn/openrouter_server.py` — Simplified, uses new discovery module
- `legacy_code/README.md`, `legacy_code/standalone_servers/README.md`

**Purpose:** The `rings/` package was renamed to `saturn/` for cleaner naming. This was the culmination of the architecture work:
- Unified CLI (`python -m saturn <subcommand>`)
- All servers share the same discovery infrastructure
- Deprecated standalone servers moved to `legacy_code/standalone_servers/`
- Clean separation between core module and client implementations

---

### fe5742d — Documentation Update

**Message:** "docs: update documentation for saturn package"

**Created:**
- `beacons/beacon_explained.md` — Detailed code walkthrough (504 lines)

**Edited:**
- `README.md` — New CLI commands and installation instructions, Windows PATH guidance
- `docs/index.html` — Updated with saturn package references and beacon section

**Purpose:** Comprehensive documentation for the new package structure. The beacon_explained.md provides a line-by-line walkthrough of the beacon implementation for educational purposes.

---

### 44cd93e — Final Packaging

**Message:** "chore: update packaging and project configuration"

**Edited:**
- `pyproject.toml` — Added all dependencies (zeroconf, fastapi, uvicorn, etc.), defined CLI entry points
- `.gitignore` — Minor updates

**Purpose:** Completed the packaging work. The pyproject.toml now defines:
- All package dependencies
- CLI entry points (`saturn`, `saturn-beacon`, `saturn-openrouter`, etc.)
- Package discovery for `saturn/*`

This enables `pip install -e .` for development and proper package distribution.

---

## Summary: The Arc of Development

The commits tell a story of progressive refinement:

1. **Foundation** (f32ddac): Project organization and vision documents
2. **Feature Build** (f43d606 → 92317db): JWT manager, beacon announcer, key rotation—building blocks created separately
3. **Consolidation** (0f506c2 → c5af6b4): Realizing simpler is better, merging files, stripping unnecessary server infrastructure
4. **Documentation** (01781f8, 535cacc, fe5742d): Making the system understandable
5. **Pivot** (0c57f4c): Layer 2 vision and rings concept emerge from research
6. **Implementation** (ac6f826): Saturn Rings module with dual registration
7. **Packaging** (75eb8e5 → 44cd93e): Professional package structure with unified CLI

The project evolved from exploratory feature code to a clean, packaged module following Python best practices. The beacon's journey—from multi-file implementation to stripped-down announcer—exemplifies the "do one thing well" philosophy that came to define Saturn's architecture.
