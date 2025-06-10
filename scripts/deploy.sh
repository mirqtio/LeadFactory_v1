#!/bin/bash
# LeadFactory Production Deployment Script - Task 093
# Deploys application containers with health checks and monitoring

set -e

# Configuration
COMPOSE_FILE="docker-compose.production.yml"
PROJECT_NAME="leadfactory"
BACKUP_DIR="/var/backups/leadfactory"
LOG_FILE="/var/log/leadfactory-deploy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

error() {
    log "${RED}ERROR: $1${NC}"
    exit 1
}

warning() {
    log "${YELLOW}WARNING: $1${NC}"
}

success() {
    log "${GREEN}SUCCESS: $1${NC}"
}

info() {
    log "${BLUE}INFO: $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    info "Checking deployment prerequisites..."
    
    # Check Docker and Docker Compose
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
    fi
    
    # Check compose file exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        error "Docker Compose file not found: $COMPOSE_FILE"
    fi
    
    # Check environment file
    if [ ! -f ".env.production" ]; then
        warning ".env.production file not found - using environment variables"
    fi
    
    # Check required directories
    mkdir -p logs uploads config/
    
    success "Prerequisites check completed"
}

# Backup current deployment
backup_current_deployment() {
    info "Creating backup of current deployment..."
    
    mkdir -p "$BACKUP_DIR"
    BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$BACKUP_DIR/deployment_$BACKUP_TIMESTAMP"
    
    # Create backup directory
    mkdir -p "$BACKUP_PATH"
    
    # Backup database if running
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps postgres | grep -q "Up"; then
        info "Backing up database..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres \
            pg_dump -U "${POSTGRES_USER:-leadfactory}" "${POSTGRES_DB:-leadfactory}" \
            > "$BACKUP_PATH/database_backup.sql" || warning "Database backup failed"
    fi
    
    # Backup volumes
    docker run --rm -v leadfactory_postgres_data:/data -v "$BACKUP_PATH:/backup" \
        alpine tar czf /backup/postgres_data.tar.gz -C /data . || warning "Postgres volume backup failed"
    
    docker run --rm -v leadfactory_redis_data:/data -v "$BACKUP_PATH:/backup" \
        alpine tar czf /backup/redis_data.tar.gz -C /data . || warning "Redis volume backup failed"
    
    success "Backup created at $BACKUP_PATH"
}

# Pull latest images
pull_images() {
    info "Pulling latest container images..."
    
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" pull
    
    success "Images pulled successfully"
}

# Build application image
build_application() {
    info "Building LeadFactory application image..."
    
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" build leadfactory-api
    
    success "Application image built successfully"
}

# Deploy services
deploy_services() {
    info "Deploying LeadFactory services..."
    
    # Start infrastructure services first
    info "Starting infrastructure services..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d postgres redis
    
    # Wait for infrastructure to be healthy
    info "Waiting for infrastructure services to be healthy..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps
    
    # Wait up to 60 seconds for postgres to be ready
    for i in {1..20}; do
        if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres pg_isready -U "${POSTGRES_USER:-leadfactory}" -d "${POSTGRES_DB:-leadfactory}"; then
            success "PostgreSQL is ready"
            break
        fi
        if [ $i -eq 20 ]; then
            error "PostgreSQL failed to start within 60 seconds"
        fi
        sleep 3
    done
    
    # Run database migrations
    info "Running database migrations..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" run --rm leadfactory-api \
        python3 scripts/db_setup.py || warning "Database setup failed"
    
    # Start all services
    info "Starting all services..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d
    
    success "All services deployed"
}

# Verify deployment
verify_deployment() {
    info "Verifying deployment health..."
    
    # Wait for services to be ready
    sleep 30
    
    # Check service status
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps
    
    # Run health checks
    info "Running health checks..."
    
    # Check API health
    if command -v python3 &> /dev/null && [ -f "scripts/health_check.py" ]; then
        python3 scripts/health_check.py --endpoint "http://localhost:8000/health" || warning "API health check failed"
    else
        curl -f http://localhost:8000/health || warning "API health check failed"
    fi
    
    # Check Prometheus
    curl -f http://localhost:9091/-/healthy || warning "Prometheus health check failed"
    
    # Check Grafana
    curl -f http://localhost:3001/api/health || warning "Grafana health check failed"
    
    success "Deployment verification completed"
}

