#!/bin/bash

# Complete rebuild script for RSS Agent with Redis and Celery workers
# Usage: ./rebuild_rss_agent.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

log_purple() {
    echo -e "${PURPLE}[RSS]${NC} $1"
}

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    log_error "❌ docker-compose.yml not found in current directory!"
    log_info "Please run this script from the RSS agent root directory containing docker-compose.yml"
    exit 1
fi

log_purple "🔄 Starting RSS Agent complete rebuild process..."

# Services defined in docker-compose.yml
SERVICES=(
    "rss-agent:8086"
    "redis:6379"
    "celery-scraping:N/A"
    "celery-processing:N/A"
    "celery-uploads:N/A"
    "celery-flower:5555"
)

echo "RSS Agent services to rebuild:"
for service in "${SERVICES[@]}"; do
    IFS=':' read -r name port <<< "$service"
    if [[ $port == "N/A" ]]; then
        echo "  - $name (worker)"
    else
        echo "  - $name (port $port)"
    fi
done
echo ""

# Stop all services
log_info "🛑 Stopping all RSS Agent services..."
docker compose down

# Remove all related containers (cleanup any orphaned containers)
log_info "🧹 Cleaning up RSS Agent containers..."
docker stop rss_agent_main 2>/dev/null || true
docker stop rss_redis 2>/dev/null || true
docker stop rss_celery_scraping 2>/dev/null || true
docker stop rss_celery_processing 2>/dev/null || true
docker stop rss_celery_uploads 2>/dev/null || true
docker stop rss_celery_flower 2>/dev/null || true

docker rm rss_agent_main 2>/dev/null || true
docker rm rss_redis 2>/dev/null || true
docker rm rss_celery_scraping 2>/dev/null || true
docker rm rss_celery_processing 2>/dev/null || true
docker rm rss_celery_uploads 2>/dev/null || true
docker rm rss_celery_flower 2>/dev/null || true

# Additional cleanup for containers using RSS agent ports
log_info "🔍 Checking for RSS Agent port conflicts..."
for port in 8086 6379 5555; do
  CONTAINER_ID=$(docker ps -q --filter publish=$port)
  if [ ! -z "$CONTAINER_ID" ]; then
    CONTAINER_NAME=$(docker ps --format "table {{.Names}}" --filter publish=$port | tail -n +2)
    log_warn "Found container using port $port: $CONTAINER_NAME ($CONTAINER_ID)"
    log_info "Stopping and removing container..."
    docker stop $CONTAINER_ID 2>/dev/null || true
    docker rm $CONTAINER_ID 2>/dev/null || true
  fi
done

# Remove RSS agent images
log_info "🗑️ Removing RSS Agent images..."
docker compose down --rmi all 2>/dev/null || true

# Additional cleanup for RSS agent images
docker rmi rss-agent-rss-agent 2>/dev/null || true
docker rmi rss-agent-celery-scraping 2>/dev/null || true
docker rmi rss-agent-celery-processing 2>/dev/null || true
docker rmi rss-agent-celery-uploads 2>/dev/null || true
docker rmi rss-agent-celery-flower 2>/dev/null || true

# Clean up dangling images and volumes
log_info "🧹 Cleaning up dangling resources..."
docker image prune -f
docker volume prune -f

# Prune RSS-specific networks
log_info "🌐 Cleaning up RSS Agent networks..."
docker network rm rss-agent_rss_network 2>/dev/null || true

# Build all services
log_blue "🔨 Building RSS Agent services..."
docker compose build --no-cache

# Start all services
log_info "🚀 Starting RSS Agent services..."
docker compose up -d

# Wait for services to be ready
log_info "⏳ Waiting for RSS Agent services to initialize..."
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

# Function to check Redis health
check_redis_health() {
    local max_attempts=12
    local attempt=1

    log_info "🏥 Checking Redis health..."

    while [ $attempt -le $max_attempts ]; do
        if docker exec rss_redis redis-cli ping &> /dev/null; then
            log_info "✅ Redis is healthy"
            return 0
        else
            log_warn "⚠️ Redis not ready, attempt $attempt/$max_attempts..."
            sleep 3
            ((attempt++))
        fi
    done

    log_error "❌ Redis failed to start properly"
    return 1
}

# Function to check Celery worker health
check_celery_health() {
    local worker_name=$1
    local max_attempts=8
    local attempt=1

    log_info "🏥 Checking Celery worker: $worker_name..."

    while [ $attempt -le $max_attempts ]; do
        if docker exec rss_celery_scraping celery -A core.queue_manager.celery_app inspect ping &> /dev/null; then
            log_info "✅ Celery workers are responding"
            return 0
        else
            log_warn "⚠️ Celery workers not ready, attempt $attempt/$max_attempts..."
            sleep 5
            ((attempt++))
        fi
    done

    log_error "❌ Celery workers failed to start properly"
    return 1
}

