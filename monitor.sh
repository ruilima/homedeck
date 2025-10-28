#!/bin/bash

# HomeDeck Real-time Diagnostics
# Monitor Home Assistant events and Stream Deck updates

echo "======================================"
echo "  HomeDeck Live Diagnostics"
echo "======================================"
echo ""

echo "Monitoring homedeck service logs..."
echo "Press Ctrl+C to stop"
echo ""
echo "What to look for:"
echo "  - 'state_changed' events from Home Assistant"
echo "  - '👆' when you press Stream Deck buttons"
echo "  - 'reload' when page updates"
echo ""
echo "----------------------------------------"
echo ""

# Follow logs with specific filters
sudo journalctl -u homedeck.service -f -n 0 | grep --line-buffered -E "state_changed|reload|Device connected|subscribed|👆|sleep|wake"
