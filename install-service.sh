#!/bin/bash

# HomeDeck Service Installer
# Automatically detects paths and installs systemd service

set -e

echo "======================================"
echo "  HomeDeck Service Installer"
echo "======================================"
echo ""

# Detect project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "✓ Project directory: $PROJECT_DIR"

# Detect Python path
PYTHON_PATH=$(which python3)
if [ -z "$PYTHON_PATH" ]; then
    echo "✗ Error: python3 not found in PATH"
    exit 1
fi
echo "✓ Python path: $PYTHON_PATH"

# Check if Python can import homedeck
echo ""
echo "Checking Python environment..."
if ! $PYTHON_PATH -c "import homedeck" 2>/dev/null; then
    echo "⚠ Warning: homedeck module not installed"
    echo "  Installing now..."
    cd "$PROJECT_DIR"
    pip3 install -e . || {
        echo "✗ Error: Failed to install homedeck"
        exit 1
    }
    echo "✓ homedeck installed successfully"
fi

# Check for .env file
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo ""
    echo "⚠ Warning: .env file not found"
    echo "  Please create .env from .env.example and configure:"
    echo "    cp .env.example .env"
    echo "    nano .env"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for configuration file
if [ ! -f "$PROJECT_DIR/assets/configuration.yml" ]; then
    echo ""
    echo "⚠ Warning: assets/configuration.yml not found"
    echo "  Please create configuration.yml from the example"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Generate service file
SERVICE_FILE="$PROJECT_DIR/homedeck-generated.service"
echo ""
echo "Generating service file..."

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=HomeDeck Stream Deck Controller
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=$PYTHON_PATH $PROJECT_DIR/deck.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Service file generated: $SERVICE_FILE"

# Show service file content
echo ""
echo "Generated service file content:"
echo "--------------------------------"
cat "$SERVICE_FILE"
echo "--------------------------------"
echo ""

# Test if deck.py can be executed
echo "Testing if deck.py can be executed..."
if [ ! -f "$PROJECT_DIR/deck.py" ]; then
    echo "✗ Error: deck.py not found in $PROJECT_DIR"
    exit 1
fi

# Test Python import (without running)
if ! $PYTHON_PATH -c "import sys; sys.path.insert(0, '$PROJECT_DIR'); from homedeck.homedeck import HomeDeck" 2>/dev/null; then
    echo "✗ Error: Cannot import HomeDeck module"
    echo "  Try running: pip3 install -e $PROJECT_DIR"
    exit 1
fi
echo "✓ Module imports successfully"

# Ask to install
echo ""
read -p "Install service to systemd? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Service file saved to: $SERVICE_FILE"
    echo "To install manually:"
    echo "  sudo cp $SERVICE_FILE /etc/systemd/system/homedeck.service"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable homedeck.service"
    echo "  sudo systemctl start homedeck.service"
    exit 0
fi

# Install service
echo ""
echo "Installing service..."

if [ "$EUID" -ne 0 ]; then
    echo "Running with sudo..."
    sudo cp "$SERVICE_FILE" /etc/systemd/system/homedeck.service
    sudo systemctl daemon-reload
else
    cp "$SERVICE_FILE" /etc/systemd/system/homedeck.service
    systemctl daemon-reload
fi

echo "✓ Service installed"

# Ask to enable and start
echo ""
read -p "Enable and start service now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ "$EUID" -ne 0 ]; then
        sudo systemctl enable homedeck.service
        sudo systemctl start homedeck.service
        echo ""
        echo "✓ Service enabled and started"
        echo ""
        echo "Checking status..."
        sleep 2
        sudo systemctl status homedeck.service --no-pager
    else
        systemctl enable homedeck.service
        systemctl start homedeck.service
        echo ""
        echo "✓ Service enabled and started"
        echo ""
        echo "Checking status..."
        sleep 2
        systemctl status homedeck.service --no-pager
    fi
else
    echo ""
    echo "Service installed but not started."
    echo "To enable and start:"
    echo "  sudo systemctl enable homedeck.service"
    echo "  sudo systemctl start homedeck.service"
fi

echo ""
echo "======================================"
echo "  Installation complete!"
echo "======================================"
echo ""
echo "Useful commands:"
echo "  View status:   sudo systemctl status homedeck.service"
echo "  View logs:     sudo journalctl -u homedeck.service -f"
echo "  Restart:       sudo systemctl restart homedeck.service"
echo "  Stop:          sudo systemctl stop homedeck.service"
echo "  Disable:       sudo systemctl disable homedeck.service"
echo ""