# Function to check Flower health (different approach)
check_flower_health() {
    local max_attempts=8
    local attempt=1

    log_info "🏥 Checking Flower monitoring interface..."

    while [ $attempt -le $max_attempts ]; do
        # Check if Flower web interface is accessible
        if curl -f -s http://localhost:5555/ &> /dev/null; then
            log_info "✅ Flower monitoring interface is accessible"
            return 0
        # Also check if the container is running properly
        elif docker exec rss_celery_flower ps aux | grep flower &> /dev/null; then
            log_info "✅ Flower process is running (web interface may take time)"
            return 0
        else
            log_warn "⚠️ Flower not ready, attempt $attempt/$max_attempts..."
            sleep 5
            ((attempt++))
        fi
    done

    log_warn "⚠️ Flower web interface not accessible, but process may be running"
    return 1
}

# Check health of all services
services_status=()
all_healthy=true

# Check Redis first (dependency for everything)
if check_redis_health; then
    services_status+=("redis:OK")
else
    services_status+=("redis:FAIL")
    all_healthy=false
fi

# Check RSS Agent API
if check_service_health "rss-agent" "8086"; then
    services_status+=("rss-agent:OK")
else
    services_status+=("rss-agent:FAIL")
    all_healthy=false
fi

# Check Flower monitoring (with relaxed criteria)
if check_flower_health; then
    services_status+=("celery-flower:OK")
else
    services_status+=("celery-flower:WARN")
    # Don't mark as unhealthy for Flower issues
fi

# Check Celery workers
if check_celery_health "celery-workers"; then
    services_status+=("celery-workers:OK")
else
    services_status+=("celery-workers:FAIL")
    all_healthy=false
fi

# Show results
echo ""
log_info "📋 RSS Agent container status:"
docker compose ps

echo ""
log_purple "🌐 RSS Agent service endpoints:"
echo "  📍 RSS Agent API: http://localhost:8086"
echo "  📍 RSS Agent health: http://localhost:8086/health"
echo "  📍 Celery Flower monitoring: http://localhost:5555"
echo "  📍 Redis: localhost:6379 (internal)"

echo ""
log_purple "🔗 RSS Agent API endpoints:"
echo "  📌 GET  / - Service info"
echo "  📌 GET  /health - Health check"
echo "  📌 POST /manual-check - Trigger manual scraping"
echo "  📌 POST /scrape/{scraper_name} - Scrape specific site"
echo "  📌 GET  /job/{job_id} - Check job status"
echo "  📌 GET  /stats - Celery statistics"
echo "  📌 GET  /test-s3 - Test S3 connection"

echo ""
log_purple "🔧 RSS Agent internal communication:"
echo "  rss-agent → redis:6379 (queue & cache)"
echo "  celery-workers → redis:6379 (job queue)"
echo "  celery-flower → redis:6379 (monitoring)"

echo ""
log_info "🌐 Network information:"
docker network ls | grep rss_network || log_warn "rss_network not found"

# Show service status summary
echo ""
log_info "📊 RSS Agent service status summary:"
for status in "${services_status[@]}"; do
    IFS=':' read -r service result <<< "$status"
    if [[ $result == "OK" ]]; then
        log_info "  ✅ $service: HEALTHY"
    elif [[ $result == "WARN" ]]; then
        log_warn "  ⚠️ $service: WARNING (may take time to initialize)"
    else
        log_error "  ❌ $service: UNHEALTHY"
    fi
done

echo ""
if [ "$all_healthy" = true ]; then
    log_purple "🎉 RSS Agent is fully operational!"
    echo ""
    log_purple "💡 Test the RSS Agent workflow:"
    echo "  1. Manual scraping: curl -X POST http://localhost:8086/manual-check"
    echo "  2. Test S3 connection: curl http://localhost:8086/test-s3"
    echo "  3. Check specific scraper: curl -X POST http://localhost:8086/scrape/league_of_legends"
    echo "  4. Monitor with Flower: http://localhost:5555"
    echo "  5. View job stats: curl http://localhost:8086/stats"
    echo ""
    log_purple "📰 Available scrapers:"
    echo "  - league_of_legends (League of Legends news)"
    echo ""
    log_purple "🔧 Useful RSS Agent commands:"
    echo "  View logs: docker compose logs [service-name]"
    echo "  View all logs: docker compose logs -f"
    echo "  Stop all: docker compose down"
    echo "  Restart: docker compose restart [service-name]"
    echo "  Scale workers: docker compose up -d --scale celery-processing=3"
else
    log_error "⚠️ Some RSS Agent services are not healthy. Check the logs."
    echo ""
    log_info "🔍 To check RSS Agent logs:"
    echo "  docker compose logs rss-agent"
    echo "  docker compose logs redis"
    echo "  docker compose logs celery-scraping"
    echo "  docker compose logs celery-processing"
    echo "  docker compose logs celery-uploads"
    echo "  docker compose logs celery-flower"
fi

echo ""
log_purple "🏁 RSS Agent rebuild complete!"

# Show quick test commands
echo ""
log_purple "🚀 Quick test commands:"
echo "  curl http://localhost:8086/health"
echo "  curl -X POST http://localhost:8086/manual-check"
echo "  docker compose logs -f celery-scraping"