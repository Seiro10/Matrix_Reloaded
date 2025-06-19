#!/bin/bash

# Complete rebuild script for all content agents using unified docker-compose.yaml
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

# Check if docker-compose.yaml exists
if [ ! -f "docker-compose.yaml" ]; then
    log_error "❌ docker-compose.yaml not found in current directory!"
    log_info "Please run this script from the root directory containing docker-compose.yaml"
    exit 1
fi

log_info "🚀 Starting complete rebuild process using unified docker-compose.yaml..."

# Services defined in docker-compose.yaml
SERVICES=(
    "content-finder:8000"
    "router-agent:8080"
    "rewriter-agent:8082"
    "metadata-generator:8084"
)

echo "Services to rebuild:"
for service in "${SERVICES[@]}"; do
    IFS=':' read -r name port <<< "$service"
    echo "  - $name (port $port)"
done
echo ""

# Stop all services
log_info "🛑 Stopping all services..."
docker compose down

# Remove all related containers (cleanup any orphaned containers)
log_info "🧹 Cleaning up any orphaned containers..."
docker stop deployment-rewriter-agent-1 2>/dev/null || true
docker stop router-agent-router-agent-1 2>/dev/null || true
docker stop agents-content-finder-content-finder-1 2>/dev/null || true
docker stop metadata-generator-metadata-generator-1 2>/dev/null || true
docker stop matrix_reloaded-metadata-agent-1 2>/dev/null || true
docker rm deployment-rewriter-agent-1 2>/dev/null || true
docker rm router-agent-router-agent-1 2>/dev/null || true
docker rm agents-content-finder-content-finder-1 2>/dev/null || true
docker rm metadata-generator-metadata-generator-1 2>/dev/null || true
docker rm matrix_reloaded-metadata-agent-1 2>/dev/null || true

# Additional cleanup for any containers using ports we need
log_info "🔍 Checking for port conflicts..."
for port in 8000 8080 8082 8084; do
  CONTAINER_ID=$(docker ps -q --filter publish=$port)
  if [ ! -z "$CONTAINER_ID" ]; then
    log_warn "Found container using port $port: $CONTAINER_ID"
    log_info "Stopping and removing container..."
    docker stop $CONTAINER_ID 2>/dev/null || true
    docker rm $CONTAINER_ID 2>/dev/null || true
  fi
done

# Remove all images
log_info "🗑️ Removing existing images..."
docker compose down --rmi all 2>/dev/null || true

# Additional cleanup for any remaining images
docker rmi deployment-rewriter-agent 2>/dev/null || true
docker rmi router-agent-router-agent 2>/dev/null || true
docker rmi agents-content-finder-content-finder 2>/dev/null || true
docker rmi metadata-generator 2>/dev/null || true

# Clean up dangling images and volumes
log_info "🧹 Cleaning up dangling resources..."
docker image prune -f
docker volume prune -f

# Build all services
log_blue "🔨 Building all services..."
docker compose build --no-cache

# Start all services
log_info "🚀 Starting all services..."
docker compose up -d

# Wait for services to be ready
log_info "⏳ Waiting for services to be ready..."
sleep 30

# Function to check service health
check_service_health() {
    local service_name=$1
    local port=$2
    local max_attempts=12
    local attempt=1

    log_info "🏥 Checking $service_name health..."

    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:$port/health &> /dev/null; then
            log_info "✅ $service_name is healthy"
            return 0
        else
            log_warn "⚠️ $service_name not ready, attempt $attempt/$max_attempts..."
            sleep 5
            ((attempt++))
        fi
    done

    log_error "❌ $service_name failed to start properly"
    return 1
}

# Check health of all services
services_status=()
all_healthy=true

# Check rewriter-agent (foundation service)
if check_service_health "rewriter-agent" "8082"; then
    services_status+=("rewriter-agent:OK")
else
    services_status+=("rewriter-agent:FAIL")
    all_healthy=false
fi

