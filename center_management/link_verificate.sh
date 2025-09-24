#!/usr/bin/env bash
# test_hysteria.sh — start a local hysteria client from a hyst2 link and verify via socks5 curl
set -euo pipefail

# Create logs directory if it doesn't exist
LOGS_DIR="./logs"
mkdir -p "$LOGS_DIR"

# Cleanup function
cleanup() {
    if [[ -n "${HY_PID:-}" ]]; then
        kill $HY_PID 2>/dev/null || true
    fi
    rm -f tmp.json
    if [[ -f "hysteria.log" ]]; then
        rm -f hysteria.log
    fi
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Logging function
log_failure() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_file="$LOGS_DIR/hysteria_failures.log"
    echo "[$timestamp] FAILED: URI=$URI, HOST=$HOST, PORT=$PORT, AUTH=$AUTH, ERROR=$1" >> "$log_file"
    echo "[$timestamp] Hysteria log:" >> "$log_file"
    if [[ -f "hysteria.log" ]]; then
        tail -20 "hysteria.log" >> "$log_file"
    fi
    echo "---" >> "$log_file"
}

log_success() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_file="$LOGS_DIR/hysteria_success.log"
    echo "[$timestamp] SUCCESS: URI=$URI, HOST=$HOST, PORT=$PORT, AUTH=$AUTH, STATUS=$1" >> "$log_file"
}

# Authentication validation function
validate_auth() {
    local auth="$1"
    if [[ -z "$auth" ]]; then
        log_failure "Empty authentication token"
        return 1
    fi

    # Check if auth token follows UUID format (basic validation)
    if [[ ! "$auth" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
        log_failure "Invalid authentication token format: $auth"
        return 1
    fi

    return 0
}

usage() {
    cat <<EOF
Usage: $0 [-z URI] | URI
Example:
    $0 -z "hysteria2://uuid@1.2.3.4:9989?security=tls&alpn=h3&insecure=1&sni=www.bing.com"
Options:
    -z, --uri   hysteria2 URI
    -h, --help  show this help
EOF
    exit 2
}

URI=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -z|--uri)
            URI="$2"; shift 2;;
        -h|--help)
            usage;;
        --)
            shift; break;;
        -*)
            echo "Unknown option: $1" >&2; usage;;
        *)
            # positional argument
            if [[ -z "$URI" ]]; then
                URI="$1"
            fi
            shift;;
    esac
done

if [[ -z "$URI" ]]; then
    echo "No URI provided" >&2
    usage
fi

# Basic URI validation
if [[ ! "$URI" =~ ^hysteria2:// ]]; then
    echo "❌ Invalid URI format. Must start with 'hysteria2://'" >&2
    log_failure "Invalid URI format: $URI"
    exit 7
fi

# create tmp client config from URI using pure bash
# Parse URI components
PROTO="${URI%%://*}"
REST="${URI#*://}"
REST="${REST%%#*}"  # Remove fragment
AUTH="${REST%%@*}"
HOST_PORT="${REST#*@}"
# Extract port and query separately
HOST="${HOST_PORT%%:*}"
PORT_QUERY="${HOST_PORT#*:}"
PORT="${PORT_QUERY%%\?*}"
QUERY="${PORT_QUERY#*\?}"

# Parse query parameters
SNI="www.bing.com"
if [[ -n "$QUERY" && "$QUERY" != "$PORT_QUERY" ]]; then
    # Extract SNI from query (remove fragment first)
    QUERY_CLEAN="${QUERY%%#*}"
    SNI_PART="${QUERY_CLEAN##*sni=}"
    if [[ "$SNI_PART" != "$QUERY_CLEAN" ]]; then
        SNI="${SNI_PART%%&*}"
        SNI="${SNI%%#*}"  # Remove any remaining fragment
    fi
fi

# Validate authentication token
echo "Validating authentication token..."
if ! validate_auth "$AUTH"; then
    echo "❌ 认证验证失败" >&2
    exit 5
fi
echo "✅ 认证验证通过"

# Create JSON config file
cat > tmp.json <<EOF
{
  "server": "$HOST:$PORT",
  "auth": "$AUTH",
  "tls": {
    "sni": "$SNI",
    "insecure": true,
    "alpn": ["h3"]
  },
  "socks5": {
    "listen": "127.0.0.1:1080"
  }
}
EOF

# start hysteria client
HYSTERIA_BIN="./hysteria"
if [[ ! -x "$HYSTERIA_BIN" ]]; then
    echo "Warning: hysteria binary not found or not executable at $HYSTERIA_BIN" >&2
    echo "Please put hysteria client next to this script or edit HYSTERIA_BIN." >&2
    log_failure "Hysteria binary not found or not executable at $HYSTERIA_BIN"
    exit 6
fi

"$HYSTERIA_BIN" client -c tmp.json >hysteria.log 2>&1 &
HY_PID=$!

# wait for local socks5 listen (timeout) by trying to open a TCP connection
echo "Waiting for local socks5 127.0.0.1:1080 to be ready..."
WAIT=0
MAX_WAIT=15
while true; do
    # try opening a TCP connection using bash /dev/tcp — quick and reliable
    if (echo > /dev/tcp/127.0.0.1/1080) >/dev/null 2>&1; then
        break
    fi
    sleep 1
    WAIT=$((WAIT+1))
    if [[ $WAIT -ge $MAX_WAIT ]]; then
        echo "socks5 not listening after ${MAX_WAIT}s. Showing hysteria.log:" >&2
        sed -n '1,200p' hysteria.log >&2 || true
        log_failure "Connection timeout - socks5 proxy not ready after ${MAX_WAIT}s"
        kill $HY_PID 2>/dev/null || true
        rm -f tmp.json
        exit 3
    fi
done

echo "socks5 is listening, testing via curl"
status=$(curl -s -o /dev/null -w "%{http_code}" -x socks5h://127.0.0.1:1080 https://google.com || true)
echo "HTTP status: ${status}"
if [[ "$status" == "301" ]]; then
    echo "✅ 代理测试成功（返回 301 重定向）"
    log_success "HTTP $status - Proxy test successful"
    RC=0
else
    echo "❌ 代理测试未通过，状态码: ${status}"
    log_failure "Proxy test failed - HTTP status: ${status}"
    RC=4
fi

exit $RC