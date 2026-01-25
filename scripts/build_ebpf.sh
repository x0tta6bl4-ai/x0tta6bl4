#!/bin/bash
# x0tta6bl4 eBPF Build & Validation Script
# Compile and validate all eBPF programs for x0tta6bl4 mesh network
#
# Usage:
#   ./scripts/build_ebpf.sh                    # Build and validate
#   ./scripts/build_ebpf.sh --clean            # Clean build artifacts
#   ./scripts/build_ebpf.sh --test             # Run full test suite
#   ./scripts/build_ebpf.sh --install          # Build, validate, and install

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EBPF_DIR="$PROJECT_ROOT/src/network/ebpf/programs"
BUILD_DIR="$PROJECT_ROOT/build/ebpf"
LOG_FILE="$BUILD_DIR/build.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}❌ $1${NC}" | tee -a "$LOG_FILE"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."
    local missing=()
    
    for cmd in clang make file python3; do
        if ! command -v "$cmd" &> /dev/null; then
            missing+=("$cmd")
        fi
    done
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing[*]}"
        echo "Install with: apt-get install -y ${missing[*]}"
        return 1
    fi
    
    log_success "All dependencies found"
    return 0
}

# Clean build artifacts
clean_build() {
    log_info "Cleaning eBPF build artifacts..."
    cd "$EBPF_DIR"
    make clean || log_warning "Make clean failed or not available"
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    log_success "Cleaned"
}

# Compile eBPF programs
compile_ebpf() {
    log_info "Compiling eBPF programs..."
    cd "$EBPF_DIR"
    
    # Create CO-RE headers if available
    log_info "Generating vmlinux.h for CO-RE support..."
    make vmlinux || log_warning "CO-RE headers not available (kernel may not support BTF)"
    
    # Compile all programs
    if ! make all >> "$LOG_FILE" 2>&1; then
        log_error "Compilation failed"
        tail -20 "$LOG_FILE"
        return 1
    fi
    
    # Copy to build directory
    mkdir -p "$BUILD_DIR"
    cp *.o "$BUILD_DIR/" 2>/dev/null || log_warning "No object files to copy"
    
    log_success "Compilation complete"
    return 0
}

# Verify compiled eBPF programs
verify_ebpf() {
    log_info "Verifying eBPF programs..."
    
    if [ -z "$(ls "$BUILD_DIR"/*.o 2>/dev/null)" ]; then
        log_error "No eBPF object files found in $BUILD_DIR"
        return 1
    fi
    
    cd "$BUILD_DIR"
    local all_valid=true
    
    for obj in *.o; do
        if file "$obj" | grep -q "ELF.*BPF"; then
            log_success "$obj is valid eBPF"
        else
            log_error "$obj is NOT valid eBPF"
            file "$obj"
            all_valid=false
        fi
    done
    
    if [ "$all_valid" = false ]; then
        return 1
    fi
    
    log_success "All eBPF programs verified"
    return 0
}

# Display object information
display_info() {
    log_info "eBPF Object Information:"
    echo "" | tee -a "$LOG_FILE"
    
    cd "$BUILD_DIR"
    ls -lh *.o 2>/dev/null | tee -a "$LOG_FILE" || echo "No objects"
    
    echo "" | tee -a "$LOG_FILE"
    log_info "Program sizes and sections:"
    for obj in *.o; do
        echo "  $obj:" | tee -a "$LOG_FILE"
        objdump -h "$obj" 2>/dev/null | grep -E "Idx|\.text|\.maps|\.rodata" | head -5 | tee -a "$LOG_FILE" || true
    done
    
    echo "" | tee -a "$LOG_FILE"
}

# Advanced validation with Python
validate_elf() {
    log_info "Running advanced ELF validation..."
    
    python3 << 'EOF'
import os
import sys
from pathlib import Path

try:
    from elftools.elf.elffile import ELFFile
except ImportError:
    print("Installing pyelftools...")
    os.system("pip3 install -q pyelftools")
    from elftools.elf.elffile import ELFFile

build_dir = Path("build/ebpf")
all_valid = True

for obj_file in sorted(build_dir.glob("*.o")):
    try:
        with open(obj_file, 'rb') as f:
            elf = ELFFile(f)
            
            # Check machine type
            machine = elf['e_machine']
            if machine != 'EM_BPF':
                print(f"❌ {obj_file.name} - Wrong machine type: {machine}")
                all_valid = False
                continue
            
            # Count sections
            section_count = elf.num_sections()
            
            # Find useful sections
            sections = []
            for section in elf.iter_sections():
                if section.name in ['.text', '.maps', '.rodata', '.data', '.bss']:
                    sections.append(f"{section.name}({section['sh_size']}B)")
            
            print(f"✅ {obj_file.name} - Valid eBPF (machine={machine}, sections={section_count}, {', '.join(sections) or 'minimal'})")
            
    except Exception as e:
        print(f"❌ {obj_file.name} - Error: {e}")
        all_valid = False

sys.exit(0 if all_valid else 1)
EOF
    
    return $?
}

# Run all validation tests
test_all() {
    log_info "Running full test suite..."
    echo "" | tee -a "$LOG_FILE"
    
    clean_build || return 1
    compile_ebpf || return 1
    verify_ebpf || return 1
    validate_elf || return 1
    display_info
    
    log_success "All tests passed!"
    return 0
}

# Install to system location
install_ebpf() {
    log_info "Installing eBPF programs..."
    cd "$EBPF_DIR"
    
    if ! make install >> "$LOG_FILE" 2>&1; then
        log_error "Installation failed"
        return 1
    fi
    
    log_success "Installation complete"
    return 0
}

# Show help
show_help() {
    cat << 'EOF'
x0tta6bl4 eBPF Build & Validation Script

USAGE:
    ./scripts/build_ebpf.sh [OPTION]

OPTIONS:
    (no args)   Build and validate eBPF programs (default: compile, verify)
    --clean     Clean all build artifacts
    --test      Run full test suite (clean, build, verify, validate)
    --install   Build, validate, and install to system
    --info      Display compiled program information
    --help      Show this help message

EXAMPLES:
    # Build and verify (default)
    ./scripts/build_ebpf.sh

    # Full test suite with detailed validation
    ./scripts/build_ebpf.sh --test

    # Clean rebuild
    ./scripts/build_ebpf.sh --clean && ./scripts/build_ebpf.sh

    # Install compiled objects
    ./scripts/build_ebpf.sh --install

REQUIREMENTS:
    - clang >= 10
    - make
    - file
    - python3 (for advanced validation)
    - linux-headers (for BTF support)
    - bpftool (optional, for CO-RE)

EOF
}

# Main entry point
main() {
    mkdir -p "$BUILD_DIR"
    > "$LOG_FILE"  # Reset log
    
    log_info "x0tta6bl4 eBPF Build & Validation"
    log_info "=================================="
    echo "" | tee -a "$LOG_FILE"
    
    # Check dependencies
    if ! check_dependencies; then
        return 1
    fi
    
    # Parse arguments
    local action="${1:-build}"
    
    case "$action" in
        --help|-h)
            show_help
            return 0
            ;;
        --clean)
            clean_build
            return 0
            ;;
        --test)
            test_all
            return $?
            ;;
        --install)
            compile_ebpf && verify_ebpf && install_ebpf
            return $?
            ;;
        --info)
            display_info
            return 0
            ;;
        build|--build)
            compile_ebpf && verify_ebpf && display_info
            return $?
            ;;
        *)
            log_error "Unknown option: $action"
            show_help
            return 1
            ;;
    esac
}

# Run main function
main "$@"
exit $?
