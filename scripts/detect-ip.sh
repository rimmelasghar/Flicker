#!/bin/sh
# Detect this computer's LAN IP address and write it as HOST_IP into .env
# (macOS and Linux). Creates .env from .env.example if it does not exist.
# Usage: scripts/detect-ip.sh [path/to/.env]
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
env_file=${1:-"$root/.env"}

detect() {
  case "$(uname -s)" in
    Darwin)
      iface=$(route -n get default 2>/dev/null | awk '/interface:/ {print $2}')
      [ -n "$iface" ] && ipconfig getifaddr "$iface"
      ;;
    *)
      # Source address the kernel would use to reach the internet.
      ip -4 route get 1.1.1.1 2>/dev/null |
        awk '{for (i = 1; i < NF; i++) if ($i == "src") {print $(i + 1); exit}}'
      ;;
  esac
}

host_ip=$(detect || true)
if [ -z "$host_ip" ]; then
  echo "Could not detect the LAN IP address. Are you connected to Wi-Fi?" >&2
  echo "Set HOST_IP in $env_file by hand." >&2
  exit 1
fi

if [ ! -f "$env_file" ]; then
  cp "$root/.env.example" "$env_file"
  echo "Created $env_file from .env.example"
fi

tmp="$env_file.tmp"
awk -v ip="$host_ip" '
  /^HOST_IP=/ { print "HOST_IP=" ip; done = 1; next }
  { print }
  END { if (!done) print "HOST_IP=" ip }
' "$env_file" > "$tmp"
mv "$tmp" "$env_file"

echo "HOST_IP=$host_ip written to $env_file"
echo "Restart Flick to use it: docker compose up -d"
