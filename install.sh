#!/bin/bash

################################################################################
# PowerMTA + XOAUTH2 Proxy Installation Script
# Automated setup for production deployment
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="${1:-.}"
PROXY_USER="${PROXY_USER:-root}"
PROXY_GROUP="${PROXY_GROUP:-root}"

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "This script must be run as root"
    fi
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
    fi
    python3_version=$(python3 --version | awk '{print $2}')
    print_success "Python 3 found: $python3_version"
}

check_pmta() {
    if ! command -v pmta &> /dev/null; then
        print_warning "PowerMTA not found. Please install PMTA first."
        print_info "Visit: https://www.powernt.net/"
        return 1
    fi
    pmta_version=$(pmta --version 2>/dev/null || echo "unknown")
    print_success "PowerMTA found"
}

install_python_deps() {
    print_info "Installing Python dependencies..."
    pip3 install prometheus-client
    print_success "Python dependencies installed"
}

create_directories() {
    print_info "Creating directories..."
    mkdir -p /etc/xoauth2
    mkdir -p /opt/xoauth2
    mkdir -p /var/log/xoauth2
    mkdir -p /var/spool/xoauth2
    print_success "Directories created"
}

set_permissions() {
    print_info "Setting permissions..."
    chmod 750 /etc/xoauth2
    chmod 755 /var/log/xoauth2
    chmod 755 /var/spool/xoauth2
    print_success "Permissions set"
}

install_proxy_files() {
    print_info "Installing proxy files..."

    # Check if files exist in current directory
    if [ ! -f "$INSTALL_DIR/xoauth2_proxy.py" ]; then
        print_error "xoauth2_proxy.py not found in $INSTALL_DIR"
    fi

    if [ ! -f "$INSTALL_DIR/accounts.json" ]; then
        print_error "accounts.json not found in $INSTALL_DIR"
    fi

    # Copy files
    cp "$INSTALL_DIR/xoauth2_proxy.py" /opt/xoauth2/
    chmod 755 /opt/xoauth2/xoauth2_proxy.py

    cp "$INSTALL_DIR/accounts.json" /etc/xoauth2/
    chmod 600 /etc/xoauth2/accounts.json

    print_success "Proxy files installed"
}

install_pmta_config() {
    print_info "Installing PMTA configuration..."

    if [ ! -f "$INSTALL_DIR/pmta.cfg" ]; then
        print_warning "pmta.cfg not found - skipping PMTA config update"
        return 0
    fi

    # Backup existing config
    if [ -f /etc/pmta/pmta.cfg ]; then
        cp /etc/pmta/pmta.cfg /etc/pmta/pmta.cfg.backup.$(date +%Y%m%d_%H%M%S)
        print_info "Backed up existing pmta.cfg"
    fi

    cp "$INSTALL_DIR/pmta.cfg" /etc/pmta/pmta.cfg

    # Verify syntax
    if pmta check-config > /dev/null 2>&1; then
        print_success "PMTA configuration installed and verified"
    else
        print_error "PMTA configuration syntax error - restored backup"
        if [ -f /etc/pmta/pmta.cfg.backup.* ]; then
            cp /etc/pmta/pmta.cfg.backup.* /etc/pmta/pmta.cfg
        fi
    fi
}

install_systemd_service() {
    print_info "Installing systemd service..."

    cat > /etc/systemd/system/xoauth2-proxy.service << 'EOF'
[Unit]
Description=XOAUTH2 SMTP Proxy for PowerMTA
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/xoauth2
ExecStart=/usr/bin/python3 /opt/xoauth2/xoauth2_proxy.py \
  --config /etc/xoauth2/accounts.json \
  --host 127.0.0.1 \
  --port 2525 \
  --metrics-port 9090

Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=xoauth2-proxy

# Resource limits
LimitNOFILE=65536
LimitNPROC=65536

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable xoauth2-proxy
    print_success "Systemd service installed"
}

install_helper_scripts() {
    print_info "Installing helper scripts..."

    if [ -f "$INSTALL_DIR/generate_pmta_config.py" ]; then
        cp "$INSTALL_DIR/generate_pmta_config.py" /opt/xoauth2/
        chmod 755 /opt/xoauth2/generate_pmta_config.py
        print_success "Configuration generator installed"
    fi
}

install_documentation() {
    print_info "Installing documentation..."

    mkdir -p /opt/xoauth2/docs

    for doc in README.md DEPLOYMENT_GUIDE.md TEST_PLAN.md; do
        if [ -f "$INSTALL_DIR/$doc" ]; then
            cp "$INSTALL_DIR/$doc" /opt/xoauth2/docs/
        fi
    done

    print_success "Documentation installed"
}

