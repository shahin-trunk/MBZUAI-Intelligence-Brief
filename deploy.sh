#!/usr/bin/env bash
# =============================================================================
# MBZUAI Intelligence Brief - Deployment Script
# =============================================================================
# Deploys Traefik + Frontend + Dispatcher via Docker Compose on the target
# EC2 server. Can also be run locally for testing.
#
# Usage:
#   ./deploy.sh deploy             Quick deploy (rebuild + start)
#   ./deploy.sh status             Show service status
#   ./deploy.sh logs [service]     Follow service logs
#   ./deploy.sh restart [service]  Restart a service
#   ./deploy.sh stop               Stop all services
#   ./deploy.sh clean              Remove containers, volumes, images
#   ./deploy.sh help               Show this help
# =============================================================================
set -euo pipefail

# -- Theme --------------------------------------------------------------------
BOLD='\033[1m'
DIM='\033[2m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

banner() {
    echo -e "${CYAN}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║    MBZUAI Intelligence Brief Deploy      ║"
    echo "  ║    Traefik + Next.js + Dispatcher        ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info()    { echo -e "  ${GREEN}●${NC} $*"; }
log_warn()    { echo -e "  ${YELLOW}●${NC} $*"; }
log_error()   { echo -e "  ${RED}●${NC} $*"; }
log_step()    { echo -e "\n${BLUE}━━━ ${BOLD}$*${NC}"; }
log_success() { echo -e "  ${GREEN}✓${NC} $*"; }

# -- Docker Compose detection -------------------------------------------------
detect_compose() {
    if docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    else
        log_error "Docker Compose not found. Install Docker and try again."
        exit 1
    fi
}

# -- Prerequisites check ------------------------------------------------------
check_prerequisites() {
    log_step "Checking prerequisites"

    if ! command -v docker &>/dev/null; then
        log_error "Docker is not installed. Install Docker first:"
        log_error "  curl -fsSL https://get.docker.com | sh"
        exit 1
    fi
    log_success "Docker available"

    detect_compose
    log_success "Docker Compose available"

    if [ ! -f "${SCRIPT_DIR}/deploy.env" ]; then
        log_warn "deploy.env not found — copying from deploy.env.example"
        cp "${SCRIPT_DIR}/deploy.env.example" "${SCRIPT_DIR}/deploy.env"
        log_warn "Edit deploy.env with your credentials, then re-run this script."
        exit 1
    fi
    log_success "deploy.env found"
}

# -- Quick deploy -------------------------------------------------------------
cmd_deploy() {
    check_prerequisites

    log_step "Building and deploying services"

    # Ensure traefik htpasswd file exists
    if [ ! -f "${SCRIPT_DIR}/traefik/users/.cache" ]; then
        mkdir -p "${SCRIPT_DIR}/traefik/users"
        echo 'admin:$2b$05$qr22kqUZtvQKLQ17QTjT2OwWhriRutanPIexhl45NLrOybXieyiw6' > "${SCRIPT_DIR}/traefik/users/.cache"
        log_info "Created default htpasswd (username: admin)"
    fi

    log_info "Building images..."
    $COMPOSE_CMD -f "${COMPOSE_FILE}" build --pull

    log_info "Starting services..."
    $COMPOSE_CMD -f "${COMPOSE_FILE}" up -d

    log_success "Deployment complete!"
    echo ""
    cmd_status
}

# -- Status -------------------------------------------------------------------
cmd_status() {
    detect_compose
    log_step "Service Status"

    $COMPOSE_CMD -f "${COMPOSE_FILE}" ps 2>/dev/null || true

    echo ""
    echo -e "  ${DIM}Health endpoints:${NC}"
    for service in frontend dispatcher traefik; do
        container="brief-${service}"
        if docker inspect --format='{{.State.Status}}' "${container}" 2>/dev/null | grep -q running; then
            echo -e "    ${GREEN}✓${NC} ${service}"
        else
            echo -e "    ${RED}✗${NC} ${service} (not running)"
        fi
    done
}

# -- Logs ---------------------------------------------------------------------
cmd_logs() {
    detect_compose
    local svc="${1:-}"
    if [ -n "$svc" ]; then
        $COMPOSE_CMD -f "${COMPOSE_FILE}" logs -f --tail 100 "$svc"
    else
        $COMPOSE_CMD -f "${COMPOSE_FILE}" logs -f --tail 100
    fi
}

# -- Restart ------------------------------------------------------------------
cmd_restart() {
    detect_compose
    local svc="${1:-}"
    if [ -n "$svc" ]; then
        log_step "Restarting $svc"
        $COMPOSE_CMD -f "${COMPOSE_FILE}" restart "$svc"
    else
        log_step "Restarting all services"
        $COMPOSE_CMD -f "${COMPOSE_FILE}" restart
    fi
    log_success "Done"
}

# -- Stop ---------------------------------------------------------------------
cmd_stop() {
    detect_compose
    log_step "Stopping all services"
    $COMPOSE_CMD -f "${COMPOSE_FILE}" down
    log_success "Services stopped"
}

# -- Clean --------------------------------------------------------------------
cmd_clean() {
    detect_compose
    log_step "Cleaning up"
    $COMPOSE_CMD -f "${COMPOSE_FILE}" down -v --rmi local 2>/dev/null || true
    log_success "Cleaned up containers, volumes, and local images"
}

# -- Help ---------------------------------------------------------------------
cmd_help() {
    banner
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "Deploy:"
    echo "  deploy               Build and start all services"
    echo ""
    echo "Management:"
    echo "  status               Show service status"
    echo "  logs [service]       Follow logs (all or specific service)"
    echo "  restart [service]    Restart all or specific service"
    echo "  stop                 Stop all services"
    echo "  clean                Remove containers, volumes, and local images"
    echo "  help                 Show this help"
    echo ""
    echo "Services:"
    echo "  frontend    Next.js 16   → brief.\$BASE_DOMAIN       port 3000"
    echo "  dispatcher  Flask        → dispatch.\$BASE_DOMAIN    port 8080"
    echo "  traefik     Traefik v3   → traefik.\$BASE_DOMAIN     ports 80/443"
    echo ""
}

# -- Main ---------------------------------------------------------------------
main() {
    cd "$SCRIPT_DIR"

    case "${1:-}" in
        deploy)
            banner
            cmd_deploy
            ;;
        status)
            cmd_status
            ;;
        logs)
            cmd_logs "${2:-}"
            ;;
        restart)
            cmd_restart "${2:-}"
            ;;
        stop)
            cmd_stop
            ;;
        clean)
            cmd_clean
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            banner
            cmd_help
            ;;
    esac
}

main "$@"
