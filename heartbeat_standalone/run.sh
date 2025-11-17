#!/bin/bash
#
# Helper script for running Heartbeat Detector
#
# Usage:
#   ./run.sh [command]
#
# Commands:
#   start     - Start the service (direct Python)
#   docker    - Start using Docker Compose
#   stop      - Stop Docker service
#   logs      - Show logs
#   test      - Test configuration
#   build     - Build Docker image
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cmd_start() {
    print_info "Starting Heartbeat Detector (Python)..."
    if command -v uv &> /dev/null; then
        uv run python heartbeat_detector.py
    else
        python3 heartbeat_detector.py
    fi
}

cmd_docker() {
    print_info "Starting Heartbeat Detector (Docker)..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    docker compose up -d
    print_info "Service started! Check status: docker compose ps"
    print_info "View logs: docker compose logs -f"
}

cmd_stop() {
    print_info "Stopping Heartbeat Detector..."
    docker compose down
}

cmd_logs() {
    docker compose logs -f
}

cmd_test() {
    print_info "Testing configuration..."
    python3 -c "
import json
data = json.load(open('config.json'))
print('✓ Config file valid')
print(f'  Targets: {len(data[\"targets\"])}')
print(f'  Timeout: {data[\"timeout\"]}s')
print(f'  Interval: {data[\"check_interval\"]}s')
"
    python3 -m py_compile heartbeat_detector.py
    print_info "✓ Python file valid"
}

cmd_build() {
    print_info "Building Docker image..."
    docker build -t heartbeat-detector:latest .
    print_info "Build completed"
}

case "${1:-}" in
    start)
        cmd_start
        ;;
    docker)
        cmd_docker
        ;;
    stop)
        cmd_stop
        ;;
    logs)
        cmd_logs
        ;;
    test)
        cmd_test
        ;;
    build)
        cmd_build
        ;;
    *)
        echo "Heartbeat Detector - Helper Script"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start     - Start the service (direct Python)"
        echo "  docker    - Start using Docker Compose"
        echo "  stop      - Stop Docker service"
        echo "  logs      - Show Docker logs"
        echo "  test      - Test configuration and Python file"
        echo "  build     - Build Docker image"
        echo ""
        echo "Examples:"
        echo "  $0 test       # Test configuration"
        echo "  $0 docker     # Start with Docker"
        echo "  $0 logs       # View logs"
        exit 1
        ;;
esac
