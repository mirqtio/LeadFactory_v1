#!/bin/bash
# Enterprise Shim Wrapper Script
# Properly activates virtual environment and starts enterprise shim

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <agent_type> <tmux_session> [additional_args...]"
    echo "Agent types: orchestrator, pm, dev, validator, integrator"
    exit 1
fi

AGENT_TYPE="$1"
TMUX_SESSION="$2"
shift 2

# Activate virtual environment
cd "$PROJECT_ROOT"
source .venv/bin/activate

# Set environment variables
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"

# Start enterprise shim
exec python3 bin/enterprise_shim.py "$AGENT_TYPE" "$TMUX_SESSION" "$@"