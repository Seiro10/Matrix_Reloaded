#!/bin/bash

# Installation complète du Dashboard HIL
# Usage: ./install_hil_dashboard.sh

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

log_info "🚀 Installing HIL Dashboard for Content Agents..."

# Check Python
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is required. Installing..."
    sudo apt update
    sudo apt install -y python3 python3-pip curl
fi

# Install Python dependencies
log_info "📦 Installing Python dependencies..."
pip3 install aiohttp asyncio --user

# Create dashboard directory
mkdir -p hil_dashboard
cd hil_dashboard

# Create the main dashboard file
log_info "📝 Creating hil_dashboard.py..."
cat > hil_dashboard.py << 'EOF'
#!/usr/bin/env python3
"""
Dashboard HIL Centralisé
Permet d'interagir avec tous les agents depuis un terminal centralisé
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, Any, List
import threading
import sys
import os
from queue import Queue
import signal

class HILDashboard:
    def __init__(self):
        self.agents = {
            "content-finder": "http://localhost:8000",
            "router-agent": "http://localhost:8080",
            "copywriter-agent": "http://localhost:8083",
            "metadata-generator": "http://localhost:8084",
            "rewriter-main": "http://localhost:8085"
        }

        self.pending_validations = {}
        self.validation_queue = Queue()
        self.running = True

        # Colors for terminal
        self.COLORS = {
            'RED': '\033[0;31m',
            'GREEN': '\033[0;32m',
            'YELLOW': '\033[1;33m',
            'BLUE': '\033[0;34m',
            'MAGENTA': '\033[0;35m',
            'CYAN': '\033[0;36m',
            'WHITE': '\033[1;37m',
            'RESET': '\033[0m'
        }

    def colored(self, text: str, color: str) -> str:
        """Add color to text"""
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['RESET']}"

    def log(self, message: str, color: str = 'WHITE'):
        """Log with timestamp and color"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"{self.colored(f'[{timestamp}]', 'CYAN')} {self.colored(message, color)}")

    def display_header(self):
        """Display dashboard header"""
        os.system('clear' if os.name == 'posix' else 'cls')
        print("=" * 80)
        print(self.colored("🎛️  DASHBOARD HIL CENTRALISÉ - AGENTS CONTENT", 'WHITE'))
        print("=" * 80)
        print()

        # Show agent status
        print(self.colored("📡 ÉTAT DES AGENTS:", 'CYAN'))
        for name, url in self.agents.items():
            port = url.split(':')[-1]
            status = "🔍 Checking..."
            print(f"  {name:<20} (:{port}) - {status}")
        print()

    async def check_agent_health(self, name: str, url: str) -> bool:
        """Check if an agent is healthy"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/health", timeout=5) as response:
                    return response.status == 200
        except:
            return False

    async def check_pending_validations(self):
        """Check for pending validations from router-agent"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.agents['router-agent']}/pending-validations") as response:
                    if response.status == 200:
                        data = await response.json()
                        pending = data.get("pending_validations", [])

                        for validation in pending:
                            validation_id = validation["validation_id"]
                            if validation_id not in self.pending_validations:
                                # New validation
                                self.pending_validations[validation_id] = validation
                                self.validation_queue.put(validation)
                                self.log(f"🔔 New validation required: {validation_id}", 'YELLOW')

        except Exception as e:
            pass  # Ignore connection errors

    def display_validation_request(self, validation_data: Dict[str, Any]):
        """Display validation request"""
        data = validation_data["data"]

        print(self.colored("🤔 VALIDATION REQUEST", 'YELLOW'))
        print("=" * 50)
        print(f"Agent: {self.colored('Router-Agent', 'MAGENTA')}")
        print(f"Keyword: {self.colored(data.get('keyword', 'N/A'), 'WHITE')}")
        print(f"Selected Site: {self.colored(data.get('selected_site', 'N/A'), 'GREEN')}")
        print(f"Decision: {self.colored(data.get('routing_decision', 'N/A'), 'BLUE')}")
        print(f"Confidence: {self.colored(data.get('confidence_score', 'N/A'), 'CYAN')}")

        if data.get('existing_content_found'):
            print(f"Existing Content: {self.colored('✅ Found', 'GREEN')}")
        else:
            print(f"Existing Content: {self.colored('❌ Not found', 'RED')}")
        print()

    async def submit_validation_response(self, validation_id: str, response: str) -> bool:
        """Submit validation response to router-agent"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "validation_id": validation_id,
                    "response": response
                }
                async with session.post(
                    f"{self.agents['router-agent']}/submit-validation",
                    json=payload
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            self.log(f"Error submitting validation: {e}", 'RED')
            return False

    def get_user_input(self, prompt: str, options: List[str]) -> str:
        """Get user input with validation"""
        while True:
            try:
                response = input(f"{prompt} ({'/'.join(options)}): ").strip().lower()
                if response in [opt.lower() for opt in options]:
                    return response
                print(f"Please choose from: {', '.join(options)}")
            except KeyboardInterrupt:
                return "stop"
            except EOFError:
                return "stop"

    async def handle_validation(self, validation_data: Dict[str, Any]):
        """Handle validation request"""
        validation_id = validation_data["validation_id"]
        data = validation_data["data"]

        self.display_validation_request(validation_data)

        if data["type"] == "routing_approval":
            response = self.get_user_input(
                self.colored("Do you approve this routing decision?", 'YELLOW'),
                ["yes", "no", "y", "n"]
            )

            if response in ["y", "yes"]:
                response = "yes"
            elif response in ["n", "no"]:
                response = "no"

            success = await self.submit_validation_response(validation_id, response)

            if success:
                self.log(f"✅ Response sent: {response}", 'GREEN')
            else:
                self.log("❌ Error sending response", 'RED')

        if validation_id in self.pending_validations:
            del self.pending_validations[validation_id]

        print()
        input(self.colored("Press Enter to continue...", 'CYAN'))

    async def monitor_agents(self):
        """Monitor agents and handle validations"""
        self.display_header()
        self.log("🚀 HIL Dashboard started", 'GREEN')
        self.log("💡 Monitoring agents for validation requests...", 'CYAN')
        self.log("🛑 Press Ctrl+C to quit", 'YELLOW')
        print()

        while self.running:
            try:
                await self.check_pending_validations()

                # Handle validation requests
                if not self.validation_queue.empty():
                    validation_data = self.validation_queue.get()
                    await self.handle_validation(validation_data)

                await asyncio.sleep(2)

            except Exception as e:
                self.log(f"Error in monitoring: {e}", 'RED')
                await asyncio.sleep(5)

    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        self.running = False
        print(f"\n{self.colored('🛑 Stopping dashboard...', 'YELLOW')}")
        sys.exit(0)

async def main():
    """Main function"""
    dashboard = HILDashboard()
    signal.signal(signal.SIGINT, dashboard.signal_handler)
    await dashboard.monitor_agents()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped")
        sys.exit(0)
EOF

# Create the start script
log_info "📝 Creating start_hil_dashboard.sh..."
cat > start_hil_dashboard.sh << 'EOF'
#!/bin/bash

# Start HIL Dashboard
# Usage: ./start_hil_dashboard.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check Python
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is required but not installed"
    exit 1
fi

# Check dependencies
python3 -c "import aiohttp, asyncio" 2>/dev/null || {
    log_warn "Installing aiohttp..."
    pip3 install aiohttp --user
}

# Check if hil_dashboard.py exists
if [ ! -f "hil_dashboard.py" ]; then
    log_error "❌ hil_dashboard.py not found!"
    exit 1
fi

# Check agents
log_info "🔍 Checking agents..."
AGENTS=("8000" "8080" "8083" "8084" "8085")
for port in "${AGENTS[@]}"; do
    if curl -f http://localhost:$port/health &> /dev/null; then
        log_info "  ✅ Agent on port $port - Running"
    else
        log_warn "  ⚠️ Agent on port $port - Not responding"
    fi
done

echo ""
log_info "🎛️ Starting HIL Dashboard..."
echo ""

# Start dashboard
python3 hil_dashboard.py
EOF

# Make scripts executable
chmod +x start_hil_dashboard.sh
chmod +x hil_dashboard.py

# Create simple test script
log_info "📝 Creating test_agents.sh..."
cat > test_agents.sh << 'EOF'
#!/bin/bash

echo "🧪 Testing all agents..."

AGENTS=(
    "8000:content-finder"
    "8080:router-agent"
    "8083:copywriter-agent"
    "8084:metadata-generator"
    "8085:rewriter-main"
)

for agent in "${AGENTS[@]}"; do
    IFS=':' read -r port name <<< "$agent"
    echo -n "Testing $name (port $port)... "
    if curl -f http://localhost:$port/health &> /dev/null; then
        echo "✅ OK"
    else
        echo "❌ FAIL"
    fi
done
EOF

chmod +x test_agents.sh

echo ""
log_info "✅ HIL Dashboard installed successfully!"
echo ""
log_info "📍 Files created:"
echo "  - hil_dashboard.py (main dashboard)"
echo "  - start_hil_dashboard.sh (start script)"
echo "  - test_agents.sh (test script)"
echo ""
log_info "🚀 Usage:"
echo "  1. Test agents: ./test_agents.sh"
echo "  2. Start dashboard: ./start_hil_dashboard.sh"
echo ""
log_info "💡 The dashboard will monitor your router-agent for validation requests"