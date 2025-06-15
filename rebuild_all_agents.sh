#!/bin/bash

# Complete rebuild script for all content agents
# Usage: ./rebuild_all_agents.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_blue() {
    echo -e "${BLUE}[BUILD]${NC} $1"
}

# Configuration
SERVICES=(
    "content-finder:8000:agents-content-finder"
    "router-agent:8080:router-agent"
    "rewriter-agent:8082:rewriter-agent"
)

log_info "🚀 Starting complete rebuild process for all content agents..."
echo "Services to rebuild:"
for service in "${SERVICES[@]}"; do
    IFS=':' read -r name port path <<< "$service"
    echo "  - $name (port $port) from $path"
done
echo ""

# Function to stop and remove container
cleanup_container() {
    local container_name=$1
    log_info "🛑 Stopping container: $container_name"
    docker stop "$container_name" 2>/dev/null || echo "Container $container_name not running"

    log_info "🗑️ Removing container: $container_name"
    docker rm "$container_name" 2>/dev/null || echo "Container $container_name not found"
}

# Function to remove image
cleanup_image() {
    local image_name=$1
    log_info "🗑️ Removing image: $image_name"
    docker rmi "$image_name" 2>/dev/null || echo "Image $image_name not found"
}

# Stop and remove all containers
log_info "🧹 Cleaning up existing containers..."
cleanup_container "agents-agents-content-finder-content-finder-1"
cleanup_container "router-agent-router-agent-1"
cleanup_container "deployment-rewriter-agent-1"

# Remove all images
log_info "🧹 Cleaning up existing images..."
cleanup_image "agents-agents-content-finder-content-finder"
cleanup_image "router-agent-router-agent"
cleanup_image "deployment-rewriter-agent"

# Clean up dangling images
log_info "🧹 Cleaning up dangling images..."
docker image prune -f

# Create network if it doesn't exist
log_info "🌐 Creating content-agents network..."
docker network create content-agents 2>/dev/null || echo "Network content-agents already exists"

# Build and start rewriter-agent first (dependency)
log_blue "🔨 Building rewriter-agent..."
cd services/rewriter-agent/deployment
docker compose build --no-cache
log_info "✅ Rewriter-agent built successfully"

log_info "🚀 Starting rewriter-agent..."
docker compose up -d
log_info "✅ Rewriter-agent started"

# Wait for rewriter to be ready
log_info "⏳ Waiting for rewriter-agent to be ready..."
sleep 20

# Check rewriter health
log_info "🏥 Checking rewriter-agent health..."
max_attempts=12
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:8082/health &> /dev/null; then
        log_info "✅ Rewriter-agent is healthy"
        break
    else
        log_warn "⚠️ Rewriter-agent not ready, attempt $attempt/$max_attempts..."
        sleep 5
        ((attempt++))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    log_error "❌ Rewriter-agent failed to start properly"
    exit 1
fi

# Build and start router-agent
log_blue "🔨 Building router-agent..."
cd ../../router-agent
docker compose build --no-cache
log_info "✅ Router-agent built successfully"

log_info "🚀 Starting router-agent..."
docker compose up -d
log_info "✅ Router-agent started"

# Wait for router to be ready
log_info "⏳ Waiting for router-agent to be ready..."
sleep 15

# Check router health
log_info "🏥 Checking router-agent health..."
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:8080/health &> /dev/null; then
        log_info "✅ Router-agent is healthy"
        break
    else
        log_warn "⚠️ Router-agent not ready, attempt $attempt/$max_attempts..."
        sleep 5
        ((attempt++))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    log_error "❌ Router-agent failed to start properly"
    exit 1
fi

# Build and start content-finder
log_blue "🔨 Building content-finder..."
cd ../agents-content-finder
docker compose build --no-cache
log_info "✅ Content-finder built successfully"

log_info "🚀 Starting content-finder..."
docker compose up -d
log_info "✅ Content-finder started"

# Wait for content-finder to be ready
log_info "⏳ Waiting for content-finder to be ready..."
sleep 15

# Check content-finder health
log_info "🏥 Checking content-finder health..."
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -f http://localhost:8000/health &> /dev/null; then
        log_info "✅ Content-finder is healthy"
        break
    else
        log_warn "⚠️ Content-finder not ready, attempt $attempt/$max_attempts..."
        sleep 5
        ((attempt++))
    fi
done

if [ $attempt -gt $max_attempts ]; then
    log_error "❌ Content-finder failed to start properly"
    exit 1
fi

# Final health check for all services
log_info "🏥 Final health check for all services..."
echo ""

services_status=()

# Check content-finder
if curl -f http://localhost:8000/health &> /dev/null; then
    log_info "✅ Content-finder (port 8000): HEALTHY"
    services_status+=("content-finder:OK")
else
    log_error "❌ Content-finder (port 8000): UNHEALTHY"
    services_status+=("content-finder:FAIL")
fi

# Check router-agent
if curl -f http://localhost:8080/health &> /dev/null; then
    log_info "✅ Router-agent (port 8080): HEALTHY"
    services_status+=("router-agent:OK")
else
    log_error "❌ Router-agent (port 8080): UNHEALTHY"
    services_status+=("router-agent:FAIL")
fi

# Check rewriter-agent
if curl -f http://localhost:8082/health &> /dev/null; then
    log_info "✅ Rewriter-agent (port 8082): HEALTHY"
    services_status+=("rewriter-agent:OK")
else
    log_error "❌ Rewriter-agent (port 8082): UNHEALTHY"
    services_status+=("rewriter-agent:FAIL")
fi

echo ""
log_info "📋 Container status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(content-finder|router-agent|rewriter-agent|NAMES)"

echo ""
log_info "🌐 Service endpoints:"
echo "  📍 Content-finder: http://localhost:8000"
echo "  📍 Content-finder health: http://localhost:8000/health"
echo "  📍 Router-agent: http://localhost:8080"
echo "  📍 Router-agent health: http://localhost:8080/health"
echo "  📍 Rewriter-agent: http://localhost:8082"
echo "  📍 Rewriter-agent health: http://localhost:8082/health"

echo ""
log_info "🔗 Workflow chain:"
echo "  Content-finder → Router-agent → Rewriter-agent"
echo "      (8000)    →     (8080)    →     (8082)"

# Check if all services are healthy
all_healthy=true
for status in "${services_status[@]}"; do
    if [[ $status == *":FAIL" ]]; then
        all_healthy=false
        break
    fi
done

echo ""
if [ "$all_healthy" = true ]; then
    log_info "🎉 All services are healthy and ready!"
    log_info "💡 You can now test the complete workflow by sending requests to content-finder"
else
    log_error "⚠️ Some services are not healthy. Check the logs above."
    echo ""
    log_info "🔍 To check logs:"
    echo "  docker logs <container-name>"
    echo ""
    log_info "📋 Available containers:"
    docker ps --format "table {{.Names}}" | grep -E "(content-finder|router-agent|rewriter-agent)"
fi

echo ""
log_info "🏁 Rebuild complete!"