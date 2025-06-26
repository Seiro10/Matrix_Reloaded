#!/bin/bash

# Script pour démarrer le Dashboard HIL Centralisé
# Usage: ./start_hil_dashboard.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is required but not installed"
    exit 1
fi

# Check if required packages are installed
log_info "📦 Checking Python dependencies..."
python3 -c "import aiohttp, asyncio" 2>/dev/null || {
    log_warn "Installing required Python packages..."
    if command -v pip3 &> /dev/null; then
        pip3 install aiohttp
    elif command -v pip &> /dev/null; then
        pip install aiohttp
    else
        log_error "pip not found. Please install aiohttp manually: sudo apt install python3-pip && pip3 install aiohttp"
        exit 1
    fi
}

# Check if hil_dashboard.py exists
if [ ! -f "hil_dashboard.py" ]; then
    log_error "❌ hil_dashboard.py not found in current directory!"
    log_info "Please create the file with the dashboard code first"
    exit 1
fi

# Check if agents are running
log_info "🔍 Checking agents status..."

AGENTS=(
    "8000:content-finder"
    "8080:router-agent"
    "8083:copywriter-agent"
    "8084:metadata-generator"
    "8085:rewriter-main"
)

all_running=true
for agent in "${AGENTS[@]}"; do
    IFS=':' read -r port name <<< "$agent"
    if curl -f http://localhost:$port/health &> /dev/null 2>&1; then
        log_info "  ✅ $name (port $port) - Running"
    else
        log_warn "  ⚠️ $name (port $port) - Not responding"
        all_running=false
    fi
done

if [ "$all_running" = false ]; then
    log_warn "Some agents are not responding. Dashboard may have limited functionality."
    echo -n "Continue anyway? (y/n): "
    read -r REPLY
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
log_info "🎛️ Starting HIL Dashboard..."
log_info "💡 Dashboard will monitor all your agents and allow interaction"
log_info "🛑 Use Ctrl+C to quit"
echo ""

# Start the dashboard
python3 hil_dashboard.py