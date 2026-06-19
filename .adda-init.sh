#!/bin/bash
set -euo pipefail
# Repo-level init hook for adda-dev-launcher.
# Invoked as a subprocess by the entrypoint at bootstrap and by current-issue switch mid-session.
# Inputs:  none (no dependencies to install for a shell project)
# Outputs: .git/hooks/pre-commit installed; stale CLAUDE.local.md removed

rm -f /workspace/CLAUDE.local.md

# Install pre-commit hook that gates commits on quality-gates (inside dev container only)
PRE_COMMIT=.git/hooks/pre-commit
if [ ! -f "$PRE_COMMIT" ]; then
    cat > "$PRE_COMMIT" <<'HOOK'
#!/bin/sh
HOOK_BIN=/usr/local/libexec/adda-dev-runtime/bin/quality-gates
if [ -x "$HOOK_BIN" ]; then
    exec "$HOOK_BIN"
fi
HOOK
    chmod +x "$PRE_COMMIT"
fi
