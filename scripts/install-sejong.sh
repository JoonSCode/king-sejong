#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/install-sejong.sh [--force] [--dry-run] [target-repo]
  scripts/install-sejong.sh --verify [target-repo]

Examples:
  scripts/install-sejong.sh /path/to/your-repo
  scripts/install-sejong.sh --force /path/to/your-repo
  scripts/install-sejong.sh --verify /path/to/your-repo

Installs:
  .agents/skills/sejong/
  .agents/skills/uigwe/
  .agents/skills/seungjeongwon/
  docs/sejong/
EOF
}

FORCE=0
DRY_RUN=0
VERIFY_ONLY=0
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
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --verify|--check)
      VERIFY_ONLY=1
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

verify_install() {
  local root=$1
  local missing=0
  local required_paths=(
    ".agents/skills/sejong/SKILL.md"
    ".agents/skills/uigwe/SKILL.md"
    ".agents/skills/seungjeongwon/SKILL.md"
    "docs/sejong/README.md"
    "docs/sejong/ROUTER.md"
    "docs/sejong/PROMPT_OVERLAYS.md"
    "docs/sejong/PROTOCOL.md"
    "docs/sejong/SEUNGJEONGWON_EXECUTOR.md"
    "docs/sejong/BUNDLE_VALIDATOR.md"
    "docs/sejong/scripts/validate_json_contracts.py"
  )

  for path in "${required_paths[@]}"; do
    if [[ ! -e "$root/$path" ]]; then
      echo "missing: $path" >&2
      missing=1
    fi
  done

  if [[ "$missing" -ne 0 ]]; then
    echo "King Sejong install verification failed: $root" >&2
    exit 1
  fi

  echo "King Sejong install verified:"
  echo "  $root"
}

if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  verify_install "$TARGET_ROOT"
  exit 0
fi

if [[ "$TARGET_ROOT" == "$SOURCE_ROOT" ]]; then
  echo "King Sejong is already present in this repository."
  verify_install "$TARGET_ROOT"
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

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "would install: $dest"
    return
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

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run complete. No files were copied."
  exit 0
fi

verify_install "$TARGET_ROOT"

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
