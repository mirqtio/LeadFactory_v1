#!/bin/bash
# Container build automation script for PRP-1060
# Builds and pushes acceptance runner container to GHCR

set -euo pipefail

# Configuration
REGISTRY="ghcr.io/leadfactory"
IMAGE_NAME="acceptance-runner"
DOCKERFILE_PATH="containers/acceptance/Dockerfile"
BUILD_CONTEXT="containers/acceptance"
DEFAULT_TAG="latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
Container Build Script for PRP-1060 Acceptance Runner

Usage: $0 [OPTIONS] [TAG]

OPTIONS:
    -h, --help          Show this help message
    -p, --push          Push to registry after building
    -t, --tag TAG       Specify custom tag (default: latest)
    --no-cache          Build without using cache
    --dry-run           Show commands without executing
    --scan              Run security scan after build

EXAMPLES:
    $0                  Build with latest tag
    $0 -p               Build and push with latest tag
    $0 -t v1.0.0 -p     Build and push with v1.0.0 tag
    $0 --scan           Build and run security scan

ENVIRONMENT VARIABLES:
    GHCR_USER           GitHub Container Registry username
    GHCR_PAT            GitHub Container Registry personal access token
    DOCKER_BUILDKIT     Enable BuildKit (default: 1)

EOF
}

# Parse command line arguments
PUSH=false
TAG="$DEFAULT_TAG"
NO_CACHE=false
DRY_RUN=false
SCAN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -p|--push)
            PUSH=true
            shift
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --scan)
            SCAN=true
            shift
            ;;
        *)
            # Assume it's a tag if no flag
            if [[ ! $1 =~ ^- ]]; then
                TAG="$1"
            else
                log_error "Unknown option: $1"
                show_help
                exit 1
            fi
            shift
            ;;
    esac
done

# Build full image name
FULL_IMAGE_NAME="$REGISTRY/$IMAGE_NAME:$TAG"

log_info "Container Build Configuration"
echo "  Registry: $REGISTRY"
echo "  Image: $IMAGE_NAME"
echo "  Tag: $TAG"
echo "  Full Name: $FULL_IMAGE_NAME"
echo "  Push: $PUSH"
echo "  No Cache: $NO_CACHE"
echo "  Dry Run: $DRY_RUN"
echo "  Security Scan: $SCAN"
echo ""

