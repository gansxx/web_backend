#!/usr/bin/env bash
# test_hysteria.sh
set -e

usage() {
    cat <<EOF
Usage: $0 <URI>
Example: $0 "hysteria2://uuid@1.2.3.4:9989?security=tls&alpn=h3&insecure=1&sni=www.bing.com"
EOF
    exit 1
}

#!/usr/bin/env bash
# test_hysteria.sh — start a local hysteria client from a hyst2 link and verify via socks5 curl
set -euo pipefail

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

# create tmp client config from URI
python3 <<PYEOF
import urllib.parse, yaml
u = urllib.parse.urlparse("$URI")
qs = urllib.parse.parse_qs(u.query)
sni = qs.get('sni', [None])[0]
cfg = {
        'server': f"{u.hostname}:{u.port}",
        'auth': u.username,
        'tls': {'sni': sni or 'www.bing.com', 'insecure': True, 'alpn': ['h3']},
        'socks5': {'listen': '127.0.0.1:1080'}
}
print(cfg)
yaml.dump(cfg, open('tmp.yml', 'w'))
PYEOF

# start hysteria client
HYSTERIA_BIN="./hysteria"
if [[ ! -x "$HYSTERIA_BIN" ]]; then
    echo "Warning: hysteria binary not found or not executable at $HYSTERIA_BIN" >&2
    echo "Please put hysteria client next to this script or edit HYSTERIA_BIN." >&2
fi

"$HYSTERIA_BIN" client -c tmp.yml >hysteria.log 2>&1 &
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
        kill $HY_PID 2>/dev/null || true
        rm -f tmp.yml
        exit 3
    fi
done

echo "socks5 is listening, testing via curl"
status=$(curl -s -o /dev/null -w "%{http_code}" -x socks5h://127.0.0.1:1080 https://google.com || true)
echo "HTTP status: ${status}"
if [[ "$status" == "301" ]]; then
    echo "✅ 代理测试成功（返回 301 重定向）"
    RC=0
else
    echo "❌ 代理测试未通过，状态码: ${status}"
    RC=4
fi

# cleanup
kill $HY_PID 2>/dev/null || true
rm -f tmp.yml
exit $RC