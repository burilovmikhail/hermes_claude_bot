#!/bin/bash
set -e

# Create Claude Code settings.json with API key from environment
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "Configuring Claude Code with API key..."
    cat > /root/.config/claude-code/settings.json <<EOF
{
  "apiKeyHelper": {
    "type": "env",
    "envVar": "ANTHROPIC_API_KEY"
  },
  "model": "${CLAUDE_MODEL:-claude-3-5-sonnet-20250122}",
  "shell": {
    "bash": "/bin/bash"
  }
}
EOF
    echo "Claude Code configured successfully"
else
    echo "WARNING: ANTHROPIC_API_KEY not set. Claude Code will not work!"
fi

# Verify Claude Code is available
if command -v claude &> /dev/null; then
    echo "Claude Code found at: $(which claude)"
else
    echo "WARNING: Claude Code not found in PATH!"
fi

# Start the worker
exec python main.py
