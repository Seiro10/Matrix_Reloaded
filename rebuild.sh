#!/bin/bash

# Complete rebuild script for router-agent and agents-content-finder
# Usage: ./rebuild.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_info "🔄 Starting complete rebuild process..."

# Stop containers
log_info "🛑 Stopping containers..."
docker stop router-agent-router-agent-1 2>/dev/null || echo "Container router-agent-router-agent-1 not running"
docker stop agents-agents-content-finder-agents-content-finder-1 2>/dev/null || echo "Container agents-agents-content-finder-agents-content-finder-1 not running"

# Remove containers
log_info "🗑️ Removing containers..."
docker rm router-agent-router-agent-1 2>/dev/null || echo "Container router-agent-router-agent-1 not found"
docker rm agents-agents-content-finder-agents-content-finder-1 2>/dev/null || echo "Container agents-agents-content-finder-agents-content-finder-1 not found"

# Remove images
log_info "🗑️ Removing images..."
docker rmi router-agent-router-agent 2>/dev/null || echo "Image router-agent-router-agent not found"
docker rmi agents-agents-content-finder-agents-content-finder 2>/dev/null || echo "Image agents-agents-content-finder-agents-content-finder not found"

# Clean up dangling images
log_info "🧹 Cleaning up dangling images..."
docker image prune -f

# Rebuild router-agent
log_info "🔨 Building router-agent..."
cd services/router-agent
docker compose build --no-cache
log_info "✅ Router-agent built successfully"

# Rebuild agents-content-finder
log_info "🔨 Building agents-content-finder..."
cd ../agents-content-finder
docker compose build --no-cache
log_info "✅ Content-finder built successfully"

# Start router-agent
log_info "🚀 Starting router-agent..."
cd ../router-agent
docker compose up -d
log_info "✅ Router-agent started"

# Start agents-content-finder
log_info "🚀 Starting agents-content-finder..."
cd ../agents-content-finder
docker compose up -d
log_info "✅ Content-finder started"

# Wait for services to be ready
log_info "⏳ Waiting for services to be ready..."
sleep 15

# Check router-agent health
log_info "🏥 Checking router-agent health..."
if curl -f http://localhost:8080/health &> /dev/null; then
    log_info "✅ Router-agent is healthy"
else
    log_error "❌ Router-agent is not responding"
fi

# Check agents-content-finder health
log_info "🏥 Checking agents-content-finder health..."
if curl -f http://localhost:8001/health &> /dev/null; then
    log_info "✅ Content-finder is healthy"
else
    log_error "❌ Content-finder is not responding"
fi

# Show running containers
log_info "📋 Running containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

log_info "🎉 Rebuild complete!"
log_info "🌐 Router-agent: http://localhost:8080"
log_info "🌐 Content-finder: http://localhost:8081"