#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/install-sejong.sh [--scope repo|user] [--force] [--dry-run] [target-repo]
  scripts/install-sejong.sh --verify [--scope repo|user] [target-repo]

Examples:
  scripts/install-sejong.sh /path/to/your-repo
  scripts/install-sejong.sh --force /path/to/your-repo
  scripts/install-sejong.sh --verify /path/to/your-repo
  scripts/install-sejong.sh --scope user
  scripts/install-sejong.sh --scope user --verify
  CODEX_HOME=/path/to/codex-home scripts/install-sejong.sh --scope user --force

Installs:
  repo scope:
    .agents/skills/sejong/
    .agents/skills/uigwe/
    .agents/skills/seungjeongwon/
    docs/sejong/
  user scope:
    ${CODEX_HOME:-~/.codex}/skills/sejong/
    ${CODEX_HOME:-~/.codex}/skills/uigwe/
    ${CODEX_HOME:-~/.codex}/skills/seungjeongwon/

Source-only:
  AGENTS.md is maintainer guidance for this source repository and is never installed.
EOF
}

FORCE=0
DRY_RUN=0
VERIFY_ONLY=0
SCOPE=repo
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
    --scope)
      if [[ $# -lt 2 ]]; then
        echo "--scope requires one of: repo, project, user" >&2
        exit 1
      fi
      case "$2" in
        repo|project|local)
          SCOPE=repo
          ;;
        user)
          SCOPE=user
          ;;
        *)
          echo "unsupported scope: $2" >&2
          echo "expected one of: repo, project, user" >&2
          exit 1
          ;;
      esac
      shift 2
      ;;
    --repo|--project|--local)
      SCOPE=repo
      shift
      ;;
    --user)
      SCOPE=user
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
SOURCE_ONLY_PATHS=(
  "AGENTS.md"
)

verify_source_only_paths_not_installed() {
  local root=$1
  local path

  if [[ "$root" == "$SOURCE_ROOT" ]]; then
    return
  fi

  for path in "${SOURCE_ONLY_PATHS[@]}"; do
    if [[ -f "$SOURCE_ROOT/$path" && -f "$root/$path" ]] && cmp -s "$SOURCE_ROOT/$path" "$root/$path"; then
      echo "source-only file was copied into install target: $path" >&2
      echo "King Sejong install should copy only managed skill and docs paths." >&2
      exit 1
    fi
  done
}

verify_tree_matches() {
  local src=$1
  local dest=$2
  local label=$3

  if ! diff -qr -x '.DS_Store' -x '__pycache__' "$src" "$dest" >/dev/null; then
    echo "managed install differs from source: $label" >&2
    diff -qr -x '.DS_Store' -x '__pycache__' "$src" "$dest" >&2 || true
    return 1
  fi
}

verify_rewritten_skill_matches() {
  local src=$1
  local dest=$2
  local replacement=$3
  local label=$4
  local tmp_file

  tmp_file=$(mktemp)
  sed "s#\\.\\./\\.\\./\\.\\./docs/sejong/#$replacement#g" "$src" > "$tmp_file"
  if ! cmp -s "$tmp_file" "$dest"; then
    echo "managed install differs from rewritten source: $label" >&2
    rm -f "$tmp_file"
    return 1
  fi
  rm -f "$tmp_file"
}

verify_repo_install() {
  local root=$1
  local missing=0
  local drift=0
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
    "docs/sejong/TEAM_EXECUTOR.md"
    "docs/sejong/scripts/team_executor.py"
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

  verify_source_only_paths_not_installed "$root"

  verify_tree_matches "$SOURCE_ROOT/.agents/skills/sejong" "$root/.agents/skills/sejong" ".agents/skills/sejong/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/uigwe" "$root/.agents/skills/uigwe" ".agents/skills/uigwe/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/seungjeongwon" "$root/.agents/skills/seungjeongwon" ".agents/skills/seungjeongwon/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/docs/sejong" "$root/docs/sejong" "docs/sejong/" || drift=1

  if [[ "$drift" -ne 0 ]]; then
    echo "King Sejong install verification failed: managed content is stale or modified in $root" >&2
    exit 1
  fi

  echo "King Sejong repo install verified:"
  echo "  $root"
}

