# Content Finder Agent Makefile

.PHONY: help build start stop restart logs status test cleanup

# Default target
help:
	@echo "Available commands:"
	@echo "  build     - Build Docker images"
	@echo "  start     - Start all services"
	@echo "  stop      - Stop all services"
	@echo "  restart   - Restart all services"
	@echo "  logs      - Show service logs"
	@echo "  status    - Show service status"
	@echo "  test      - Test the complete workflow"
	@echo "  cleanup   - Stop and cleanup Docker resources"

# Build Docker images
build:
	./deploy.sh build

# Start all services
start:
	./deploy.sh start

# Stop all services
stop:
	./deploy.sh stop

# Restart all services
restart:
	./deploy.sh restart

# Show service logs
logs:
	./deploy.sh logs

# Show service status
status:
	./deploy.sh status

# Test the complete workflow
test:
	./deploy.sh test

# Clean up Docker resources
cleanup:
	./deploy.sh cleanup

# Quick development commands
dev-build: build start

dev-test: status test

dev-restart: restart status