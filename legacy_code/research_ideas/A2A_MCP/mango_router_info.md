# GL-MT300N-V2 (Mango) Hardware Reference

**Source:** Screenshots in `GLinet_ss/` taken 2026-01-12
**Related Issue:** Saturn-emq (closed)
**Blocks:** Saturn-t1p (Phase E1: Minimal Viable Beacon)

---

## Quick Reference for Cross-Compilation

```bash
# Go build command for Mango
GOOS=linux GOARCH=mipsle GOMIPS=softfloat go build -ldflags "-s -w" -o saturn-beacon ./cmd/saturn-beacon

# After build, compress with UPX
upx --best saturn-beacon
```

**Target platform string:** `ramips/mt76x8` (for OpenWRT package feeds)

---

## System Specifications

| Spec | Value | Notes |
|------|-------|-------|
| **Model** | GL-MT300N-V2 | "Mango" travel router |
| **Hostname** | GL-MT300N-V2 | Default hostname |
| **Architecture** | MediaTek MT7628AN ver:1 eco:2 | MIPS little-endian |
| **OpenWRT Version** | 22.03.4 r20123-38ccc47687 | Exceeds 21.02+ requirement |
| **Kernel** | 5.10.176 | Linux kernel |
| **LuCI Branch** | openwrt-22.03 git-23.119.80898-65ef406 | Web UI |

---

## Memory (RAM)

| Metric | Value | Implication |
|--------|-------|-------------|
| **Total** | 119.10 MiB (~128MB) | Matches spec sheet |
| **Used** | 64.96 MiB (54%) | Base system overhead |
| **Available** | 69.49 MiB (58%) | **Plenty for saturn-beacon** |
| **Cached** | 31.54 MiB (26%) | Can be reclaimed |
| **Buffered** | 52.00 KiB (0%) | Minimal |

**Saturn requirement:** 10-15MB RAM → **PASS** (70MB+ available)

---

## Storage (Flash)

| Filesystem | Size | Used | Available | Mount |
|------------|------|------|-----------|-------|
| /dev/root | 11.5M | 11.5M | 0 | /rom (read-only) |
| /dev/mtdblock6 | 1.9M | 1.2M | 728KB | /overlay |
| overlayfs:/overlay | 1.9M | 1.2M | 728KB | / |
| tmpfs | 59.6M | 380KB | 59.2M | /tmp |
| tmpfs | 512KB | 0 | 512KB | /dev |

**GUI reports:**
- Total Flash: 16.00 MB
- System Used: 88.28% (14.13 MB)
- Apps Used: 2.39% (392 KB)
- Available: 9.33% (**1.49 MB**)

### Storage Strategy

**Problem:** Only 1.49MB flash available; saturn-beacon needs ~3MB after UPX compression.

**Solution for Phase 1 (testing):**
```bash
# Copy binary to tmpfs (59MB available)
scp saturn-beacon root@192.168.8.1:/tmp/
ssh root@192.168.8.1 '/tmp/saturn-beacon'
```

**Solution for Phase 2+ (permanent):**
- Consider USB storage expansion (Mango has USB port)
- Or optimize binary size further
- Or clear unused packages from /overlay

---

## SSH Access

| Setting | Value |
|---------|-------|
| SSH Server | Dropbear |
| Port | 22 |
| Interface | All (unspecified) |
| Password Auth | Enabled |
| Root Login | Allowed |

**Connection:**
```bash
ssh root@192.168.8.1
# Password: same as admin panel password
```

---

## Network Configuration (as tested)

The device was connected to UCSC-Guest WiFi during screenshot capture:

| Setting | Value |
|---------|-------|
| SSID | UCSC-Guest (2.4G) |
| Protocol | DHCP client |
| IP Address | 169.233.80.201/20 |
| Gateway | 169.233.95.254 |
| DNS | 128.114.142.6, 128.114.129.33 |
| MAC | 96:83:C4:0D:59:79 |

**For development/testing:** Connect laptop to Mango's own WiFi AP (192.168.8.x subnet) for mDNS to work properly. mDNS won't traverse from UCSC network to Mango's internal network.

---

## Compatibility Verification

Cross-referencing with `OPENWRT_BEACON_PLAN.md` Section 2:

| Requirement | Spec | Actual | Status |
|-------------|------|--------|--------|
| CPU | 580MHz MT7628NN | MT7628AN | ✅ Same family |
| RAM | 128MB | 119.10 MiB | ✅ Match |
| Flash | 16MB | 16MB | ✅ Match |
| OpenWRT | 21.02+ | 22.03.4 | ✅ Exceeds |

---

## Phase 1 Testing Checklist

From `OPENWRT_BEACON_PLAN.md` Section 8:

- [ ] Go binary runs on Mango without errors
- [ ] mDNS beacon visible via `dns-sd -B _saturn._tcp` (from laptop)
- [ ] Claude Code on laptop discovers and uses ephemeral JWT
- [ ] RAM usage < 15MB (verify with `top` on router)

**Test command on Mango:**
```bash
# Run beacon
/tmp/saturn-beacon --config /tmp/saturn.json

# Check memory in another SSH session
top -bn1 | grep saturn
```

**Test command on laptop:**
```bash
# macOS/Linux
dns-sd -B _saturn._tcp local.

# Or using Python zeroconf
python -c "from zeroconf import Zeroconf, ServiceBrowser; z=Zeroconf(); ServiceBrowser(z, '_saturn._tcp.local.', None); import time; time.sleep(5)"
```

---

## Files Referenced

- `GLinet_ss/` - Source screenshots (Overview.png, System_info_version.png, df h.png, memory_usage.png, SSH_access.png, detailed_overview.png, Storage_UCSC_gust_info.png, UCSC_guest_info.png)
- `research/A2A_MCP/OPENWRT_BEACON_PLAN.md` - Implementation plan
- `research/A2A_MCP/IMPLEMENTATION_PLAN.md` - Full saturnd architecture
- `for_joey.md` - Human action items tracker

---

## Next Steps

**Issue Saturn-t1p** is unblocked and ready for work:
1. Set up Go cross-compilation environment
2. Create minimal `cmd/saturn-beacon/main.go`
3. Implement mDNS announcement (grandcat/zeroconf)
4. Add single provider (DeepInfra JWT generation)
5. Cross-compile and test on Mango

Run `bd show Saturn-t1p` for full issue details.
