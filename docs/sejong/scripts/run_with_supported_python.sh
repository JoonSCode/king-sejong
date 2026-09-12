#!/usr/bin/env bash

# This file is both a sourceable runtime selector and the public launcher for
# King Sejong Python tools. It never changes the system Python or installs a
# global package.

sejong_select_python() {
  local candidate
  local candidate_path
  local uv_path
  local uv_python

  for candidate in python3 python3.14 python3.13 python3.12 python3.11; do
    candidate_path=$(command -v "$candidate" 2>/dev/null || true)
    if [[ -n "$candidate_path" ]] && "$candidate_path" -c \
      'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
      >/dev/null 2>&1; then
      SEJONG_PYTHON_COMMAND=("$candidate_path")
      return 0
    fi
  done

  uv_path=$(command -v uv 2>/dev/null || true)
  if [[ -n "$uv_path" ]]; then
    uv_python=$("$uv_path" python find '>=3.11' 2>/dev/null || true)
    SEJONG_PYTHON_COMMAND=("$uv_python")
    if [[ -n "$uv_python" && -x "$uv_python" ]] && "$uv_python" -c \
      'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
      >/dev/null 2>&1; then
      return 0
    fi
    echo "King Sejong found uv, but uv could not provide Python 3.11 or newer." >&2
    echo "Run 'uv python install 3.11', then retry. The system Python does not need to change." >&2
    return 127
  fi

  echo "King Sejong requires Python 3.11 or newer, or uv." >&2
  echo "Install either runtime, then retry. The system Python does not need to change." >&2
  return 127
}

sejong_run_python() {
  "${SEJONG_PYTHON_COMMAND[@]}" "$@"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  set -euo pipefail
  sejong_select_python
  export PYTHONDONTWRITEBYTECODE=1
  exec "${SEJONG_PYTHON_COMMAND[@]}" "$@"
fi
