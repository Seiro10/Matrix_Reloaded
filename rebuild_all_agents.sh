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
    "rewriter-main:8085"
    "copywriter-agent:8083"
    "copywriter-worker:N/A"
    "metadata-generator:8084"
    "rss-agent:8086"
    "rss-worker:N/A"
    "copywriter-redis:6379"
    "rss-redis:6379"
)

echo "Services to rebuild:"
for service in "${SERVICES[@]}"; do
    IFS=':' read -r name port <<< "$service"
    if [ "$port" = "N/A" ]; then
        echo "  - $name (worker/background service)"
    else
        echo "  - $name (port $port)"
    fi
done
echo ""

log_info "🛑 Stopping all services..."
docker compose down

# Stop RSS agent if it exists
if [ -f "services/rss-agent/docker-compose.yml" ]; then
    log_info "🛑 Stopping RSS agent..."
    cd services/rss-agent
    docker compose down
    cd ../..
fi

# Force stop all containers that might be using our networks
log_info "🧹 Force stopping all related containers..."
docker ps -a --format "table {{.Names}}" | grep -E "(content-finder|router-agent|copywriter|metadata|rewriter|rss)" | xargs -r docker stop 2>/dev/null || true
docker ps -a --format "table {{.Names}}" | grep -E "(content-finder|router-agent|copywriter|metadata|rewriter|rss)" | xargs -r docker rm 2>/dev/null || true

# Remove containers by pattern
docker rm -f $(docker ps -aq --filter "name=content-finder") 2>/dev/null || true
docker rm -f $(docker ps -aq --filter "name=router-agent") 2>/dev/null || true
docker rm -f $(docker ps -aq --filter "name=copywriter") 2>/dev/null || true
docker rm -f $(docker ps -aq --filter "name=metadata") 2>/dev/null || true
docker rm -f $(docker ps -aq --filter "name=rewriter") 2>/dev/null || true
docker rm -f $(docker ps -aq --filter "name=rss") 2>/dev/null || true

# Check for containers still using networks and force remove them
log_info "🔍 Checking for containers using our networks..."
for network in "matrix_reloaded_content-agents" "content-agents" "router-agent_default" "agents-content-finder_default" "agents-content-finder_agent_network"; do
    if docker network inspect $network >/dev/null 2>&1; then
        log_info "Disconnecting all containers from network: $network"
        # Get container IDs connected to this network
        CONTAINER_IDS=$(docker network inspect $network --format '{{range $id, $v := .Containers}}{{printf "%s " $id}}{{end}}' 2>/dev/null || true)
        if [ ! -z "$CONTAINER_IDS" ]; then
            for container_id in $CONTAINER_IDS; do
                docker network disconnect -f $network $container_id 2>/dev/null || true
            done
        fi
    fi
done

# Additional cleanup for any orphaned containers
docker stop deployment-rewriter-agent-1 deployment-rewriter-main-1 router-agent-router-agent-1 agents-content-finder-content-finder-1 agents-copywriter-copywriter-agent-1 metadata-generator-metadata-generator-1 matrix_reloaded-metadata-agent-1 2>/dev/null || true
docker rm deployment-rewriter-agent-1 deployment-rewriter-main-1 router-agent-router-agent-1 agents-content-finder-content-finder-1 agents-copywriter-copywriter-agent-1 metadata-generator-metadata-generator-1 matrix_reloaded-metadata-agent-1 2>/dev/null || true

# Remove all networks
log_info "🌐 Removing all related networks..."
docker network rm matrix_reloaded_content-agents content-agents router-agent_default agents-content-finder_default agents-content-finder_agent_network agents-copywriter_default metadata-generator_default rss-agent_rss_network 2>/dev/null || true

# Additional cleanup for port conflicts
log_info "🔍 Checking for port conflicts..."
for port in 8000 8080 8083 8084 8085 8086 6379; do
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
docker rmi deployment-rewriter-agent deployment-rewriter-main router-agent-router-agent agents-content-finder-content-finder agents-copywriter-copywriter-agent metadata-generator matrix_reloaded-rss-agent 2>/dev/null || true

# Clean up dangling images and volumes
log_info "🧹 Cleaning up dangling resources..."
docker image prune -f
docker volume prune -f
docker network prune -f

# Build all services
log_blue "🔨 Building all services..."
docker compose build --no-cache

# Start infrastructure services first (Redis instances)
log_info "🚀 Starting infrastructure services (Redis)..."
docker compose up -d copywriter-redis rss-redis

# Wait for Redis to be ready
log_info "⏳ Waiting for Redis services to be ready..."
sleep 10

# Start core services
log_info "🚀 Starting core services..."
docker compose up -d copywriter-agent rewriter-main

# Wait for core services
log_info "⏳ Waiting for core services to be ready..."
sleep 20

# Start workers and dependent services
log_info "🚀 Starting workers and dependent services..."
docker compose up -d copywriter-worker metadata-generator router-agent

