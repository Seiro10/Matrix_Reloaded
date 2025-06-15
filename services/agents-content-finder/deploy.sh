#!/bin/bash

# Content Finder Agent Deployment Script (connects to existing router-agent)
# Usage: ./deploy.sh [build|start|stop|restart|logs|status|test]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.yml"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking requirements..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    # Check if router-agent is running
    if ! curl -f http://localhost:8080/health &> /dev/null; then
        log_error "Router Agent is not running on port 8080"
        log_info "Please start your router-agent first, then run this script"
        exit 1
    else
        log_info "✅ Router Agent is running on port 8080"
    fi

    # Check .env file
    if [ ! -f .env ]; then
        log_warn ".env file not found. Creating from template..."
        cat > .env << EOF
# API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
DATAFOR_SEO_TOKEN=your_dataforseo_token_here
BRIGHT_DATA_API_KEY=your_brightdata_api_key_here
BRIGHTDATA_ZONE_NAME=your_brightdata_zone_name_here

# Environment
ENVIRONMENT=production
EOF
        log_warn "Please edit .env file with your API keys before running"
        exit 1
    fi

    log_info "Requirements check passed"
}

build_images() {
    log_info "Building Content Finder Docker image..."
    docker compose -f $COMPOSE_FILE build content-finder
    log_info "Docker image built successfully"
}

start_services() {
    log_info "Starting Content Finder Agent..."
    docker compose -f $COMPOSE_FILE up -d content-finder

    # Wait for service to be ready
    log_info "Waiting for Content Finder to be ready..."
    sleep 15

    # Check health
    log_info "Checking service health..."

    if curl -f http://localhost:8080/health &> /dev/null; then
        log_info "✅ Router Agent is healthy"
    else
        log_error "❌ Router Agent is not responding"
    fi

    if curl -f http://localhost:8000/health &> /dev/null; then
        log_info "✅ Content Finder Agent is healthy"
    else
        log_error "❌ Content Finder Agent is not responding"
    fi

    log_info "🌐 Services available at:"
    log_info "   Router Agent (existing): http://localhost:8080"
    log_info "   Content Finder (new): http://localhost:8000"
    log_info "   Health checks: /health on both services"
}

stop_services() {
    log_info "Stopping Content Finder Agent..."
    docker compose -f $COMPOSE_FILE down
    log_info "Content Finder stopped (Router Agent remains running)"
}

restart_services() {
    log_info "Restarting Content Finder Agent..."
    stop_services
    start_services
}

show_logs() {
    log_info "Showing Content Finder logs..."
    docker compose -f $COMPOSE_FILE logs -f content-finder
}

show_status() {
    log_info "Service status:"
    docker compose -f $COMPOSE_FILE ps

    echo ""
    log_info "Health checks:"

    if curl -f http://localhost:8080/health &> /dev/null; then
        echo "✅ Router Agent (existing): Healthy"
    else
        echo "❌ Router Agent (existing): Not responding"
    fi

    if curl -f http://localhost:8000/health &> /dev/null; then
        echo "✅ Content Finder: Healthy"
    else
        echo "❌ Content Finder: Not responding"
    fi
}

test_workflow() {
    log_info "Testing complete workflow..."

    # Test data
    TEST_PAYLOAD='{"terms": ["meilleure souris gaming 2025"]}'

    log_info "Sending test request to Content Finder..."

    response=$(curl -s -X POST "http://localhost:8000/content-finder" \
         -H "Content-Type: application/json" \
         -d "$TEST_PAYLOAD")

    if [ $? -eq 0 ]; then
        log_info "✅ Workflow test completed"
        echo "Response preview:"
        echo "$response" | head -20

        # Check if router was called
        if echo "$response" | grep -q "router_response"; then
            log_info "✅ Router Agent was successfully called"
        else
            log_warn "⚠️ Router response not found in output"
        fi
    else
        log_error "❌ Workflow test failed"
    fi
}

cleanup() {
    log_info "Cleaning up Content Finder resources..."
    docker compose -f $COMPOSE_FILE down -v --remove-orphans
    docker system prune -f
    log_info "Cleanup completed (Router Agent untouched)"
}

show_help() {
    cat << EOF
Content Finder Agent Deployment Script

Usage: ./deploy.sh [COMMAND]

Commands:
    build       Build Content Finder Docker image
    start       Start Content Finder service
    stop        Stop Content Finder service
    restart     Restart Content Finder service
    logs        Show Content Finder logs
    status      Show service status
    test        Test the complete workflow
    cleanup     Stop and cleanup Docker resources
    help        Show this help message

Prerequisites:
    - Router Agent must be running on port 8080
    - .env file with API keys configured

Examples:
    ./deploy.sh build       # Build the image
    ./deploy.sh start       # Start the service
    ./deploy.sh test        # Test workflow
    ./deploy.sh logs        # View logs

Services will be available at:
    Content Finder: http://localhost:8000
    Router Agent:   http://localhost:8080 (existing)
EOF
}

# Main script
case "${1:-help}" in
    build)
        check_requirements
        build_images
        ;;
    start)
        check_requirements
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    test)
        test_workflow
        ;;
    cleanup)
        cleanup
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac