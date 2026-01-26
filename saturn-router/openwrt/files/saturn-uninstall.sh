#!/bin/sh
# Saturn OpenWRT Uninstaller

logger -t saturn "Uninstalling Saturn..."

# Stop service
/etc/init.d/saturn stop 2>/dev/null
/etc/init.d/saturn disable 2>/dev/null

# Kill any running processes
killall saturn 2>/dev/null

# Remove binary (may be in /tmp or /usr/bin)
rm -f /tmp/saturn
rm -f /usr/bin/saturn

# Remove init script and config
rm -f /etc/init.d/saturn
rm -f /etc/config/saturn

# Remove runtime files
rm -rf /var/run/saturn-*
rm -rf /tmp/saturn.d

# Remove LuCI components
rm -rf /www/luci-static/resources/view/saturn
rm -f /usr/libexec/rpcd/luci.saturn
rm -f /usr/share/luci/menu.d/luci-app-saturn.json
rm -f /usr/share/rpcd/acl.d/luci-app-saturn.json

# Remove self
rm -f /usr/bin/saturn-uninstall

# Clear LuCI cache
rm -rf /tmp/luci-*

# Restart services
/etc/init.d/rpcd restart
/etc/init.d/uhttpd restart

logger -t saturn "Saturn uninstalled successfully"
echo "Saturn has been uninstalled"