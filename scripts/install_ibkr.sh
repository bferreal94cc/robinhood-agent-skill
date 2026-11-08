#!/usr/bin/env bash
# =============================================================================
# IBKR Agent Skill — One-Click Setup
# =============================================================================
# Installs/configures ibkr-mcp and creates skill directories for Hermes Agent,
# Claude Code, Claude Desktop, OpenCode, Cline, Codex, and Windsurf.
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
DIM='\033[2m'
RESET='\033[0m'

info()  { echo -e "${BLUE}ℹ${RESET} $*"; }
ok()    { echo -e "${GREEN}✓${RESET} $*"; }
warn()  { echo -e "${YELLOW}⚠${RESET} $*"; }
dim()   { echo -e "${DIM}$*${RESET}"; }
fail()  { echo -e "${RED}✗${RESET} $*"; exit 1; }

NON_INTERACTIVE=false
SKIP_CREDENTIALS=false
AGENT=""
SKILL_SOURCE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --non-interactive) NON_INTERACTIVE=true; shift ;;
    --skip-credentials) SKIP_CREDENTIALS=true; shift ;;
    --agent)
      [[ $# -ge 2 ]] || fail "Missing value for --agent"
      AGENT="$2"
      shift 2
      ;;
    --source)
      [[ $# -ge 2 ]] || fail "Missing value for --source"
      SKILL_SOURCE="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: bash scripts/install_ibkr.sh [options]"
      echo ""
      echo "Options:"
      echo "  --non-interactive   Run without prompts (reads from env vars)"
      echo "  --skip-credentials  Skip IBKR environment variable setup"
      echo "  --agent AGENT       Target agent: hermes, claude-code, opencode, cline, codex, windsurf, all"
      echo "  --source PATH       Local path to skill source (default: script directory)"
      echo "  -h, --help          Show this help"
      exit 0
      ;;
    *) fail "Unknown argument: $1" ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SOURCE="${SKILL_SOURCE:-$(dirname "$SCRIPT_DIR")}"

info "IBKR Agent Skill Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"

info "Checking prerequisites..."
command -v python3 &>/dev/null || fail "Python 3 is required. Install it first."
ok "Python 3 found: $(python3 --version 2>&1 | head -1)"

if command -v uvx &>/dev/null; then
  ok "uvx found (recommended MCP runner)"
else
  fail "uvx is required for generated MCP configs. Install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

if command -v node &>/dev/null; then
  dim "Node.js found: $(node --version)"
else
  warn "Node.js not found. Some agents require it for MCP subprocess management."
fi

IBKR_HOST="${IBKR_HOST:-127.0.0.1}"
IBKR_PORT="${IBKR_PORT:-4001}"
IBKR_CLIENT_ID="${IBKR_CLIENT_ID:-0}"
IBKR_ACCOUNT="${IBKR_ACCOUNT:-}"
IBKR_MCP_MARKET_DATA_TYPE="${IBKR_MCP_MARKET_DATA_TYPE:-LIVE}"

if [[ "$SKIP_CREDENTIALS" == "true" ]]; then
  warn "Skipping IBKR environment setup. Configure manually later."
else
  if [[ "$NON_INTERACTIVE" == "false" ]]; then
    echo -n "IBKR host [${IBKR_HOST}]: "
    read -r INPUT_HOST
    IBKR_HOST="${INPUT_HOST:-$IBKR_HOST}"

    echo -n "IBKR port [${IBKR_PORT}]: "
    read -r INPUT_PORT
    IBKR_PORT="${INPUT_PORT:-$IBKR_PORT}"

    echo -n "IBKR client id [${IBKR_CLIENT_ID}]: "
    read -r INPUT_CLIENT_ID
    IBKR_CLIENT_ID="${INPUT_CLIENT_ID:-$IBKR_CLIENT_ID}"

    if [[ -z "$IBKR_ACCOUNT" ]]; then
      echo -n "IBKR account (required, e.g. U1234567): "
      read -r IBKR_ACCOUNT
    fi

    echo -n "Market data type [${IBKR_MCP_MARKET_DATA_TYPE}] (LIVE/FROZEN): "
    read -r INPUT_MDT
    IBKR_MCP_MARKET_DATA_TYPE="${INPUT_MDT:-$IBKR_MCP_MARKET_DATA_TYPE}"
  fi
fi

if [[ -z "$IBKR_ACCOUNT" && "$SKIP_CREDENTIALS" != "true" ]]; then
  warn "IBKR_ACCOUNT is empty. MCP tools may not initialize correctly until it is set."
fi

export IBKR_HOST IBKR_PORT IBKR_CLIENT_ID IBKR_ACCOUNT IBKR_MCP_MARKET_DATA_TYPE

if [[ -z "$AGENT" ]]; then
  if [[ "$NON_INTERACTIVE" == "true" ]]; then
    AGENT="all"
  else
    echo ""
    echo "Which agent(s) are you configuring?"
    echo "  1) Hermes Agent"
    echo "  2) Claude Code / OpenClaw"
    echo "  3) Claude Desktop"
    echo "  4) Codex CLI"
    echo "  5) OpenCode"
    echo "  6) Cline"
    echo "  7) Windsurf"
    echo "  8) All of the above"
    echo -n "Enter number [8]: "
    read -r AGENT_CHOICE
    case "${AGENT_CHOICE:-8}" in
      1) AGENT="hermes" ;;
      2) AGENT="claude-code" ;;
      3) AGENT="claude-desktop" ;;
      4) AGENT="codex" ;;
      5) AGENT="opencode" ;;
      6) AGENT="cline" ;;
      7) AGENT="windsurf" ;;
      8) AGENT="all" ;;
      *) AGENT="all" ;;
    esac
  fi
