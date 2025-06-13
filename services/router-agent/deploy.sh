#!/bin/bash

# Router Agent Deployment Script
# Usage: ./deploy.sh [build|start|stop|restart|logs|status]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="router-agent"
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

    # Check .env file
    if [ ! -f .env ]; then
        log_warn ".env file not found. Creating from template..."
        if [ -f .env.example ]; then
            cp .env.example .env
            log_warn "Please edit .env file with your API keys before running"
            exit 1
        else
            log_error "No .env.example file found. Please create .env with required variables"
            exit 1
        fi
    fi

    log_info "Requirements check passed"
}

create_directories() {
    log_info "Creating necessary directories..."
    mkdir -p data output logs
    log_info "Directories created"
}

build_image() {
    log_info "Building Docker image..."
    docker compose -f $COMPOSE_FILE build
    log_info "Docker image built successfully"
}

start_service() {
    log_info "Starting Router Agent service..."
    docker compose -f $COMPOSE_FILE up -d

    # Wait for service to be ready
    log_info "Waiting for service to be ready..."
    sleep 10

    # Check health
    if curl -f http://localhost:8080/health &> /dev/null; then
        log_info "✅ Router Agent is running successfully!"
        log_info "🌐 API available at: http://localhost:8080"
        log_info "📊 Health check: http://localhost:8080/health"
        log_info "📋 Available sites: http://localhost:8080/sites"
    else
        log_error "❌ Service is not responding. Check logs with: ./deploy.sh logs"
        exit 1
    fi
}

stop_service() {
    log_info "Stopping Router Agent service..."
    docker compose -f $COMPOSE_FILE down
    log_info "Service stopped"
}

restart_service() {
    log_info "Restarting Router Agent service..."
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
    if curl -f http://localhost:8080/health &> /dev/null; then
        echo "✅ Service is healthy"
    else
        echo "❌ Service is not responding"
    fi
}

cleanup() {
    log_info "Cleaning up Docker resources..."
    docker compose -f $COMPOSE_FILE down -v --remove-orphans
    docker system prune -f
    log_info "Cleanup completed"
}

show_help() {
    cat << EOF
Router Agent Deployment Script

Usage: ./deploy.sh [COMMAND]

Commands:
    build       Build Docker image
    start       Start the service
    stop        Stop the service
    restart     Restart the service
    logs        Show service logs
    status      Show service status
    cleanup     Stop and cleanup Docker resources
    help        Show this help message

Examples:
    ./deploy.sh build       # Build the image
    ./deploy.sh start       # Start the service
    ./deploy.sh logs        # View logs
    ./deploy.sh status      # Check if running

Service will be available at: http://localhost:8080
EOF
}

# Main script
case "${1:-help}" in
    build)
        check_requirements
        create_directories
        build_image
        ;;
    start)
        check_requirements
        create_directories
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