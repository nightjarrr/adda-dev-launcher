# Conventions

## Bash

- Open with `#!/bin/bash` and `set -euo pipefail`.
- Begin each script with a brief comment block stating purpose, inputs, and outputs.
- Structure logic into named functions; group related functions under `# ---`-delimited section headings.
- `# shellcheck disable=SC…` requires a `# Why:` comment on the immediately following line.

### Style

- Prefer `[[ … ]]` over `[ … ]` for conditionals.
- Quote all variable expansions: `"${var}"`.
- Use `local` for variables inside functions.
- Prefer `printf` over `echo` for output that must be portable or include escape sequences.
- Keep functions short and single-purpose.