# Show deployment status
show_status() {
    info "Deployment Status:"
    echo ""
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps
    echo ""
    
    info "Service URLs:"
    echo "  API: http://localhost:8000"
    echo "  API Health: http://localhost:8000/health"
    echo "  API Docs: http://localhost:8000/docs"
    echo "  Prometheus: http://localhost:9091"
    echo "  Grafana: http://localhost:3001 (admin/${GRAFANA_ADMIN_PASSWORD:-admin})"
    echo "  Metrics: http://localhost:9090/metrics"
    echo ""
    
    info "Log locations:"
    echo "  Application: ./logs/"
    echo "  Deployment: $LOG_FILE"
    echo "  Container logs: docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs [service]"
    echo ""
}

# Cleanup old images and containers
cleanup() {
    info "Cleaning up old images and containers..."
    
    # Remove old images
    docker image prune -f
    
    # Remove unused volumes (be careful with this in production)
    # docker volume prune -f
    
    success "Cleanup completed"
}

# Main deployment function
deploy() {
    info "Starting LeadFactory production deployment..."
    
    check_prerequisites
    backup_current_deployment
    pull_images
    build_application
    deploy_services
    verify_deployment
    show_status
    cleanup
    
    success "LeadFactory deployment completed successfully!"
    info "Monitor the deployment with: docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f"
}

# Rollback function
rollback() {
    local backup_path="$1"
    
    if [ -z "$backup_path" ]; then
        error "Backup path not specified for rollback"
    fi
    
    if [ ! -d "$backup_path" ]; then
        error "Backup directory not found: $backup_path"
    fi
    
    warning "Rolling back to backup: $backup_path"
    
    # Stop current services
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down
    
    # Restore data volumes
    if [ -f "$backup_path/postgres_data.tar.gz" ]; then
        docker run --rm -v leadfactory_postgres_data:/data -v "$backup_path:/backup" \
            alpine tar xzf /backup/postgres_data.tar.gz -C /data
    fi
    
    if [ -f "$backup_path/redis_data.tar.gz" ]; then
        docker run --rm -v leadfactory_redis_data:/data -v "$backup_path:/backup" \
            alpine tar xzf /backup/redis_data.tar.gz -C /data
    fi
    
    # Restore database
    if [ -f "$backup_path/database_backup.sql" ]; then
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d postgres
        sleep 10
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres \
            psql -U "${POSTGRES_USER:-leadfactory}" "${POSTGRES_DB:-leadfactory}" \
            < "$backup_path/database_backup.sql"
    fi
    
    # Start services
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d
    
    success "Rollback completed"
}

# Script usage
usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy                 Deploy LeadFactory (default)"
    echo "  status                 Show deployment status"
    echo "  stop                   Stop all services"
    echo "  start                  Start all services"
    echo "  restart                Restart all services"
    echo "  logs [service]         Show logs for all services or specific service"
    echo "  rollback <backup_path> Rollback to previous backup"
    echo "  cleanup                Clean up old images and containers"
    echo "  help                   Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 deploy"
    echo "  $0 status"
    echo "  $0 logs leadfactory-api"
    echo "  $0 rollback /var/backups/leadfactory/deployment_20250610_120000"
}

# Handle command line arguments
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    status)
        show_status
        ;;
    stop)
        info "Stopping LeadFactory services..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down
        success "Services stopped"
        ;;
    start)
        info "Starting LeadFactory services..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d
        success "Services started"
        ;;
    restart)
        info "Restarting LeadFactory services..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" restart
        success "Services restarted"
        ;;
    logs)
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs -f "${2:-}"
        ;;
    rollback)
        rollback "$2"
        ;;
    cleanup)
        cleanup
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        error "Unknown command: $1"
        usage
        ;;
esac