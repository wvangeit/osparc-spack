#!/bin/bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if running on Linux (no Windows support per project guidelines)
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        log_error "Windows is not supported. Use WSL2 instead."
        exit 1
    fi

    # Check Spack
    if ! command -v spack &>/dev/null; then
        log_error "Spack is not installed or not in PATH"
        log_info "Install Spack: https://spack.readthedocs.io/en/latest/getting_started.html"
        exit 1
    fi

    # Check Docker
    if ! command -v docker &>/dev/null; then
        log_error "Docker is not installed"
        log_info "Install Docker: https://docs.docker.com/engine/install/"
        exit 1
    fi

    # Check Docker daemon
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running"
        log_info "Start Docker: sudo systemctl start docker"
        exit 1
    fi

    # Check Make version (project requires 4.2+)
    if ! make --version | head -1 | grep -q "GNU Make"; then
        log_warn "GNU Make not found. Project requires GNU Make 4.2+"
    fi

    log_info "Prerequisites check passed ✓"
}

# Setup Spack repository
setup_spack_repo() {
    echo "Setting up spack repo"
    local repo_path="${HOME}/.spack/repos/"
    local namespace="vilitis"

    log_info "Setting up Spack repository..."

    if [ ! -d "$repo_path" ]; then
        log_info "Creating Spack repository: $repo_path"
        spack repo create "$repo_path" "$namespace"
        spack repo add "$repo_path"/spack_repo/"$namespace"
    fi

    # Copy package file
    local pkg_dir="$repo_path/spack_repo/vilitis/packages/osparc"
    mkdir -p "$pkg_dir"

    spack external find

    # Assume package.py is in same directory as this script
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$script_dir/package.py" ]; then
        cp "$script_dir/package.py" "$pkg_dir/"
        log_info "Package file installed ✓"
    else
        log_error "package.py not found in $script_dir"
        exit 1
    fi
}

# Install osparc
install_osparc() {
    local variant_args=""
    local install_mode="devel"

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
        --prod)
            variant_args="+prod"
            install_mode="prod"
            shift
            ;;
        --no-frontend)
            variant_args="$variant_args ~frontend"
            shift
            ;;
        --no-ops)
            variant_args="$variant_args ~ops"
            shift
            ;;
        --with-tests)
            variant_args="$variant_args +tests"
            shift
            ;;
        --help | -h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
        esac
    done

    # Set default variants if none specified
    if [ -z "$variant_args" ]; then
        variant_args="+devel +frontend +ops +vendors"
    fi

    log_info "Installing osparc in $install_mode mode..."
    log_info "Variants: $variant_args"

    # Install with progress monitoring
    if ! spack -d install -v osparc "${variant_args}"; then
        log_error "Installation failed"
        exit 1
    fi

    log_info "Installation completed successfully ✓"
}

# Post-installation setup
post_install() {
    log_info "Setting up osparc environment..."

    # Load the package
    spack load osparc

    # Verify installation
    if command -v osparc-info &>/dev/null; then
        log_info "Running post-installation verification..."
        osparc-info
    else
        log_warn "osparc-info command not found. Try: spack load osparc"
    fi

    log_info ""
    log_info "🎉 osparc is ready!"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Load environment: spack load osparc"
    log_info "  2. Build images:     osparc-build"
    log_info "  3. Start platform:   osparc-up"
    log_info "  4. Open browser:     http://127.0.0.1.nip.io:9081/"
    log_info ""
    log_info "For help: osparc-info"
}

show_help() {
    cat <<EOF
osparc Spack Installation Script

Usage: $0 [OPTIONS]

Options:
    --prod    Install for production deployment (default: devel)
    --no-frontend   Skip frontend components
    --no-ops        Skip ops stack (monitoring, portainer, etc.)
    --with-tests    Include test dependencies
    -h, --help      Show this help message

Examples:
    $0                          # Development installation
    $0 --prod             # Production installation  
    $0 --prod --no-ops    # Production without ops stack
    $0 --with-tests             # Development with test dependencies

Environment Variables (following env-vars.md):
    SWARM_STACK_NAME           Docker stack name (default: spack-osparc)
    DOCKER_REGISTRY            Docker registry (default: local)
    DOCKER_IMAGE_TAG           Docker image tag (default: development/production)

Requirements:
    - Linux operating system (WSL2 on Windows)
    - Docker Engine running
    - Spack package manager
    - GNU Make 4.2+
    - Python 3.11+

For more information: https://github.com/ITISFoundation/osparc-simcore
EOF
}

# Main execution
main() {
    log_info "Starting osparc Spack installation..."

    export SPACK_ROOT=spack
    # shellcheck disable=SC1091
    source "${SPACK_ROOT}/share/spack/setup-env.sh"

    check_prerequisites
    setup_spack_repo
    install_osparc "$@"
    post_install

    log_info "Installation script completed successfully! 🚀"
}

# Run main function with all arguments
main "$@"
