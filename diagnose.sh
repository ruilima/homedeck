#!/bin/bash

# HomeDeck Service Diagnostics
# Helps identify issues before running the service

echo "======================================"
echo "  HomeDeck Service Diagnostics"
echo "======================================"
echo ""

# Detect project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Project directory: $PROJECT_DIR"
echo ""

# Check Python
echo "1. Checking Python..."
PYTHON_PATH=$(which python3)
if [ -z "$PYTHON_PATH" ]; then
    echo "   ✗ python3 not found in PATH"
    exit 1
else
    echo "   ✓ Python found: $PYTHON_PATH"
    $PYTHON_PATH --version
fi
echo ""

# Check pip
echo "2. Checking pip..."
if ! which pip3 > /dev/null 2>&1; then
    echo "   ✗ pip3 not found"
else
    echo "   ✓ pip3 found: $(which pip3)"
fi
echo ""

# Check if homedeck module is installed
echo "3. Checking homedeck module..."
if $PYTHON_PATH -c "import homedeck" 2>/dev/null; then
    echo "   ✓ homedeck module installed"
    $PYTHON_PATH -c "import homedeck; print('   Version:', homedeck.__dict__.get('__version__', 'unknown'))"
else
    echo "   ✗ homedeck module not installed"
    echo "   → Run: pip3 install -e $PROJECT_DIR"
fi
echo ""

# Check required files
echo "4. Checking required files..."

if [ -f "$PROJECT_DIR/deck.py" ]; then
    echo "   ✓ deck.py found"
else
    echo "   ✗ deck.py not found"
fi

if [ -f "$PROJECT_DIR/.env" ]; then
    echo "   ✓ .env found"

    # Check .env contents
    if grep -q "HA_HOST=" "$PROJECT_DIR/.env" && grep -q "HA_ACCESS_TOKEN=" "$PROJECT_DIR/.env"; then
        HA_HOST=$(grep "HA_HOST=" "$PROJECT_DIR/.env" | cut -d'=' -f2 | tr -d '"' | tr -d ' ')
        HA_TOKEN=$(grep "HA_ACCESS_TOKEN=" "$PROJECT_DIR/.env" | cut -d'=' -f2 | tr -d '"' | tr -d ' ')

        if [ -z "$HA_HOST" ] || [ "$HA_HOST" = "" ]; then
            echo "   ⚠ HA_HOST is empty in .env"
        else
            echo "   ✓ HA_HOST configured: $HA_HOST"
        fi

        if [ -z "$HA_TOKEN" ] || [ "$HA_TOKEN" = "" ]; then
            echo "   ⚠ HA_ACCESS_TOKEN is empty in .env"
        else
            echo "   ✓ HA_ACCESS_TOKEN configured (hidden)"
        fi
    fi
else
    echo "   ✗ .env not found"
    echo "   → Copy from: cp .env.example .env"
fi

if [ -f "$PROJECT_DIR/assets/configuration.yml" ]; then
    echo "   ✓ configuration.yml found"
else
    echo "   ⚠ configuration.yml not found"
    echo "   → Check: assets/configuration.yml"
fi
echo ""

# Check USB devices (for Stream Deck)
echo "5. Checking USB devices..."
if [ -d "/dev/bus/usb" ]; then
    echo "   ✓ USB devices available"
    if which lsusb > /dev/null 2>&1; then
        # Check for Ulanzi device (vendor:product = 2207:0019)
        if lsusb | grep -q "2207:0019"; then
            echo "   ✓ Ulanzi D200 detected!"
        else
            echo "   ⚠ Ulanzi D200 not detected"
            echo "   → Make sure device is connected"
            echo ""
            echo "   All USB devices:"
            lsusb | sed 's/^/      /'
        fi
    fi
else
    echo "   ⚠ USB devices not accessible"
fi
echo ""

# Check if running as root
echo "6. Checking permissions..."
if [ "$EUID" -eq 0 ]; then
    echo "   ✓ Running as root"
else
    echo "   ⚠ Not running as root"
    echo "   → Service needs root to access USB devices"
    echo "   → Use: sudo ./diagnose.sh"
fi
echo ""

# Check if systemd is available
echo "7. Checking systemd..."
if which systemctl > /dev/null 2>&1; then
    echo "   ✓ systemd available"

    # Check if service exists
    if systemctl list-unit-files | grep -q "homedeck.service"; then
        echo "   ✓ homedeck.service installed"

        # Check service status
        echo ""
        echo "   Service status:"
        systemctl status homedeck.service --no-pager 2>&1 | sed 's/^/      /'
    else
        echo "   ⚠ homedeck.service not installed yet"
        echo "   → Run: ./install-service.sh"
    fi
else
    echo "   ✗ systemd not available"
fi
echo ""

# Try to import and test
echo "8. Testing module import..."
TEST_OUTPUT=$($PYTHON_PATH -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')
try:
    from homedeck.homedeck import HomeDeck
    print('   ✓ HomeDeck class imported successfully')
except ImportError as e:
    print(f'   ✗ Import error: {e}')
    sys.exit(1)
" 2>&1)

if [ $? -eq 0 ]; then
    echo "$TEST_OUTPUT"
else
    echo "$TEST_OUTPUT"
    echo "   → Fix import errors before running service"
fi
echo ""

# Check network connectivity
echo "9. Checking network..."
if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
    echo "   ✓ Internet connectivity OK"
else
    echo "   ⚠ No internet connectivity"
    echo "   → Check network connection"
fi
echo ""

echo "======================================"
echo "  Diagnostics complete!"
echo "======================================"
echo ""

# Summary
HAS_ERRORS=0

if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "⚠ Action required: Create .env file"
    HAS_ERRORS=1
fi

if ! $PYTHON_PATH -c "import homedeck" 2>/dev/null; then
    echo "⚠ Action required: Install homedeck module (pip3 install -e .)"
    HAS_ERRORS=1
fi

if [ "$HAS_ERRORS" -eq 0 ]; then
    echo "✓ All checks passed! Ready to install service."
    echo ""
    echo "Next steps:"
    echo "  1. Run: sudo ./install-service.sh"
    echo "  2. Check logs: sudo journalctl -u homedeck.service -f"
else
    echo ""
    echo "⚠ Please fix the issues above before installing the service."
fi
echo ""
