#!/bin/bash
# x0tta6bl4 Global Edge Network Deployment Utility
# Automates launching Anchor Nodes (PoPs) across multiple clouds.

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}   x0tta6bl4 GLOBAL EDGE NETWORK DEPLOYMENT         ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Regions to deploy
REGIONS=(
  "nyc1.pop.x0tta6bl4.net"
  "fra1.pop.x0tta6bl4.net"
  "sgp1.pop.x0tta6bl4.net"
  "ams3.pop.x0tta6bl4.net"
  "blr1.pop.x0tta6bl4.net"
)

if [ -z "$X0T_ENROLL_TOKEN" ]; then
    echo "❌ Error: X0T_ENROLL_TOKEN environment variable not set."
    exit 1
fi

echo "🚀 Starting parallel deployment to ${#REGIONS[@]} regions..."

# Generate Ansible Inventory on the fly
INVENTORY="deploy/ansible/inventory_edge.ini"
echo "[edge_nodes]" > $INVENTORY
for host in "${REGIONS[@]}"; do
    echo "$host ansible_user=root" >> $INVENTORY
done

# Run Ansible Playbook
ansible-playbook -i $INVENTORY deploy/ansible/anchor_node.yml

echo -e "${GREEN}✅ Global Edge Network deployment sequence complete.${NC}"
echo "Monitoring status: https://control.x0tta6bl4.net/mesh/global-anchor-net"
