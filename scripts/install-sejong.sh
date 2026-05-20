#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/install-sejong.sh [--force] [target-repo]

Examples:
  scripts/install-sejong.sh /path/to/your-repo
  scripts/install-sejong.sh --force /path/to/your-repo

Installs:
  .agents/skills/sejong/
  .agents/skills/uigwe/
  .agents/skills/seungjeongwon/
  docs/sejong/
EOF
}

FORCE=0
TARGET_REPO="."

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --force)
      FORCE=1
      shift
      ;;
    *)
      TARGET_REPO=$1
      shift
      ;;
  esac
done

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SOURCE_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

if [[ ! -d "$TARGET_REPO" ]]; then
  echo "target repo does not exist: $TARGET_REPO" >&2
  exit 1
fi

TARGET_ROOT=$(cd "$TARGET_REPO" && pwd)

if [[ ! -d "$TARGET_ROOT/.git" && ! -f "$TARGET_ROOT/.git" ]]; then
  echo "target is not a git repository: $TARGET_ROOT" >&2
  exit 1
fi

if [[ "$TARGET_ROOT" == "$SOURCE_ROOT" ]]; then
  echo "King Sejong is already present in this repository."
  exit 0
fi

copy_dir() {
  local src=$1
  local dest=$2

  if [[ ! -d "$src" ]]; then
    echo "missing source directory: $src" >&2
    exit 1
  fi

  if [[ -e "$dest" && "$FORCE" -ne 1 ]]; then
    echo "destination already exists: $dest" >&2
    echo "rerun with --force to replace the managed install path" >&2
    exit 1
  fi

  mkdir -p "$(dirname "$dest")"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '.DS_Store' \
      --exclude '__pycache__/' \
      "$src/" "$dest/"
  else
    rm -rf "$dest"
    cp -R "$src" "$dest"
  fi
}

copy_dir "$SOURCE_ROOT/.agents/skills/sejong" "$TARGET_ROOT/.agents/skills/sejong"
copy_dir "$SOURCE_ROOT/.agents/skills/uigwe" "$TARGET_ROOT/.agents/skills/uigwe"
copy_dir "$SOURCE_ROOT/.agents/skills/seungjeongwon" "$TARGET_ROOT/.agents/skills/seungjeongwon"
copy_dir "$SOURCE_ROOT/docs/sejong" "$TARGET_ROOT/docs/sejong"

cat <<EOF
Installed King Sejong into:
  $TARGET_ROOT

Managed paths:
  .agents/skills/sejong/
  .agents/skills/uigwe/
  .agents/skills/seungjeongwon/
  docs/sejong/

Invoke with:
  \$sejong <broad request>
  \$uigwe <formal planning request>
  \$seungjeongwon <execution request>
EOF
