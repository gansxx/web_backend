#!/bin/bash
#
# Helper script to run Heartbeat Detector in Docker
#
# Usage:
#   ./scripts/run_heartbeat_docker.sh [command]
#
# Commands:
#   start     - Start heartbeat detector service
#   stop      - Stop heartbeat detector service
#   restart   - Restart heartbeat detector service
#   logs      - Show logs
#   status    - Show service status
#   build     - Rebuild the Docker image
#   clean     - Stop and remove containers, images, and volumes
#

set -e

COMPOSE_FILE="docker-compose.heartbeat.yml"
SERVICE_NAME="heartbeat"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Functions
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if docker compose is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not available"
        exit 1
    fi
}

# Start service
start_service() {
    print_info "Starting Heartbeat Detector service..."
    docker compose -f "$COMPOSE_FILE" up -d
    print_info "Service started! Access at http://localhost:8003"
    print_info "Check health: curl http://localhost:8003/health"
}

# Stop service
stop_service() {
    print_info "Stopping Heartbeat Detector service..."
    docker compose -f "$COMPOSE_FILE" down
    print_info "Service stopped"
}

# Restart service
restart_service() {
    print_info "Restarting Heartbeat Detector service..."
    docker compose -f "$COMPOSE_FILE" restart
    print_info "Service restarted"
}

# Show logs
show_logs() {
    print_info "Showing logs (Ctrl+C to exit)..."
    docker compose -f "$COMPOSE_FILE" logs -f "$SERVICE_NAME"
}

# Show status
show_status() {
    print_info "Service status:"
    docker compose -f "$COMPOSE_FILE" ps

    print_info "\nContainer health:"
    docker inspect heartbeat-detector --format='{{.State.Health.Status}}' 2>/dev/null || echo "Container not running"

    print_info "\nQuick health check:"
    curl -s http://localhost:8003/health 2>/dev/null && echo "" || echo "Service not responding"
}

# Build image
build_image() {
    print_info "Building Heartbeat Detector Docker image..."
    docker compose -f "$COMPOSE_FILE" build
    print_info "Build completed"
}

# Clean up
clean_up() {
    print_warn "This will remove containers, images, and volumes. Continue? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        print_info "Cleaning up..."
        docker compose -f "$COMPOSE_FILE" down -v --rmi all
        print_info "Cleanup completed"
    else
        print_info "Cleanup cancelled"
    fi
}

# Main
check_docker

case "${1:-}" in
    start)
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
    build)
        build_image
        ;;
    clean)
        clean_up
        ;;
    *)
        echo "Heartbeat Detector Docker Helper"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start     - Start heartbeat detector service"
        echo "  stop      - Stop heartbeat detector service"
        echo "  restart   - Restart heartbeat detector service"
        echo "  logs      - Show logs (follow mode)"
        echo "  status    - Show service status"
        echo "  build     - Rebuild the Docker image"
        echo "  clean     - Stop and remove containers, images, and volumes"
        echo ""
        echo "Examples:"
        echo "  $0 start          # Start the service"
        echo "  $0 logs           # View logs"
        echo "  $0 status         # Check status"
        exit 1
        ;;
esac
