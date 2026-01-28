# SPDX-License-Identifier: MIT
# Saturn OpenWRT Package
# Zero-configuration AI service discovery for local networks
#
# This package uses pre-built binaries since Rust cross-compilation
# in OpenWRT SDK is complex. Binaries are built via GitHub Actions.

include $(TOPDIR)/rules.mk

PKG_NAME:=saturn
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

PKG_LICENSE:=MIT
PKG_MAINTAINER:=Joey Perrello <jperrello@ucsc.edu>

# Pre-built binary - downloaded during install, not build
# This avoids needing Rust in the OpenWRT SDK
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)

include $(INCLUDE_DIR)/package.mk

# Architecture to binary name mapping
ifeq ($(ARCH),mipsel)
  SATURN_ARCH:=mipsel-sf
  SATURN_VARIANT:=full
endif

SATURN_BINARY:=saturn-$(SATURN_ARCH)-$(SATURN_VARIANT)
SATURN_URL:=https://github.com/jperrello/Saturn/releases/download/v$(PKG_VERSION)/$(SATURN_BINARY)

define Package/saturn
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=AI Services
  TITLE:=Saturn - Network AI Service Discovery
  URL:=https://github.com/jperrello/Saturn
  DEPENDS:=@(mipsel)
  PKGARCH:=all
endef

define Package/saturn/description
Saturn provides zero-configuration AI service discovery for local networks.
It announces AI services via mDNS (Bonjour/Avahi), allowing any device on
the network to discover and use AI backends without manual configuration.

Features:
- mDNS service advertisement (_saturn._tcp.local)
- Cloud services: Ephemeral key rotation (OpenRouter)
- Network services: Health-monitored proxies (Ollama, vLLM, LocalAI)
- Priority-based service selection
- LuCI web interface for easy configuration
- Low resource usage (<15MB RAM)
endef

define Package/saturn/conffiles
/etc/config/saturn
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
	# Download pre-built binary
	wget -q -O $(PKG_BUILD_DIR)/saturn "$(SATURN_URL)" || \
		curl -sSL -o $(PKG_BUILD_DIR)/saturn "$(SATURN_URL)"
	chmod +x $(PKG_BUILD_DIR)/saturn
endef

define Package/saturn/install
	$(INSTALL_DIR) $(1)/tmp
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/saturn $(1)/tmp/saturn

	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/saturn.init $(1)/etc/init.d/saturn

	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/saturn.config $(1)/etc/config/saturn
endef

define Package/saturn/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	echo "Enabling Saturn service..."
	/etc/init.d/saturn enable
	echo ""
	echo "==============================================="
	echo " Saturn installed successfully!"
	echo ""
	echo " Configure via LuCI: Services > Saturn"
	echo " Or via command line: uci show saturn"
	echo ""
	echo " NOTE: Binary is in /tmp and will be lost on"
	echo " reboot. Run 'opkg install saturn' after reboot."
	echo "==============================================="
}
exit 0
endef

define Package/saturn/prerm
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	/etc/init.d/saturn stop
	/etc/init.d/saturn disable
}
exit 0
endef

$(eval $(call BuildPackage,saturn))