verify_installation() {
    print_info "Verifying installation..."

    local errors=0

    # Check proxy file
    if [ ! -f /opt/xoauth2/xoauth2_proxy.py ]; then
        print_error "Proxy not found at /opt/xoauth2/xoauth2_proxy.py"
        errors=$((errors + 1))
    fi

    # Check config file
    if [ ! -f /etc/xoauth2/accounts.json ]; then
        print_error "Config not found at /etc/xoauth2/accounts.json"
        errors=$((errors + 1))
    fi

    # Check PMTA config
    if [ -f /etc/pmta/pmta.cfg ]; then
        if ! pmta check-config > /dev/null 2>&1; then
            print_error "PMTA config syntax error"
            errors=$((errors + 1))
        fi
    fi

    # Check systemd service
    if ! systemctl list-unit-files | grep -q xoauth2-proxy; then
        print_error "Systemd service not installed"
        errors=$((errors + 1))
    fi

    if [ $errors -eq 0 ]; then
        print_success "Installation verified successfully"
        return 0
    else
        print_error "Installation verification failed with $errors errors"
    fi
}

start_services() {
    print_info "Starting services..."

    # Start proxy
    systemctl start xoauth2-proxy
    if systemctl is-active --quiet xoauth2-proxy; then
        print_success "XOAUTH2 proxy started"
    else
        print_warning "Failed to start XOAUTH2 proxy - check logs"
    fi

    # Start PMTA
    if command -v pmta &> /dev/null; then
        systemctl start pmta
        if systemctl is-active --quiet pmta; then
            print_success "PMTA started"
        else
            print_warning "Failed to start PMTA - check logs"
        fi
    fi
}

show_status() {
    echo ""
    print_header "Installation Complete"
    echo ""

    print_info "Service Status:"
    systemctl status xoauth2-proxy --no-pager | head -5

    echo ""
    print_info "Configuration Files:"
    echo "  Proxy config:   /etc/xoauth2/accounts.json"
    echo "  PMTA config:    /etc/pmta/pmta.cfg"
    echo "  Proxy logs:     /var/log/xoauth2_proxy.log"
    echo "  PMTA logs:      /var/log/pmta/pmta.log"

    echo ""
    print_info "Useful Commands:"
    echo "  View status:    systemctl status xoauth2-proxy"
    echo "  View logs:      tail -f /var/log/xoauth2_proxy.log"
    echo "  Reload config:  kill -HUP \$(pgrep -f xoauth2_proxy)"
    echo "  Metrics:        curl http://127.0.0.1:9090/metrics"

    echo ""
    print_info "Next Steps:"
    echo "  1. Update /etc/xoauth2/accounts.json with your OAuth tokens"
    echo "  2. Review /etc/pmta/pmta.cfg and adjust IPs as needed"
    echo "  3. Run comprehensive tests from /opt/xoauth2/docs/TEST_PLAN.md"
    echo "  4. Monitor metrics at http://127.0.0.1:9090/metrics"

    echo ""
    print_success "Installation complete!"
}

show_usage() {
    cat << EOF
PowerMTA + XOAUTH2 Proxy Installation Script

Usage: $0 [INSTALL_DIR]

Arguments:
  INSTALL_DIR     Directory containing installation files
                  Default: current directory

Example:
  sudo $0 /path/to/ProxyPowermtaXOAUTH2

Environment Variables:
  PROXY_USER      User to run proxy as (default: root)
  PROXY_GROUP     Group for proxy (default: root)

EOF
}

################################################################################
# Main Installation Flow
################################################################################

main() {
    print_header "PowerMTA + XOAUTH2 Proxy Installation"

    # Pre-installation checks
    print_info "Performing pre-installation checks..."
    check_root
    check_python
    check_pmta

    echo ""

    # Install dependencies
    print_header "Installing Dependencies"
    install_python_deps

    echo ""

    # Create directories and set permissions
    print_header "Setting Up Directories"
    create_directories
    set_permissions

    echo ""

    # Install components
    print_header "Installing Components"
    install_proxy_files
    install_pmta_config
    install_systemd_service
    install_helper_scripts
    install_documentation

    echo ""

    # Verify and test
    print_header "Verifying Installation"
    verify_installation

    echo ""

    # Start services
    print_header "Starting Services"
    start_services

    echo ""

    # Show status and next steps
    show_status
}

################################################################################
# Entry Point
################################################################################

# Handle help flag
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    show_usage
    exit 0
fi

# Run main installation
main

exit 0
