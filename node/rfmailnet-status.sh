#!/bin/bash
# RFMailNet Node Status Generator (VK2ICW)
# Node: 44.136.166.10  Tunnel: 10.44.0.2

ASSETS_DIR="/var/www/vk2icw/assets"
NODE_JSON="$ASSETS_DIR/rfmailnet-node.json"
HUB_JSON="$ASSETS_DIR/rfmailnet-hub.json"
HUB_IP="10.44.0.1"

# --- Node Info ---
HOSTNAME=$(hostname)
WG_IP=$(ip -4 addr show wg0 | awk '/10\.44/{print $2}' | cut -d'/' -f1)
NET44_IP=$(ip -4 addr show wg0 | grep -oE '44(\.[0-9]+){3}' | head -n1)
UPTIME=$(uptime -p)
LASTSEEN=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# --- Generate Node JSON ---
cat <<EOF > "$NODE_JSON"
{
  "type": "node",
  "hostname": "$HOSTNAME",
  "tunnel_ip": "$WG_IP",
  "net44_ip": "$NET44_IP",
  "uptime": "$UPTIME",
  "last_seen": "$LASTSEEN",
  "status": "online"
}
EOF

# --- Fetch Hub JSON over tunnel ---
curl -s "http://$HUB_IP/assets/rfmailnet-hub.json" -o "$HUB_JSON"

# --- Set Permissions ---
chown www-data:www-data "$ASSETS_DIR"/rfmailnet-*.json
chmod 644 "$ASSETS_DIR"/rfmailnet-*.json
