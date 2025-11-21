#!/bin/bash

# Supabase CLI Updater Script
# Updates Supabase CLI to the latest version from GitHub releases
# Usage: ./update_supabase_cli.sh [--force] [--check]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
GITHUB_REPO="supabase/cli"
GITHUB_API="https://api.github.com/repos/${GITHUB_REPO}/releases/latest"
TEMP_DIR="/tmp/supabase-update-$$"

# Parse arguments
FORCE_UPDATE=false
CHECK_ONLY=false

for arg in "$@"; do
    case $arg in
        --force)
            FORCE_UPDATE=true
            shift
            ;;
        --check)
            CHECK_ONLY=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --force    Force update even if already on latest version"
            echo "  --check    Only check version, don't update"
            echo "  --help     Show this help message"
            exit 0
            ;;
    esac
done

# Helper functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}✓${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1" >&2
}

log_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

cleanup() {
    if [ -d "$TEMP_DIR" ]; then
        log_info "Cleaning up temporary files..."
        rm -rf "$TEMP_DIR"
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Check dependencies
check_dependencies() {
    local missing_deps=()

    for cmd in curl dpkg; do
        if ! command -v $cmd &> /dev/null; then
            missing_deps+=($cmd)
        fi
    done

    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_info "Install them with: sudo apt-get install ${missing_deps[*]}"
        exit 1
    fi
}

# Check if running with sudo
check_sudo() {
    if [ "$EUID" -ne 0 ] && [ "$CHECK_ONLY" = false ]; then
        log_error "This script requires sudo privileges to install packages"
        log_info "Please run: sudo $0 $@"
        exit 1
    fi
}

# Detect system architecture
detect_arch() {
    local machine_arch=$(uname -m)

    case $machine_arch in
        x86_64)
            echo "amd64"
            ;;
        aarch64|arm64)
            echo "arm64"
            ;;
        *)
            log_error "Unsupported architecture: $machine_arch"
            exit 1
            ;;
    esac
}

# Get current installed version
get_current_version() {
    if command -v supabase &> /dev/null; then
        supabase --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "unknown"
    else
        echo "not_installed"
    fi
}

# Get latest version from GitHub
get_latest_version() {
    log_info "Fetching latest version from GitHub..."

    local latest_version=$(curl -s -f "$GITHUB_API" | grep -o '"tag_name"[^"]*"v[^"]*"' | head -1 | sed 's/.*"v\([^"]*\)".*/\1/')

    if [ -z "$latest_version" ]; then
        log_error "Failed to fetch release information from GitHub"
        log_warning "Please check your internet connection or GitHub API rate limits"
        exit 1
    fi

    echo "$latest_version"
}

# Get download URL for the .deb package
get_download_url() {
    local version=$1
    local arch=$2

    local deb_file="supabase_${version}_linux_${arch}.deb"

    local download_url=$(curl -s -f "$GITHUB_API" | grep -o "\"browser_download_url\"[^\"]*\"[^\"]*${deb_file}\"" | sed 's/.*"browser_download_url": "\([^"]*\)".*/\1/')

    if [ -z "$download_url" ]; then
        log_error "Could not find .deb package for version $version and architecture $arch"
        log_info "Searched for: $deb_file"
        exit 1
    fi

    echo "$download_url"
}

# Download and install
download_and_install() {
    local download_url=$1
    local filename=$(basename "$download_url")

    # Create temp directory
    mkdir -p "$TEMP_DIR"

    log_info "Downloading $filename..."
    if ! curl -L -f -o "$TEMP_DIR/$filename" "$download_url" --progress-bar; then
        log_error "Failed to download package"
        exit 1
    fi

    log_success "Download completed"

    log_info "Installing Supabase CLI..."
    if dpkg -i "$TEMP_DIR/$filename" 2>&1 | grep -v "warning"; then
        log_success "Installation completed successfully"
    else
        log_warning "dpkg reported warnings, fixing dependencies..."
        apt-get -f install -y
        log_success "Dependencies fixed"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   Supabase CLI Updater v1.0           ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""

    # Pre-flight checks
    log_info "Checking dependencies..."
    check_dependencies
    log_success "All dependencies found"

    check_sudo

    # Detect architecture
    local arch=$(detect_arch)
    log_info "Detected architecture: $arch"

    # Get versions
    local current_version=$(get_current_version)
    log_info "Current version: $current_version"

    local latest_version=$(get_latest_version)
    log_info "Latest version: $latest_version"

    # Check if already on latest version
    if [ "$current_version" = "$latest_version" ] && [ "$FORCE_UPDATE" = false ]; then
        log_success "Already on the latest version ($latest_version)"

        if [ "$CHECK_ONLY" = false ]; then
            log_info "Use --force to reinstall anyway"
        fi
        exit 0
    fi

    # Check-only mode
    if [ "$CHECK_ONLY" = true ]; then
        if [ "$current_version" != "$latest_version" ]; then
            log_warning "Update available: $current_version → $latest_version"
            log_info "Run without --check to update"
        fi
        exit 0
    fi

    # Get download URL
    local download_url=$(get_download_url "$latest_version" "$arch")
    log_info "Download URL: $download_url"

    # Confirm update
    if [ "$FORCE_UPDATE" = false ]; then
        echo ""
        log_warning "About to update Supabase CLI: $current_version → $latest_version"
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Update cancelled"
            exit 0
        fi
    fi

    # Download and install
    download_and_install "$download_url"

    # Verify installation
    local new_version=$(get_current_version)
    if [ "$new_version" = "$latest_version" ]; then
        echo ""
        log_success "Successfully updated Supabase CLI to version $latest_version"
        echo ""
        log_info "Run 'supabase --version' to verify"
    else
        log_warning "Installation completed but version verification failed"
        log_info "Expected: $latest_version, Got: $new_version"
    fi
}

# Run main function
main "$@"