# Validation checks
validate_environment() {
    log_info "Validating environment"
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check if Dockerfile exists
    if [[ ! -f "$DOCKERFILE_PATH" ]]; then
        log_error "Dockerfile not found at: $DOCKERFILE_PATH"
        exit 1
    fi
    
    # Check if build context exists
    if [[ ! -d "$BUILD_CONTEXT" ]]; then
        log_error "Build context directory not found: $BUILD_CONTEXT"
        exit 1
    fi
    
    # Check required files in build context
    required_files=(
        "$BUILD_CONTEXT/requirements.txt"
        "$BUILD_CONTEXT/entrypoint.sh"
        "$BUILD_CONTEXT/acceptance_runner.py"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Required file not found: $file"
            exit 1
        fi
    done
    
    # Validate push credentials if pushing
    if [[ "$PUSH" == true ]]; then
        if [[ -z "${GHCR_USER:-}" ]] || [[ -z "${GHCR_PAT:-}" ]]; then
            log_warning "GHCR_USER or GHCR_PAT not set. Checking if already logged in..."
            
            # Try to check if already logged in
            if ! echo "$GHCR_PAT" | docker login ghcr.io -u "$GHCR_USER" --password-stdin &> /dev/null; then
                if ! docker system info | grep -q "ghcr.io"; then
                    log_error "Not logged into GHCR. Please set GHCR_USER and GHCR_PAT or login manually"
                    exit 1
                fi
            fi
        fi
    fi
    
    log_success "Environment validation complete"
}

# Execute command with dry run support
execute_cmd() {
    local cmd="$1"
    local description="$2"
    
    log_info "$description"
    echo "  Command: $cmd"
    
    if [[ "$DRY_RUN" == true ]]; then
        log_warning "DRY RUN - Command not executed"
        return 0
    fi
    
    if eval "$cmd"; then
        log_success "$description completed"
        return 0
    else
        log_error "$description failed"
        return 1
    fi
}

# Docker login
docker_login() {
    if [[ "$PUSH" == true && "$DRY_RUN" == false ]]; then
        log_info "Logging into GitHub Container Registry"
        
        if [[ -n "${GHCR_USER:-}" && -n "${GHCR_PAT:-}" ]]; then
            echo "$GHCR_PAT" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
            log_success "GHCR login successful"
        else
            log_info "Using existing Docker login credentials"
        fi
    fi
}

# Build container
build_container() {
    log_info "Building container image"
    
    # Enable BuildKit
    export DOCKER_BUILDKIT=1
    
    # Build command
    local build_cmd="docker build"
    
    # Add no-cache flag if specified
    if [[ "$NO_CACHE" == true ]]; then
        build_cmd="$build_cmd --no-cache"
    fi
    
    # Add build args
    build_cmd="$build_cmd --build-arg BUILDKIT_INLINE_CACHE=1"
    build_cmd="$build_cmd --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    build_cmd="$build_cmd --build-arg VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
    
    # Add tags
    build_cmd="$build_cmd -t $FULL_IMAGE_NAME"
    
    # Add latest tag if not already latest
    if [[ "$TAG" != "latest" ]]; then
        build_cmd="$build_cmd -t $REGISTRY/$IMAGE_NAME:latest"
    fi
    
    # Add file and context
    build_cmd="$build_cmd -f $DOCKERFILE_PATH $BUILD_CONTEXT"
    
    execute_cmd "$build_cmd" "Building container image"
}

# Security scan
security_scan() {
    if [[ "$SCAN" == true ]]; then
        log_info "Running security scan"
        
        # Check if trivy is available
        if command -v trivy &> /dev/null; then
            execute_cmd "trivy image --exit-code 1 --severity HIGH,CRITICAL $FULL_IMAGE_NAME" "Security scan with Trivy"
        else
            log_warning "Trivy not available, skipping security scan"
            log_info "To install Trivy: https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
        fi
    fi
}

# Push container
push_container() {
    if [[ "$PUSH" == true ]]; then
        log_info "Pushing container to registry"
        
        execute_cmd "docker push $FULL_IMAGE_NAME" "Pushing tagged image"
        
        # Push latest tag if different
        if [[ "$TAG" != "latest" ]]; then
            execute_cmd "docker push $REGISTRY/$IMAGE_NAME:latest" "Pushing latest tag"
        fi
    fi
}

# Cleanup
cleanup() {
    log_info "Cleaning up build artifacts"
    
    # Remove intermediate images
    docker image prune -f &> /dev/null || true
    
    log_success "Cleanup complete"
}

# Main execution
main() {
    log_info "Starting container build process"
    echo "Timestamp: $(date -Iseconds)"
    echo ""
    
    # Validation
    validate_environment
    
    # Docker login
    docker_login
    
    # Build
    build_container
    
    # Security scan
    security_scan
    
    # Push
    push_container
    
    # Cleanup
    cleanup
    
    # Success summary
    log_success "Container build process completed successfully!"
    echo ""
    echo "Image Details:"
    echo "  Name: $FULL_IMAGE_NAME"
    echo "  Size: $(docker images --format 'table {{.Size}}' $FULL_IMAGE_NAME | tail -n1)"
    echo "  Created: $(docker images --format 'table {{.CreatedAt}}' $FULL_IMAGE_NAME | tail -n1)"
    
    if [[ "$PUSH" == true ]]; then
        echo ""
        echo "Registry Information:"
        echo "  Registry: $REGISTRY"
        echo "  Pull Command: docker pull $FULL_IMAGE_NAME"
    fi
    
    if [[ "$DRY_RUN" == true ]]; then
        echo ""
        log_warning "This was a dry run - no actual operations were performed"
    fi
}

# Error handling
trap 'log_error "Build process failed at line $LINENO"' ERR

# Run main function
main