# SPDX-License-Identifier: MIT
# LuCI App for Saturn - Network AI Service Registry

include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI support for Saturn AI Service Discovery
LUCI_DEPENDS:=+saturn +curl +jsonfilter
LUCI_PKGARCH:=all

PKG_LICENSE:=MIT
PKG_MAINTAINER:=Joey Perrello <jperrello@ucsc.edu>

include ../../luci.mk

# call BuildPackage - OpenWrt buildance
$(eval $(call BuildPackage,luci-app-saturn))
