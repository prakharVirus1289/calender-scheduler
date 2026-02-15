#!/bin/bash

# Task Scheduler - Docker Deployment Script
# Simple script to manage Docker deployment

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}    Task Scheduler - Docker Deployment Manager           ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Docker and Docker Compose are installed"
}

# Build the Docker image
build() {
    print_info "Building Docker image..."
    docker-compose build
    print_success "Build completed!"
}

# Start the application
start() {
    print_info "Starting Task Scheduler..."
    docker-compose up -d
    
    # Wait for health check
    sleep 3
    
    if docker ps | grep -q "task-scheduler"; then
        print_success "Container started successfully!"
        print_info "Web Interface: http://localhost:5000"
        print_info "API Health: http://localhost:5000/api/health"
    else
        print_error "Failed to start container"
        print_info "Check logs with: ./deploy.sh logs"
        exit 1
    fi
}

# Stop the application
stop() {
    print_info "Stopping Task Scheduler..."
    docker-compose down
    print_success "Container stopped"
}

# Restart the application
restart() {
    print_info "Restarting Task Scheduler..."
    docker-compose restart
    print_success "Container restarted"
}

# Show logs
logs() {
    print_info "Showing logs (Ctrl+C to exit)..."
    docker-compose logs -f
}

# Show status
status() {
    print_info "Container Status:"
    docker-compose ps
    echo ""
    
    if docker ps | grep -q "task-scheduler"; then
        print_success "Container is running"
        
        # Check health
        if docker inspect task-scheduler | grep -q '"Status": "healthy"'; then
            print_success "Health check: Healthy"
        else
            print_warning "Health check: Not healthy yet"
        fi
        
        echo ""
        print_info "Access points:"
        echo "  • Web Interface: http://localhost:5000"
        echo "  • API Health: http://localhost:5000/api/health"
    else
        print_error "Container is not running"
    fi
}

# Rebuild and restart
rebuild() {
    print_info "Rebuilding and restarting..."
    docker-compose down
    docker-compose up -d --build
    print_success "Rebuild completed!"
    status
}

# Clean up
clean() {
    print_warning "This will remove the container and image. Data in scheduler_storage will be preserved."
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cleaning up..."
        docker-compose down
        docker rmi task-scheduler_task-scheduler 2>/dev/null || true
        print_success "Cleanup completed"
    else
        print_info "Cleanup cancelled"
    fi
}

# Backup data
backup() {
    BACKUP_DIR="scheduler_storage_backup_$(date +%Y%m%d_%H%M%S)"
    print_info "Creating backup: $BACKUP_DIR"
    
    if [ -d "scheduler_storage" ]; then
        cp -r scheduler_storage "$BACKUP_DIR"
        print_success "Backup created: $BACKUP_DIR"
    else
        print_warning "No scheduler_storage directory found"
    fi
}

# Show help
show_help() {
    echo "Usage: ./deploy.sh [command]"
    echo ""
    echo "Commands:"
    echo "  build     - Build the Docker image"
    echo "  start     - Start the application"
    echo "  stop      - Stop the application"
    echo "  restart   - Restart the application"
    echo "  status    - Show application status"
    echo "  logs      - Show application logs"
    echo "  rebuild   - Rebuild and restart"
    echo "  clean     - Remove container and image"
    echo "  backup    - Backup scheduler data"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./deploy.sh start     # Start the application"
    echo "  ./deploy.sh logs      # View logs"
    echo "  ./deploy.sh rebuild   # Rebuild after code changes"
}

# Main script
main() {
    print_header
    
    # Check Docker installation
    check_docker
    echo ""
    
    # Parse command
    case "${1:-help}" in
        build)
            build
            ;;
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        status)
            status
            ;;
        logs)
            logs
            ;;
        rebuild)
            rebuild
            ;;
        clean)
            clean
            ;;
        backup)
            backup
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"