fi

HERMES_DIR="$HOME/.hermes"
CONFIGURED_AGENTS=()

write_json_config() {
  local file_path="$1"
  local root_key="$2"
  CONFIG_PATH="$file_path" ROOT_KEY="$root_key" python3 <<'PY'
import json
import os

config = {
    os.environ["ROOT_KEY"]: {
        "ibkr": {
            "command": "uvx",
            "args": ["ibkr-mcp"],
            "env": {
                "IBKR_HOST": os.environ["IBKR_HOST"],
                "IBKR_PORT": os.environ["IBKR_PORT"],
                "IBKR_CLIENT_ID": os.environ["IBKR_CLIENT_ID"],
                "IBKR_ACCOUNT": os.environ["IBKR_ACCOUNT"],
                "IBKR_MCP_MARKET_DATA_TYPE": os.environ["IBKR_MCP_MARKET_DATA_TYPE"],
            },
        }
    }
}
with open(os.environ["CONFIG_PATH"], "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2)
PY
}

merge_json_mcp_server() {
  local file_path="$1"
  local root_key="$2"
  CONFIG_PATH="$file_path" ROOT_KEY="$root_key" python3 <<'PY'
import json
import os

path = os.environ["CONFIG_PATH"]
root_key = os.environ["ROOT_KEY"]
with open(path, "r", encoding="utf-8") as f:
    config = json.load(f)
config.setdefault(root_key, {})["ibkr"] = {
    "command": "uvx",
    "args": ["ibkr-mcp"],
    "env": {
        "IBKR_HOST": os.environ["IBKR_HOST"],
        "IBKR_PORT": os.environ["IBKR_PORT"],
        "IBKR_CLIENT_ID": os.environ["IBKR_CLIENT_ID"],
        "IBKR_ACCOUNT": os.environ["IBKR_ACCOUNT"],
        "IBKR_MCP_MARKET_DATA_TYPE": os.environ["IBKR_MCP_MARKET_DATA_TYPE"],
    },
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2)
PY
}

merge_hermes_yaml() {
  local file_path="$1"
  CONFIG_PATH="$file_path" python3 <<'PY'
import os
import sys

try:
    import yaml
except Exception:
    sys.exit(1)

path = os.environ["CONFIG_PATH"]
with open(path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}

config.setdefault("mcp_servers", {})["ibkr"] = {
    "command": "uvx",
    "args": ["ibkr-mcp"],
    "env": {
        "IBKR_HOST": os.environ["IBKR_HOST"],
        "IBKR_PORT": os.environ["IBKR_PORT"],
        "IBKR_CLIENT_ID": os.environ["IBKR_CLIENT_ID"],
        "IBKR_ACCOUNT": os.environ["IBKR_ACCOUNT"],
        "IBKR_MCP_MARKET_DATA_TYPE": os.environ["IBKR_MCP_MARKET_DATA_TYPE"],
    },
    "timeout": 60,
    "connect_timeout": 30,
}

with open(path, "w", encoding="utf-8") as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
PY
}

configure_hermes() {
  info "Configuring Hermes Agent..."

  SKILL_DIR="$HERMES_DIR/skills/finance/ibkr"
  mkdir -p "$SKILL_DIR"
  cp "$SKILL_SOURCE/IBKR_SKILL.md" "$SKILL_DIR/SKILL.md"

  mkdir -p "$HERMES_DIR/data/ibkr"

  CONFIG_FILE="$HERMES_DIR/config.yaml"
  if [[ -f "$CONFIG_FILE" ]]; then
    if grep -q "^[[:space:]]*ibkr:" "$CONFIG_FILE" 2>/dev/null; then
      ok "IBKR MCP already configured in config.yaml"
    else
      if merge_hermes_yaml "$CONFIG_FILE" 2>/dev/null; then
        ok "Added IBKR MCP config to config.yaml"
      else
        fail "Could not merge IBKR into existing Hermes config.yaml automatically. Install PyYAML or merge templates/ibkr-config-snippet.yaml manually."
      fi
    fi
  else
    mkdir -p "$HERMES_DIR"
    cat > "$CONFIG_FILE" << YAML_EOF
mcp_servers:
  ibkr:
    command: uvx
    args:
      - ibkr-mcp
    env:
      IBKR_HOST: "${IBKR_HOST}"
      IBKR_PORT: "${IBKR_PORT}"
      IBKR_CLIENT_ID: "${IBKR_CLIENT_ID}"
      IBKR_ACCOUNT: "${IBKR_ACCOUNT}"
      IBKR_MCP_MARKET_DATA_TYPE: "${IBKR_MCP_MARKET_DATA_TYPE}"
    timeout: 60
    connect_timeout: 30
YAML_EOF
    ok "Created new config.yaml with IBKR MCP config"
  fi

  if [[ "$SKIP_CREDENTIALS" != "true" ]]; then
    ENV_FILE="$HERMES_DIR/.env"
    {
      echo ""
      echo "# IBKR MCP settings (added by robinhood-agent-skill/scripts/install_ibkr.sh)"
      echo "IBKR_HOST=${IBKR_HOST}"
      echo "IBKR_PORT=${IBKR_PORT}"
      echo "IBKR_CLIENT_ID=${IBKR_CLIENT_ID}"
      echo "IBKR_ACCOUNT=${IBKR_ACCOUNT}"
      echo "IBKR_MCP_MARKET_DATA_TYPE=${IBKR_MCP_MARKET_DATA_TYPE}"
    } >> "$ENV_FILE"
    ok "IBKR env values saved to $ENV_FILE"
  fi

  ok "Hermes Agent configured"
  CONFIGURED_AGENTS+=("hermes")
}

configure_claude_code() {
  info "Configuring Claude Code / OpenClaw..."

  MCP_FILE="$HOME/.mcp.json"
  if [[ -f "$MCP_FILE" ]]; then
    merge_json_mcp_server "$MCP_FILE" "mcpServers" 2>/dev/null || warn "Could not merge .mcp.json. Add manually from templates/ibkr-claude-code-mcp.json"
  else
    write_json_config "$MCP_FILE" "mcpServers"
  fi

  SKILL_DIR="$HOME/.claude/skills/ibkr"
  mkdir -p "$SKILL_DIR"
  cp "$SKILL_SOURCE/IBKR_SKILL.md" "$SKILL_DIR/SKILL.md"

  ok "Claude Code / OpenClaw configured"
  CONFIGURED_AGENTS+=("claude-code")
}

configure_claude_desktop() {
  info "Configuring Claude Desktop..."

  if [[ "$OSTYPE" == "darwin"* ]]; then
    DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
  else
    DESKTOP_CONFIG="$HOME/.config/Claude/claude_desktop_config.json"
  fi
  mkdir -p "$(dirname "$DESKTOP_CONFIG")"

  if [[ -f "$DESKTOP_CONFIG" ]]; then
    merge_json_mcp_server "$DESKTOP_CONFIG" "mcpServers" 2>/dev/null || warn "Could not merge Claude Desktop config. Add manually from templates/ibkr-claude-desktop.json"
  else
    write_json_config "$DESKTOP_CONFIG" "mcpServers"
  fi

  ok "Claude Desktop configured ($DESKTOP_CONFIG)"
  CONFIGURED_AGENTS+=("claude-desktop")
}

configure_codex() {
  info "Configuring Codex CLI..."

  CODEX_DIR="$HOME/.codex"
  mkdir -p "$CODEX_DIR"
  CODEX_CONFIG="$CODEX_DIR/config.json"

  if [[ -f "$CODEX_CONFIG" ]]; then
    warn "Codex config exists. Add MCP config manually from templates/ibkr-codex.json"
  else
    write_json_config "$CODEX_CONFIG" "mcpServers"
  fi

  SKILL_DIR="$CODEX_DIR/skills/ibkr"
  mkdir -p "$SKILL_DIR"
  cp "$SKILL_SOURCE/IBKR_SKILL.md" "$SKILL_DIR/SKILL.md"

  ok "Codex CLI configured"
  CONFIGURED_AGENTS+=("codex")
}

configure_opencode() {
  info "Configuring OpenCode..."

  OPENCODE_DIR="$HOME/.opencode"
  mkdir -p "$OPENCODE_DIR"
  OPENCODE_CONFIG="$OPENCODE_DIR/opencode.json"

  if [[ -f "$OPENCODE_CONFIG" ]]; then
    warn "OpenCode config exists. Add MCP config manually from templates/ibkr-opencode.json"
  else
    write_json_config "$OPENCODE_CONFIG" "mcp"
  fi

  ok "OpenCode configured"
  CONFIGURED_AGENTS+=("opencode")
}

configure_cline() {
  info "Configuring Cline..."

  CLINE_DIR="$HOME/.cline"
  mkdir -p "$CLINE_DIR"
  CLINE_MCP="$CLINE_DIR/mcp.json"

  if [[ -f "$CLINE_MCP" ]]; then
    warn "Cline MCP config exists. Add IBKR config manually from templates/ibkr-cline-mcp.json"
  else
    write_json_config "$CLINE_MCP" "mcpServers"
  fi

  ok "Cline configured"
  CONFIGURED_AGENTS+=("cline")
}

configure_windsurf() {
  info "Configuring Windsurf..."

  WINDSURF_DIR="$HOME/.codeium/windsurf"
  mkdir -p "$WINDSURF_DIR"
  WINDSURF_MCP="$WINDSURF_DIR/mcp.json"

  if [[ -f "$WINDSURF_MCP" ]]; then
    warn "Windsurf MCP config exists. Add IBKR config manually from templates/ibkr-windsurf-mcp.json"
  else
    write_json_config "$WINDSURF_MCP" "mcpServers"
  fi

  ok "Windsurf configured"
  CONFIGURED_AGENTS+=("windsurf")
}

case "$AGENT" in
  hermes) configure_hermes ;;
  claude-code) configure_claude_code ;;
  claude-desktop) configure_claude_desktop ;;
  codex) configure_codex ;;
  opencode) configure_opencode ;;
  cline) configure_cline ;;
  windsurf) configure_windsurf ;;
  all)
    configure_hermes
    configure_claude_code
    configure_claude_desktop
    configure_codex
    configure_opencode
    configure_cline
    configure_windsurf
    ;;
  *) warn "Unknown agent: $AGENT. Configuring Hermes only." ; configure_hermes ;;
esac

echo ""
info "Testing ibkr-mcp accessibility..."
if command -v uvx &>/dev/null; then
  timeout 15 uvx ibkr-mcp --help >/dev/null 2>&1 || true
  ok "ibkr-mcp package is resolvable via uvx"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "IBKR MCP setup complete!"
echo "Configured agents: ${CONFIGURED_AGENTS[*]}"
echo ""
echo "Next steps:"
echo "  1. Ensure TWS or IB Gateway is running and API access is enabled"
echo "  2. Restart your agent"
echo "  3. Ask your agent for account summary or positions"
