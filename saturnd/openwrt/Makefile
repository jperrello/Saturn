# SPDX-License-Identifier: MIT
# Saturn Beacon OpenWRT Package
# Zero-configuration AI service discovery for local networks

include $(TOPDIR)/rules.mk

PKG_NAME:=saturn-beacon
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

PKG_LICENSE:=MIT
PKG_MAINTAINER:=Joey Perrello <jperrello@ucsc.edu>

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/joeyperrello/saturn.git
PKG_SOURCE_VERSION:=HEAD
PKG_MIRROR_HASH:=skip

PKG_BUILD_DEPENDS:=golang/host
PKG_BUILD_PARALLEL:=1
PKG_BUILD_FLAGS:=no-mips16

GO_PKG:=github.com/joeyperrello/saturn/saturnd
GO_PKG_BUILD_PKG:=$(GO_PKG)/cmd/saturn-beacon

include $(INCLUDE_DIR)/package.mk
include ../../lang/golang/golang-package.mk

define Package/saturn-beacon
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=AI Services
  TITLE:=Saturn AI Service Discovery Beacon
  URL:=https://github.com/joeyperrello/saturn
  DEPENDS:=$(GO_ARCH_DEPENDS)
  PKGARCH:=all
endef

define Package/saturn-beacon/description
Saturn Beacon provides zero-configuration AI service discovery for local
networks. It announces AI API credentials via mDNS (Bonjour/Avahi),
allowing any device on the network to discover and use AI services
without individual API key configuration.

Features:
- mDNS service advertisement (_saturn._tcp.local)
- Ephemeral JWT credential generation (DeepInfra)
- Automatic credential rotation
- Priority-based service selection
- Low resource usage (<15MB RAM)
endef

define Package/saturn-beacon/conffiles
/etc/config/saturn
endef

define Build/Compile
	$(call GoPackage/Build/Compile)
endef

define Package/saturn-beacon/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(GO_PKG_BUILD_BIN_DIR)/saturn-beacon $(1)/usr/bin/saturn-beacon

	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/saturn.init $(1)/etc/init.d/saturn

	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/saturn.config $(1)/etc/config/saturn
endef

define Package/saturn-beacon/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	echo "Enabling saturn-beacon service..."
	/etc/init.d/saturn enable
	echo ""
	echo "==============================================="
	echo " Saturn Beacon installed successfully!"
	echo ""
	echo " NEXT STEPS:"
	echo " 1. Configure your API key:"
	echo "    uci set saturn.deepinfra.api_key='YOUR_KEY'"
	echo "    uci commit saturn"
	echo ""
	echo " 2. Start the service:"
	echo "    /etc/init.d/saturn start"
	echo ""
	echo " Or use LuCI: Services > Saturn Beacon"
	echo "==============================================="
}
exit 0
endef

define Package/saturn-beacon/prerm
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	/etc/init.d/saturn stop
	/etc/init.d/saturn disable
}
exit 0
endef

$(eval $(call GoBinPackage,saturn-beacon))
$(eval $(call BuildPackage,saturn-beacon))
