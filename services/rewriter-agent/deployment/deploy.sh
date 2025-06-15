#!/bin/bash

# Rewriter Agent Deployment Script
# Usage: ./deploy.sh [build|start|stop|restart|logs|status|test]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="rewriter-agent"
COMPOSE_FILE="docker-compose.yml"
PORT=8082

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

log_blue() {
    echo -e "${BLUE}[DEPLOY]${NC} $1"
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

    # Check .env file
    if [ ! -f .env ]; then
        log_warn ".env file not found. Creating from template..."
        if [ -f .env.example ]; then
            cp .env.example .env
            log_warn "Please edit .env file with your API keys and WordPress credentials before running"
            exit 1
        else
            log_error "No .env.example file found. Please create .env with required variables"
            exit 1
        fi
    fi

    # Fix line endings in .env file (Windows compatibility)
    if command -v dos2unix &> /dev/null; then
        dos2unix .env 2>/dev/null
    else
        # Use sed to remove carriage returns
        sed -i 's/\r$//' .env 2>/dev/null || true
    fi

    # Validate required environment variables
    source .env
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        log_error "ANTHROPIC_API_KEY is required in .env file"
        exit 1
    fi

    if [ -z "$WORDPRESS_API_URL" ]; then
        log_error "WORDPRESS_API_URL is required in .env file"
        exit 1
    fi

    if [ -z "$WORDPRESS_USERNAME" ]; then
        log_error "WORDPRESS_USERNAME is required in .env file"
        exit 1
    fi

    if [ -z "$WORDPRESS_PASSWORD" ]; then
        log_error "WORDPRESS_PASSWORD is required in .env file"
        exit 1
    fi

    log_info "Requirements check passed"
}

create_directories() {
    log_info "Creating necessary directories..."
    mkdir -p output logs temp
    log_info "Directories created"
}

create_network() {
    log_info "Creating Docker network..."
    if ! docker network ls | grep -q "content-agents"; then
        docker network create content-agents
        log_info "Created content-agents network"
    else
        log_info "content-agents network already exists"
    fi
}

build_image() {
    log_blue "Building Rewriter Agent Docker image..."
    docker compose -f $COMPOSE_FILE build
    log_info "Docker image built successfully"
}

start_service() {
    log_blue "Starting Rewriter Agent service..."
    docker compose -f $COMPOSE_FILE up -d

    # Wait for service to be ready
    log_info "Waiting for service to be ready..."
    sleep 15

    # Check health
    max_attempts=12
    attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:${PORT}/health &> /dev/null; then
            log_info "✅ Rewriter Agent is running successfully!"
            log_info "🌐 API available at: http://localhost:${PORT}"
            log_info "📊 Health check: http://localhost:${PORT}/health"
            log_info "📋 Active sessions: http://localhost:${PORT}/rewrite/sessions"
            echo ""
            log_blue "Available endpoints:"
            echo "  POST /rewrite/csv     - Rewrite article from CSV file"
            echo "  POST /rewrite/json    - Rewrite article from JSON data"
            echo "  GET  /rewrite/status/{session_id} - Check rewrite status"
            echo "  GET  /rewrite/sessions - List active sessions"
            return 0
        else
            log_warn "Service not ready, attempt $attempt/$max_attempts..."
            sleep 5
            ((attempt++))
        fi
    done

    log_error "❌ Service is not responding after $max_attempts attempts. Check logs with: ./deploy.sh logs"
    exit 1
}

stop_service() {
    log_blue "Stopping Rewriter Agent service..."
    docker compose -f $COMPOSE_FILE down
    log_info "Service stopped"
}

restart_service() {
    log_blue "Restarting Rewriter Agent service..."
    stop_service
    start_service
}

show_logs() {
    log_info "Showing service logs..."
    docker compose -f $COMPOSE_FILE logs -f $SERVICE_NAME
}

show_status() {
    log_info "Service status:"
    docker compose -f $COMPOSE_FILE ps

    echo ""
    log_info "Health check:"
    if curl -f http://localhost:${PORT}/health &> /dev/null; then
        echo "✅ Service is healthy"

        # Get active sessions
        log_info "Active sessions:"
        curl -s http://localhost:${PORT}/rewrite/sessions | python3 -m json.tool 2>/dev/null || echo "Could not fetch sessions"
    else
        echo "❌ Service is not responding"
    fi
}

run_tests() {
    log_blue "Running Rewriter Agent tests..."

    # Check if service is running
    if ! curl -f http://localhost:${PORT}/health &> /dev/null; then
        log_warn "Service is not running. Starting service first..."
        start_service
    fi

    # Run test script
    if [ -f "test_rewriter_agent.py" ]; then
        python3 test_rewriter_agent.py
    else
        log_error "Test script not found. Please ensure test_rewriter_agent.py exists."
        exit 1
    fi
}

cleanup() {
    log_blue "Cleaning up Docker resources..."
    docker compose -f $COMPOSE_FILE down -v --remove-orphans
    docker system prune -f
    log_info "Cleanup completed"
}

show_help() {
    cat << EOF
${BLUE}Rewriter Agent Deployment Script${NC}

Usage: ./deploy.sh [COMMAND]

Commands:
    build       Build Docker image
    start       Start the service
    stop        Stop the service
    restart     Restart the service
    logs        Show service logs
    status      Show service status
    test        Run integration tests
    cleanup     Stop and cleanup Docker resources
    help        Show this help message

Examples:
    ./deploy.sh build       # Build the image
    ./deploy.sh start       # Start the service
    ./deploy.sh test        # Run tests
    ./deploy.sh logs        # View logs
    ./deploy.sh status      # Check if running

Service will be available at: http://localhost:${PORT}

Required environment variables in .env:
    ANTHROPIC_API_KEY       - Anthropic API key for LLM
    WORDPRESS_API_URL       - WordPress site API URL
    WORDPRESS_USERNAME      - WordPress username
    WORDPRESS_PASSWORD      - WordPress password

EOF
}

# Main script
case "${1:-help}" in
    build)
        check_requirements
        create_directories
        create_network
        build_image
        ;;
    start)
        check_requirements
        create_directories
        create_network
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    test)
        run_tests
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