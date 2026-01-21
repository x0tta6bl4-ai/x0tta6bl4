#!/bin/bash
# Setup eBPF Development Environment for x0tta6bl4
# Prepares system for eBPF program compilation and validation
#
# Usage:
#   ./scripts/setup_ebpf_environment.sh                 # Full setup
#   ./scripts/setup_ebpf_environment.sh --check-only    # Check without install
#   ./scripts/setup_ebpf_environment.sh --dry-run       # Show what would be installed

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Flags
CHECK_ONLY=${1:-""}
DRY_RUN=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --check-only)
            CHECK_ONLY="--check-only"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            cat << 'EOF'
Setup eBPF Development Environment for x0tta6bl4

USAGE:
    ./scripts/setup_ebpf_environment.sh [OPTIONS]

OPTIONS:
    (no args)       Full setup with automatic installation
    --check-only    Check requirements without installing
    --dry-run       Show what would be installed without installing
    --verbose       Verbose output
    -h, --help      Show this help

REQUIREMENTS:
    - Linux kernel >= 5.4 (with eBPF support)
    - clang >= 10
    - llvm >= 10
    - linux-headers for current kernel
    - build-essential
    - bpftool (optional)

EXAMPLE:
    # Check if system is ready
    ./scripts/setup_ebpf_environment.sh --check-only
    
    # Setup in dry-run mode
    ./scripts/setup_ebpf_environment.sh --dry-run
    
    # Full setup
    sudo ./scripts/setup_ebpf_environment.sh

EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root (required for apt operations)
check_root() {
    if [ "$CHECK_ONLY" != "--check-only" ] && [ "$DRY_RUN" = false ] && [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root for installation"
        echo "Run: sudo $0"
        exit 1
    fi
}

# Detect distro
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    else
        echo "unknown"
    fi
}

# Check kernel version
check_kernel_version() {
    log_info "Checking kernel version..."
    
    kernel_ver=$(uname -r | cut -d. -f1-2)
    if (( $(echo "$kernel_ver >= 5.4" | bc -l) )); then
        log_success "Kernel version $kernel_ver is compatible (>= 5.4)"
        return 0
    else
        log_error "Kernel version $kernel_ver is too old (requires >= 5.4)"
        return 1
    fi
}

# Check for eBPF support
check_ebpf_support() {
    log_info "Checking eBPF kernel support..."
    
    if grep -q CONFIG_BPF=y /boot/config-$(uname -r) 2>/dev/null; then
        log_success "CONFIG_BPF=y found"
    else
        log_warning "Could not verify CONFIG_BPF, assuming enabled"
    fi
    
    if [ -d /sys/kernel/debug/tracing ]; then
        log_success "Kernel tracing available"
    else
        log_warning "Kernel tracing may not be available"
    fi
}

# Check for required tools
check_tool() {
    local tool=$1
    if command -v "$tool" &> /dev/null; then
        local version=$($tool --version 2>/dev/null | head -1 || echo "unknown")
        log_success "$tool found ($version)"
        return 0
    else
        log_error "$tool not found"
        return 1
    fi
}

# Check all requirements
check_requirements() {
    log_info "=== Checking eBPF Requirements ==="
    echo ""
    
    local all_ok=true
    
    # Kernel
    if ! check_kernel_version; then
        all_ok=false
    fi
    check_ebpf_support
    echo ""
    
    # Tools
    log_info "Checking required tools..."
    for tool in clang llvm-config make gcc file python3; do
        if ! check_tool "$tool"; then
            all_ok=false
        fi
    done
    echo ""
    
    # Optional tools
    log_info "Checking optional tools..."
    for tool in bpftool pahole; do
        if check_tool "$tool"; then
            log_success "$tool is available (good for CO-RE)"
        else
            log_warning "$tool not found (optional, CO-RE support may be limited)"
        fi
    done
    echo ""
    
    # Linux headers
    log_info "Checking linux-headers..."
    kernel_ver=$(uname -r)
    if [ -d /usr/src/linux-headers-$kernel_ver ]; then
        log_success "linux-headers-$kernel_ver found"
    else
        log_error "linux-headers-$kernel_ver not found"
        all_ok=false
    fi
    
    return $([ "$all_ok" = true ] && echo 0 || echo 1)
}

# Install requirements on Ubuntu/Debian
install_debian() {
    log_info "Installing packages for Debian/Ubuntu..."
    
    local packages=(
        "clang"
        "llvm"
        "build-essential"
        "linux-headers-$(uname -r)"
        "bpftool"
        "pahole"
        "python3-dev"
    )
    
    if [ "$DRY_RUN" = true ]; then
        log_info "Would run: apt-get install ${packages[@]}"
        return 0
    fi
    
    apt-get update || log_warning "apt-get update failed"
    apt-get install -y "${packages[@]}" || log_error "Package installation failed"
}

# Install requirements on RHEL/CentOS
install_rhel() {
    log_info "Installing packages for RHEL/CentOS..."
    
    local packages=(
        "clang"
        "llvm-devel"
        "make"
        "gcc"
        "kernel-devel"
        "bpf-tools"
        "pahole"
        "python3-devel"
    )
    
    if [ "$DRY_RUN" = true ]; then
        log_info "Would run: yum install ${packages[@]}"
        return 0
    fi
    
    yum install -y "${packages[@]}" || log_error "Package installation failed"
}

# Install eBPF tools
install_ebpf_tools() {
    log_info "=== Installing eBPF Tools ==="
    echo ""
    
    local distro=$(detect_distro)
    
    case "$distro" in
        ubuntu|debian)
            install_debian
            ;;
        rhel|centos|fedora)
            install_rhel
            ;;
        *)
            log_error "Unsupported distro: $distro"
            log_info "Please install the following packages manually:"
            echo "  - clang >= 10"
            echo "  - llvm >= 10"
            echo "  - make"
            echo "  - gcc"
            echo "  - linux-headers"
            echo "  - bpftool (optional)"
            echo "  - pahole (optional)"
            return 1
            ;;
    esac
}

# Verify installation
verify_installation() {
    log_info "=== Verifying Installation ==="
    echo ""
    
    if check_requirements; then
        log_success "All requirements met!"
        return 0
    else
        log_error "Some requirements missing"
        return 1
    fi
}

# Main
main() {
    log_info "x0tta6bl4 eBPF Environment Setup"
    echo ""
    
    check_root
    
    if [ "$CHECK_ONLY" = "--check-only" ]; then
        if check_requirements; then
            log_success "System is ready for eBPF development"
            exit 0
        else
            log_error "System is not ready for eBPF development"
            exit 1
        fi
    fi
    
    if [ "$DRY_RUN" = true ]; then
        log_info "DRY RUN MODE - No changes will be made"
        echo ""
        check_requirements || true
        install_ebpf_tools || true
        echo ""
        log_info "Dry run complete. Run without --dry-run to install."
        exit 0
    fi
    
    check_requirements || log_warning "Some requirements missing, attempting to install..."
    echo ""
    install_ebpf_tools || log_warning "Installation completed with some errors"
    echo ""
    verify_installation
    
    if [ $? -eq 0 ]; then
        log_success "eBPF environment setup complete!"
        log_info "Next steps:"
        echo "  1. Run: ./scripts/build_ebpf.sh --test"
        echo "  2. Run: python3 scripts/validate_ebpf_observability.py"
        exit 0
    else
        log_error "Setup incomplete. Please fix issues above."
        exit 1
    fi
}

main "$@"
