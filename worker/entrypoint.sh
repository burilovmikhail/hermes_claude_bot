#!/bin/bash
set -e

# Create Claude Code settings.json with API key from environment
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "Configuring Claude Code with API key..."
    mkdir -p "$HOME/.config/claude-code"
    cat > "$HOME/.config/claude-code/settings.json" <<EOF
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

# Configure git to trust the workspace directory
echo "Configuring git safe.directory for /workspace..."
git config --global --add safe.directory '*'

# Verify GitHub CLI is available and will use GITHUB_TOKEN from environment
if [ -n "$GITHUB_TOKEN" ]; then
    echo "GitHub CLI will use GITHUB_TOKEN from environment"
    # GitHub CLI automatically uses GITHUB_TOKEN env var, no need to login
else
    echo "WARNING: GITHUB_TOKEN not set. GitHub CLI operations may fail!"
fi

# Verify Claude Code is available
if command -v claude &> /dev/null; then
    echo "Claude Code found at: $(which claude)"
    echo "Running as user: $(whoami)"
else
    echo "WARNING: Claude Code not found in PATH!"
fi

# Start the worker
exec python main.py