# Wait for dependent services
log_info "⏳ Waiting for dependent services to be ready..."
sleep 20

# Start remaining services
log_info "🚀 Starting remaining services..."
docker compose up -d rss-agent rss-worker content-finder

# Wait for all services to be ready
log_info "⏳ Waiting for all services to be ready..."
sleep 30

# Function to check service health
check_service_health() {
    local service_name=$1
    local port=$2
    local max_attempts=12
    local attempt=1

    if [ "$port" = "N/A" ]; then
        log_info "⚠️ $service_name is a worker service (no health check)"
        return 0
    fi

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

# Check services with health endpoints
for service_info in "${SERVICES[@]}"; do
    IFS=':' read -r service_name port <<< "$service_info"

    if [ "$port" != "N/A" ] && [ "$port" != "6379" ]; then  # Skip Redis ports
        if check_service_health "$service_name" "$port"; then
            services_status+=("$service_name:OK")
        else
            services_status+=("$service_name:FAIL")
            all_healthy=false
        fi
    else
        services_status+=("$service_name:WORKER")
    fi
done

# Check Redis connectivity
log_info "🔍 Checking Redis connectivity..."
if docker exec matrix_reloaded-copywriter-redis-1 redis-cli ping >/dev/null 2>&1; then
    services_status+=("copywriter-redis:OK")
    log_info "✅ Copywriter Redis is healthy"
else
    services_status+=("copywriter-redis:FAIL")
    log_error "❌ Copywriter Redis is unhealthy"
    all_healthy=false
fi

if docker exec matrix_reloaded-rss-redis-1 redis-cli ping >/dev/null 2>&1; then
    services_status+=("rss-redis:OK")
    log_info "✅ RSS Redis is healthy"
else
    services_status+=("rss-redis:FAIL")
    log_error "❌ RSS Redis is unhealthy"
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
echo "  📍 Rewriter-main: http://localhost:8085"
echo "  📍 Rewriter-main health: http://localhost:8085/health"
echo "  📍 Copywriter-agent: http://localhost:8083"
echo "  📍 Copywriter-agent health: http://localhost:8083/health"
echo "  📍 Metadata-generator: http://localhost:8084"
echo "  📍 Metadata-generator health: http://localhost:8084/health"
echo "  📍 RSS-agent: http://localhost:8086"
echo "  📍 RSS-agent health: http://localhost:8086/health"

echo ""
log_info "🔗 Service communication (internal Docker network):"
echo "  content-finder → http://router-agent:8080"
echo "  router-agent → http://rewriter-main:8085"
echo "  router-agent → http://copywriter-agent:8083"
echo "  metadata-generator → http://copywriter-agent:8083"
echo "  rss-agent → http://router-agent:8080"

echo ""
log_info "⚙️ Queue Systems:"
echo "  📊 Copywriter Celery: redis://copywriter-redis:6379/0"
echo "  📊 RSS Celery: redis://rss-redis:6379/0"

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
    elif [[ $result == "WORKER" ]]; then
        log_info "  ⚙️ $service: WORKER SERVICE"
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
    echo "  3. Router-agent will call copywriter-agent (with queue system)"
    echo "  4. Copywriter-agent will process using Celery workers"
    echo "  5. Metadata-generator can call copywriter-agent if needed"
    echo "  6. RSS-agent will process articles with its own queue system"
    echo ""
    log_info "🔧 Useful commands:"
    echo "  View logs: docker compose logs [service-name]"
    echo "  View worker logs: docker compose logs copywriter-worker"
    echo "  Stop all: docker compose down"
    echo "  Restart: docker compose restart [service-name]"
    echo "  Monitor queues: docker compose exec copywriter-redis redis-cli monitor"
else
    log_error "⚠️ Some services are not healthy. Check the logs."
    echo ""
    log_info "🔍 To check logs:"
    echo "  docker compose logs content-finder"
    echo "  docker compose logs router-agent"
    echo "  docker compose logs rewriter-main"
    echo "  docker compose logs copywriter-agent"
    echo "  docker compose logs copywriter-worker"
    echo "  docker compose logs metadata-generator"
    echo "  docker compose logs rss-agent"
    echo "  docker compose logs rss-worker"
    echo ""
    log_info "🔧 To restart a specific service:"
    echo "  docker compose restart [service-name]"
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
required_vars=("ANTHROPIC_API_KEY" "OPENAI_API_KEY" "TAVILY_API_KEY" "WORDPRESS_API_URL" "WORDPRESS_USERNAME" "WORDPRESS_PASSWORD")
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

echo ""
log_info "🎯 Queue System Status:"
echo "  📊 Check Copywriter queue: docker compose exec copywriter-redis redis-cli llen copywriter"
echo "  📊 Check RSS queue: docker compose exec rss-redis redis-cli llen scraping"
echo "  📊 Monitor all queues: docker compose logs copywriter-worker rss-worker"