---
name: ibkr
description: Interactive Brokers portfolio assistant — read-only access to account summary, positions, quotes, and options context via MCP.
version: 0.1.0
author: Dakota + Copilot Agent
license: MIT
metadata:
  hermes:
    tags: [trading, ibkr, interactive-brokers, mcp, finance]
    requires_mcp: true
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
---

# IBKR Portfolio Assistant

Read-only access to your Interactive Brokers account via `ibkr-mcp`.

## Required environment variables

- `IBKR_ACCOUNT` (required)
- `IBKR_HOST` (default: `127.0.0.1`)
- `IBKR_PORT` (default: `4001` for IB Gateway, often `7497` for TWS paper)
- `IBKR_CLIENT_ID` (default: `0`)
- `IBKR_MCP_MARKET_DATA_TYPE` (`LIVE` or `FROZEN`)

## Setup

```bash
bash scripts/install_ibkr.sh
```

For non-interactive setup:

```bash
IBKR_ACCOUNT="U1234567" \
IBKR_HOST="127.0.0.1" \
IBKR_PORT="4001" \
IBKR_CLIENT_ID="0" \
IBKR_MCP_MARKET_DATA_TYPE="LIVE" \
bash scripts/install_ibkr.sh --non-interactive
```

## Notes

- This skill assumes TWS or IB Gateway is running with API access enabled.
- This repository does not place orders; use it for read-only research and monitoring workflows.
