# OpenWRT Package Feed Submission Guide

This document outlines the process for getting Saturn into the official OpenWRT packages repository.

## Goal

Enable users to install Saturn with:
```bash
opkg update
opkg install saturn
```

## Prerequisites

Before submitting:
- [ ] Saturn has stable releases on GitHub
- [ ] Binary sizes are reasonable for target devices
- [ ] Documentation is complete
- [ ] License is clearly stated (MIT)
- [ ] Package has been tested on multiple OpenWRT versions

## OpenWRT Packages Repository

**Repository**: https://github.com/openwrt/packages

**Documentation**: https://openwrt.org/docs/guide-developer/packages

## Submission Process

### 1. Fork the Packages Repository

```bash
# Fork on GitHub, then clone
git clone https://github.com/YOUR_USERNAME/packages.git
cd packages
git remote add upstream https://github.com/openwrt/packages.git
```

### 2. Create Package Directory

```bash
mkdir -p net/saturn
```

### 3. Package Structure

The package needs:
```
net/saturn/
├── Makefile           # Build instructions
└── files/
    ├── saturn.init    # procd init script
    └── saturn.config  # UCI configuration
```

### 4. Makefile Requirements

OpenWRT packages must follow strict conventions:

```makefile
# Required header
include $(TOPDIR)/rules.mk

PKG_NAME:=saturn
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

# License (required)
PKG_LICENSE:=MIT
PKG_LICENSE_FILES:=LICENSE

# Maintainer (required)
PKG_MAINTAINER:=Joey Perrello <jperrello@ucsc.edu>

# Source (GitHub releases work well)
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/jperrello/Saturn/tar.gz/v$(PKG_VERSION)?
PKG_HASH:=<sha256sum of tarball>

# For Rust packages, options include:
# 1. Pre-built binaries (simplest, what we use)
# 2. cargo-c integration (complex, not well supported)
# 3. Build in SDK (requires Rust toolchain in SDK)
```

### 5. Handling Rust in OpenWRT

OpenWRT doesn't have native Rust support like it does for Go. Options:

**Option A: Pre-built Binaries (Recommended)**
- Build binaries via GitHub Actions for each architecture
- Package downloads pre-built binary from releases
- Pros: Simple, fast package builds
- Cons: Need to build for each arch, larger hosting

**Option B: Source Build with Rust**
- Would need to add Rust support to OpenWRT SDK
- See: https://github.com/nicholasbalasus/openwrt-rust
- Complex, but more "native" approach

We're using Option A for simplicity.

### 6. Testing in OpenWRT SDK

Before submitting, test the package:

```bash
# Download SDK for your target
wget https://downloads.openwrt.org/releases/23.05.0/targets/ramips/mt76x8/openwrt-sdk-*.tar.xz

# Extract and set up
tar xf openwrt-sdk-*.tar.xz
cd openwrt-sdk-*

# Add your package
mkdir -p package/feeds/saturn
cp -r /path/to/saturn-router/openwrt/* package/feeds/saturn/

# Update feeds
./scripts/feeds update -a
./scripts/feeds install saturn

# Build
make package/saturn/compile V=s
```

### 7. Submit Pull Request

1. Create branch:
   ```bash
   git checkout -b add-saturn
   ```

2. Add package files:
   ```bash
   cp -r /path/to/saturn-router/openwrt/Makefile net/saturn/
   cp -r /path/to/saturn-router/openwrt/files net/saturn/
   ```

3. Commit with proper message:
   ```bash
   git add net/saturn
   git commit -m "saturn: add new package

   Saturn provides zero-configuration AI service discovery for local
   networks using mDNS/DNS-SD. It allows routers to advertise AI
   services (OpenRouter, Ollama, etc.) to all devices on the network.

   Homepage: https://github.com/jperrello/Saturn
   License: MIT
   Signed-off-by: Joey Perrello <jperrello@ucsc.edu>"
   ```

4. Push and create PR:
   ```bash
   git push origin add-saturn
   ```

5. Open PR against `openwrt/packages` `master` branch

### 8. Review Process

Expect feedback on:
- Package naming conventions
- Makefile style
- Dependencies
- Binary size concerns
- Security considerations (API key handling)

Be responsive and address feedback promptly.

## Package Maintainer Responsibilities

Once accepted, you'll be expected to:
- Keep package updated with new releases
- Respond to issues and PRs affecting the package
- Test on new OpenWRT releases
- Fix bugs in a timely manner

## Alternative: Custom Package Feed

If official submission is too complex, create a custom feed:

1. Create a GitHub repo: `saturn-openwrt-feed`
2. Structure:
   ```
   saturn-openwrt-feed/
   └── net/
       └── saturn/
           ├── Makefile
           └── files/
   ```

3. Users add to `/etc/opkg/customfeeds.conf`:
   ```
   src/gz saturn https://github.com/jperrello/saturn-openwrt-feed/raw/main
   ```

4. Then:
   ```bash
   opkg update
   opkg install saturn
   ```

## Timeline Estimate

- Package preparation: 1-2 weeks
- Initial PR submission: 1 day
- Review and revisions: 2-4 weeks
- Merge (if accepted): 1-2 weeks
- Available in next OpenWRT release: 3-6 months

## Resources

- [OpenWRT Package Guidelines](https://openwrt.org/docs/guide-developer/packages)
- [OpenWRT Makefile Reference](https://openwrt.org/docs/guide-developer/packages-framework)
- [Existing Network Packages](https://github.com/openwrt/packages/tree/master/net) (for reference)
- [OpenWRT Forum](https://forum.openwrt.org/) (for questions)
