# Legacy Code Archive

This directory contains proof-of-concept code, experimental implementations, and archived files that are no longer part of the main Saturn codebase but are preserved for reference and historical context.

## Contents

### beacon_client.py
**Status:** Archived - Replaced by beacon-aware `simple_chat_client.py`

**Purpose:** Original proof-of-concept demonstrating that Saturn Beacon ephemeral credential system works end-to-end.

**What it proved:**
- Beacons can be discovered via mDNS using zeroconf library
- Ephemeral JWTs can be extracted from TXT records
- Direct DeepInfra API calls work with beacon-provided credentials
- Key rotation detection works via `update_service` callbacks

**Why it was archived:**
This was created as a minimal test client to validate the beacon concept. Once proven successful, the beacon discovery and JWT authentication logic was integrated into `clients/simple_chat_client.py`, which provides a full chat interface with history management, server switching, and automatic failover.

**For production beacon usage, use:** `clients/simple_chat_client.py`

**Historical significance:** This file demonstrates the original beacon implementation pattern and serves as a reference for understanding how the zeroconf-based credential discovery system works at its core.

---

## Other Archived Materials

This directory may also contain:
- Old experiment logs and notes
- Previous implementation attempts
- Development snapshots for reference
- Files replaced during refactoring

These materials are kept for historical context and to document the evolution of the Saturn project.