# Check metadata-generator
if check_service_health "metadata-generator" "8084"; then
    services_status+=("metadata-generator:OK")
else
    services_status+=("metadata-generator:FAIL")
    all_healthy=false
fi

# Check router-agent (middle service)
if check_service_health "router-agent" "8080"; then
    services_status+=("router-agent:OK")
else
    services_status+=("router-agent:FAIL")
    all_healthy=false
fi

# Check content-finder (top service)
if check_service_health "content-finder" "8000"; then
    services_status+=("content-finder:OK")
else
    services_status+=("content-finder:FAIL")
    all_healthy=false
fi

# Show results
echo ""
log_info "📋 Container status:"
docker compose ps

echo ""
log_info "🌐 Service endpoints:"
echo "  📍 Content-finder: http://localhost:8000"
echo "  📍 Content-finder health: http://localhost:8000/health"
echo "  📍 Router-agent: http://localhost:8080"
echo "  📍 Router-agent health: http://localhost:8080/health"
echo "  📍 Rewriter-agent: http://localhost:8082"
echo "  📍 Rewriter-agent health: http://localhost:8082/health"
echo "  📍 Metadata-generator: http://localhost:8084"
echo "  📍 Metadata-generator health: http://localhost:8084/health"

echo ""
log_info "🔗 Service communication (internal Docker network):"
echo "  content-finder → http://router-agent:8080"
echo "  router-agent → http://metadata-generator:8084"
echo "  metadata-generator → http://copywriter-agent:8083 (future)"

echo ""
log_info "🌐 Network information:"
docker network ls | grep content-agents || log_warn "content-agents network not found"

# Show service status summary
echo ""
log_info "📊 Service status summary:"
for status in "${services_status[@]}"; do
    IFS=':' read -r service result <<< "$status"
    if [[ $result == "OK" ]]; then
        log_info "  ✅ $service: HEALTHY"
    else
        log_error "  ❌ $service: UNHEALTHY"
    fi
done

echo ""
if [ "$all_healthy" = true ]; then
    log_info "🎉 All services are healthy and ready!"
    echo ""
    log_info "💡 Test the complete workflow:"
    echo "  1. Send a request to content-finder: http://localhost:8000"
    echo "  2. Content-finder will automatically call router-agent"
    echo "  3. Router-agent will call metadata-generator"
    echo "  4. Metadata-generator will process and later call copywriter (when implemented)"
    echo ""
    log_info "🔧 Useful commands:"
    echo "  View logs: docker-compose logs [service-name]"
    echo "  Stop all: docker-compose down"
    echo "  Restart: docker-compose restart [service-name]"
else
    log_error "⚠️ Some services are not healthy. Check the logs."
    echo ""
    log_info "🔍 To check logs:"
    echo "  docker-compose logs content-finder"
    echo "  docker-compose logs router-agent"
    echo "  docker-compose logs rewriter-agent"
    echo "  docker-compose logs metadata-generator"
    echo ""
    log_info "🔧 To restart a specific service:"
    echo "  docker-compose restart [service-name]"
fi

echo ""
log_info "🏁 Rebuild complete!"

# Optional: Show environment check
echo ""
log_info "🔍 Environment check:"
if [ -f ".env" ]; then
    log_info "  ✅ .env file found"
else
    log_warn "  ⚠️ .env file not found - make sure environment variables are set"
fi

# Check if required environment variables are mentioned in docker-compose
required_vars=("ANTHROPIC_API_KEY" "WORDPRESS_API_URL" "WORDPRESS_USERNAME" "WORDPRESS_PASSWORD")
missing_vars=()

for var in "${required_vars[@]}"; do
    if ! grep -q "$var" docker-compose.yaml; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -eq 0 ]; then
    log_info "  ✅ All required environment variables are referenced in docker-compose.yaml"
else
    log_warn "  ⚠️ Some environment variables might be missing:"
    for var in "${missing_vars[@]}"; do
        echo "    - $var"
    done
fi