verify_user_install() {
  local root=$1
  local missing=0
  local drift=0
  local required_paths=(
    "skills/sejong/SKILL.md"
    "skills/sejong/docs/README.md"
    "skills/sejong/docs/ROUTER.md"
    "skills/sejong/docs/PROMPT_OVERLAYS.md"
    "skills/sejong/docs/PROTOCOL.md"
    "skills/sejong/docs/SEUNGJEONGWON_EXECUTOR.md"
    "skills/sejong/docs/BUNDLE_VALIDATOR.md"
    "skills/sejong/docs/TEAM_EXECUTOR.md"
    "skills/sejong/docs/scripts/team_executor.py"
    "skills/sejong/docs/scripts/validate_json_contracts.py"
    "skills/uigwe/SKILL.md"
    "skills/seungjeongwon/SKILL.md"
  )

  for path in "${required_paths[@]}"; do
    if [[ ! -e "$root/$path" ]]; then
      echo "missing: $path" >&2
      missing=1
    fi
  done

  if [[ "$missing" -ne 0 ]]; then
    echo "King Sejong user install verification failed: $root" >&2
    exit 1
  fi

  verify_source_only_paths_not_installed "$root/skills"

  verify_rewritten_skill_matches "$SOURCE_ROOT/.agents/skills/sejong/SKILL.md" "$root/skills/sejong/SKILL.md" "docs/" "skills/sejong/SKILL.md" || drift=1
  verify_rewritten_skill_matches "$SOURCE_ROOT/.agents/skills/uigwe/SKILL.md" "$root/skills/uigwe/SKILL.md" "../sejong/docs/" "skills/uigwe/SKILL.md" || drift=1
  verify_rewritten_skill_matches "$SOURCE_ROOT/.agents/skills/seungjeongwon/SKILL.md" "$root/skills/seungjeongwon/SKILL.md" "../sejong/docs/" "skills/seungjeongwon/SKILL.md" || drift=1
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/sejong/agents" "$root/skills/sejong/agents" "skills/sejong/agents/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/uigwe/agents" "$root/skills/uigwe/agents" "skills/uigwe/agents/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/seungjeongwon/agents" "$root/skills/seungjeongwon/agents" "skills/seungjeongwon/agents/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/docs/sejong" "$root/skills/sejong/docs" "skills/sejong/docs/" || drift=1

  if [[ "$drift" -ne 0 ]]; then
    echo "King Sejong user install verification failed: managed content is stale or modified in $root" >&2
    exit 1
  fi

  echo "King Sejong user install verified:"
  echo "  $root"
}

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

rewrite_skill_doc_paths() {
  local file=$1
  local replacement=$2
  local tmp_file

  if [[ ! -f "$file" ]]; then
    echo "missing skill file for path rewrite: $file" >&2
    exit 1
  fi

  tmp_file=$(mktemp "${file}.tmp.XXXXXX")
  sed "s#\\.\\./\\.\\./\\.\\./docs/sejong/#$replacement#g" "$file" > "$tmp_file"
  chmod 0644 "$tmp_file"
  mv "$tmp_file" "$file"
}

install_repo_scope() {
  local target_repo=$1
  local target_root

  if [[ ! -d "$target_repo" ]]; then
    echo "target repo does not exist: $target_repo" >&2
    exit 1
  fi

  target_root=$(cd "$target_repo" && pwd)

  if [[ ! -d "$target_root/.git" && ! -f "$target_root/.git" ]]; then
    echo "target is not a git repository: $target_root" >&2
    exit 1
  fi

  if [[ "$VERIFY_ONLY" -eq 1 ]]; then
    verify_repo_install "$target_root"
    exit 0
  fi

  if [[ "$target_root" == "$SOURCE_ROOT" ]]; then
    echo "King Sejong is already present in this repository."
    verify_repo_install "$target_root"
    exit 0
  fi

  copy_dir "$SOURCE_ROOT/.agents/skills/sejong" "$target_root/.agents/skills/sejong"
  copy_dir "$SOURCE_ROOT/.agents/skills/uigwe" "$target_root/.agents/skills/uigwe"
  copy_dir "$SOURCE_ROOT/.agents/skills/seungjeongwon" "$target_root/.agents/skills/seungjeongwon"
  copy_dir "$SOURCE_ROOT/docs/sejong" "$target_root/docs/sejong"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "Dry run complete. No files were copied."
    exit 0
  fi

  verify_repo_install "$target_root"

  cat <<EOF
Installed King Sejong into repo:
  $target_root

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
}

install_user_scope() {
  local codex_home=${CODEX_HOME:-$HOME/.codex}
  local skill_root="$codex_home/skills"

  if [[ "$VERIFY_ONLY" -eq 1 ]]; then
    verify_user_install "$codex_home"
    exit 0
  fi

  copy_dir "$SOURCE_ROOT/.agents/skills/sejong" "$skill_root/sejong"
  copy_dir "$SOURCE_ROOT/.agents/skills/uigwe" "$skill_root/uigwe"
  copy_dir "$SOURCE_ROOT/.agents/skills/seungjeongwon" "$skill_root/seungjeongwon"
  copy_dir "$SOURCE_ROOT/docs/sejong" "$skill_root/sejong/docs"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "would rewrite repo-local doc paths for user-scope skill layout"
    echo "Dry run complete. No files were copied."
    exit 0
  fi

  rewrite_skill_doc_paths "$skill_root/sejong/SKILL.md" "docs/"
  rewrite_skill_doc_paths "$skill_root/uigwe/SKILL.md" "../sejong/docs/"
  rewrite_skill_doc_paths "$skill_root/seungjeongwon/SKILL.md" "../sejong/docs/"

  verify_user_install "$codex_home"

  cat <<EOF
Installed King Sejong into Codex user scope:
  $codex_home

Managed paths:
  skills/sejong/
  skills/uigwe/
  skills/seungjeongwon/

Invoke from any Codex workspace with:
  \$sejong <broad request>
  \$uigwe <formal planning request>
  \$seungjeongwon <execution request>
EOF
}

case "$SCOPE" in
  repo)
    install_repo_scope "$TARGET_REPO"
    ;;
  user)
    install_user_scope
    ;;
  *)
    echo "unsupported scope: $SCOPE" >&2
    exit 1
    ;;
esac
