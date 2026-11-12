#!/usr/bin/env bash
# Kept for convenience: delegates to the cross-platform launcher used by `npm run dev`.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
exec node scripts/dev.mjs "$@"
