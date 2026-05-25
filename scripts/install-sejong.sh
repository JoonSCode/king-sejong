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
    .agents/skills/jangyeongsil/
    .agents/skills/jiphyeonjeon/
    .agents/skills/uigwe/
    .agents/skills/seungjeongwon/
    docs/sejong/
  user scope:
    ${CODEX_HOME:-~/.codex}/skills/sejong/
    ${CODEX_HOME:-~/.codex}/skills/jangyeongsil/
    ${CODEX_HOME:-~/.codex}/skills/jiphyeonjeon/
    ${CODEX_HOME:-~/.codex}/skills/uigwe/
    ${CODEX_HOME:-~/.codex}/skills/seungjeongwon/
    ${CODEX_HOME:-~/.codex}/config.toml managed King Sejong hooks block
    ${CODEX_HOME:-~/.codex}/sejong/state/active-context.json

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

canonical_path() {
  python3 - "$1" <<'PY'
import sys
from pathlib import Path

print(Path(sys.argv[1]).expanduser().resolve())
PY
}

same_path() {
  python3 - "$1" "$2" <<'PY'
import sys
from pathlib import Path


def path_key(value: str) -> str:
    path = Path(value).expanduser().resolve()
    text = str(path)
    if sys.platform == "darwin":
        return text.casefold()
    return text


left = sys.argv[1]
right = sys.argv[2]
try:
    if Path(left).expanduser().samefile(Path(right).expanduser()):
        raise SystemExit(0)
except OSError:
    pass

raise SystemExit(0 if path_key(left) == path_key(right) else 1)
PY
}

verify_hook_script_reference() {
  python3 - "$1" "$2" <<'PY'
import re
import sys
from pathlib import Path


def path_key(value: str) -> str:
    path = Path(value).expanduser().resolve()
    text = str(path)
    if sys.platform == "darwin":
        return text.casefold()
    return text


config_path = Path(sys.argv[1])
expected = path_key(sys.argv[2])
text = config_path.read_text(encoding="utf-8")
for candidate in re.findall(r'python3\s+"([^"]*king_sejong_hooks\.py)"', text):
    if path_key(candidate) == expected:
        raise SystemExit(0)
raise SystemExit(1)
PY
}

SCRIPT_DIR=$(canonical_path "$(dirname "${BASH_SOURCE[0]}")")
SOURCE_ROOT=$(canonical_path "$SCRIPT_DIR/..")
SOURCE_ONLY_PATHS=(
  "AGENTS.md"
)

verify_source_only_paths_not_installed() {
  local root=$1
  local path

  if same_path "$root" "$SOURCE_ROOT"; then
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

ensure_hooks_feature_enabled() {
  local config_file=$1
  local tmp_file

  mkdir -p "$(dirname "$config_file")"
  touch "$config_file"
  tmp_file=$(mktemp)

  awk '
    BEGIN {
      in_features = 0
      seen_features = 0
      wrote_hooks = 0
    }
    /^\[features\]$/ {
      if (in_features && !wrote_hooks) {
        print "hooks = true"
        wrote_hooks = 1
      }
      in_features = 1
      seen_features = 1
      print
      next
    }
    /^\[/ {
      if (in_features && !wrote_hooks) {
        print "hooks = true"
        wrote_hooks = 1
      }
      in_features = 0
      print
      next
    }
    in_features && /^[[:space:]]*hooks[[:space:]]*=/ {
      print "hooks = true"
      wrote_hooks = 1
      next
    }
    { print }
    END {
      if (!seen_features) {
        print ""
        print "[features]"
        print "hooks = true"
      } else if (in_features && !wrote_hooks) {
        print "hooks = true"
      }
    }
  ' "$config_file" > "$tmp_file"

  mv "$tmp_file" "$config_file"
}

append_managed_hooks_block() {
  local config_file=$1
  local hook_script=$2
  local tmp_file
  local escaped_script

  escaped_script=${hook_script//\'/\'\\\'\'}
  tmp_file=$(mktemp)

  awk '
    /^# BEGIN King Sejong hooks$/ { skip = 1; next }
    /^# END King Sejong hooks$/ { skip = 0; next }
    !skip { print }
  ' "$config_file" > "$tmp_file"

  cat >> "$tmp_file" <<EOF

# BEGIN King Sejong hooks
[[hooks.SessionStart]]
matcher = "startup|resume|compact"

[[hooks.SessionStart.hooks]]
type = "command"
command = 'python3 "$escaped_script" SessionStart'
timeout = 30
statusMessage = "Loading King Sejong context"

[[hooks.UserPromptSubmit]]

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = 'python3 "$escaped_script" UserPromptSubmit'
timeout = 30
statusMessage = "Checking King Sejong context"

[[hooks.PreToolUse]]
matcher = "Bash|apply_patch|Edit|Write"

[[hooks.PreToolUse.hooks]]
type = "command"
command = 'python3 "$escaped_script" PreToolUse'
timeout = 30
statusMessage = "Checking King Sejong protected paths"

[[hooks.PermissionRequest]]
matcher = "Bash|apply_patch|Edit|Write"

[[hooks.PermissionRequest.hooks]]
type = "command"
command = 'python3 "$escaped_script" PermissionRequest'
timeout = 30
statusMessage = "Checking King Sejong permissions"

[[hooks.PostToolUse]]
matcher = "Bash|apply_patch|Edit|Write"

[[hooks.PostToolUse.hooks]]
type = "command"
command = 'python3 "$escaped_script" PostToolUse'
timeout = 30
statusMessage = "Recording King Sejong tool evidence"

[[hooks.SubagentStart]]
matcher = ".*"

[[hooks.SubagentStart.hooks]]
type = "command"
command = 'python3 "$escaped_script" SubagentStart'
timeout = 30
statusMessage = "Passing King Sejong context to subagent"

[[hooks.SubagentStop]]
matcher = ".*"

[[hooks.SubagentStop.hooks]]
type = "command"
command = 'python3 "$escaped_script" SubagentStop'
timeout = 30
statusMessage = "Checking King Sejong subagent handoff"

[[hooks.Stop]]

[[hooks.Stop.hooks]]
type = "command"
command = 'python3 "$escaped_script" Stop'
timeout = 30
statusMessage = "Checking King Sejong completion gates"

[[hooks.PreCompact]]
matcher = "manual|auto"

[[hooks.PreCompact.hooks]]
type = "command"
command = 'python3 "$escaped_script" PreCompact'
timeout = 30
statusMessage = "Checking King Sejong checkpoint before compaction"

[[hooks.PostCompact]]
matcher = "manual|auto"

[[hooks.PostCompact.hooks]]
type = "command"
command = 'python3 "$escaped_script" PostCompact'
timeout = 30
statusMessage = "Restoring King Sejong context after compaction"
# END King Sejong hooks
EOF

  mv "$tmp_file" "$config_file"
}

write_active_context_if_missing() {
  local codex_home=$1
  local context_file="$codex_home/sejong/state/active-context.json"
  local repo_root
  local timestamp

  repo_root=$(canonical_path "$SOURCE_ROOT")
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  mkdir -p "$(dirname "$context_file")"

  if [[ -f "$context_file" ]]; then
    python3 - "$context_file" "$timestamp" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
timestamp = sys.argv[2]
data = json.loads(path.read_text(encoding="utf-8"))
protected = data.setdefault("protected_paths", [])
for item in [
    ".agents/skills/sejong/",
    ".agents/skills/jangyeongsil/",
    ".agents/skills/jiphyeonjeon/",
    ".agents/skills/uigwe/",
    ".agents/skills/seungjeongwon/",
    "docs/sejong/",
    "scripts/install-sejong.sh",
]:
    if item not in protected:
        protected.append(item)
required = data.setdefault("required_route_sequence", [])
for item in ["jiphyeonjeon", "uigwe", "seungjeongwon"]:
    if item not in required:
        required.append(item)
data["last_updated_at"] = timestamp
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
    return
  fi

  cat > "$context_file" <<EOF
{
  "format": "king-sejong.context/v0.1-draft",
  "active_context_id": "ctx-king-sejong-user-install",
  "repo_id": "king-sejong",
  "repo_root": "$repo_root",
  "run_id": "user-install",
  "session_id": "user-scope-install",
  "route_id": "route-user-scope-install",
  "current_surface": "sejong",
  "route_sequence": ["sejong"],
  "required_route_sequence": ["jiphyeonjeon", "uigwe", "seungjeongwon"],
  "last_user_intent": "King Sejong user-scope hooks are installed.",
  "pending_gates": [],
  "protected_paths": [
    ".agents/skills/sejong/",
    ".agents/skills/jangyeongsil/",
    ".agents/skills/jiphyeonjeon/",
    ".agents/skills/uigwe/",
    ".agents/skills/seungjeongwon/",
    "docs/sejong/",
    "scripts/install-sejong.sh"
  ],
  "allowed_direct_change_types": [
    "typo",
    "broken_link",
    "formatting_only",
    "deterministic_scorecard_regeneration"
  ],
  "evidence_refs": [],
  "artifact_refs": [],
  "team_run_refs": [],
  "subagent_refs": [],
  "exit_conditions": [
    "user_explicitly_exits_sejong",
    "user_switches_to_non_sejong_workflow",
    "host_conversation_ends"
  ],
  "last_updated_at": "$timestamp"
}
EOF
}

configure_user_hooks() {
  local codex_home=$1
  local config_file="$codex_home/config.toml"
  local hook_script="$codex_home/skills/sejong/docs/scripts/king_sejong_hooks.py"

  ensure_hooks_feature_enabled "$config_file"
  append_managed_hooks_block "$config_file" "$hook_script"
  write_active_context_if_missing "$codex_home"
}

verify_user_hooks_config() {
  local codex_home=$1
  local config_file="$codex_home/config.toml"
  local hook_script="$codex_home/skills/sejong/docs/scripts/king_sejong_hooks.py"
  local context_file="$codex_home/sejong/state/active-context.json"

  if [[ ! -f "$config_file" ]]; then
    echo "missing Codex config: $config_file" >&2
    return 1
  fi
  if ! grep -q "hooks = true" "$config_file"; then
    echo "Codex hooks feature is not enabled in config.toml" >&2
    return 1
  fi
  if ! grep -q "# BEGIN King Sejong hooks" "$config_file" || ! grep -q "# END King Sejong hooks" "$config_file"; then
    echo "King Sejong managed hooks block is missing from config.toml" >&2
    return 1
  fi
  if ! verify_hook_script_reference "$config_file" "$hook_script"; then
    echo "King Sejong hook block does not reference installed hook script" >&2
    return 1
  fi
  if [[ ! -f "$context_file" ]]; then
    echo "missing King Sejong active context checkpoint: $context_file" >&2
    return 1
  fi
  for path in \
    ".agents/skills/jangyeongsil/" \
    ".agents/skills/jiphyeonjeon/" \
    "scripts/install-sejong.sh"; do
    if ! grep -q "$path" "$context_file"; then
      echo "King Sejong active context checkpoint is missing protected path: $path" >&2
      return 1
    fi
  done
}

verify_repo_install() {
  local root=$1
  local missing=0
  local drift=0
  local required_paths=(
    ".agents/skills/sejong/SKILL.md"
    ".agents/skills/jangyeongsil/SKILL.md"
    ".agents/skills/jiphyeonjeon/SKILL.md"
    ".agents/skills/uigwe/SKILL.md"
    ".agents/skills/seungjeongwon/SKILL.md"
    "docs/sejong/README.md"
    "docs/sejong/ROUTER.md"
    "docs/sejong/REPO_CONTEXT.md"
    "docs/sejong/HOOKS.md"
    "docs/sejong/SECURITY.md"
    "docs/sejong/SILLOK_TRACE.md"
    "docs/sejong/king-sejong-context.schema.json"
    "docs/sejong/sillok-trace-event.schema.json"
    "docs/sejong/PROMPT_OVERLAYS.md"
    "docs/sejong/PROTOCOL.md"
    "docs/sejong/SEUNGJEONGWON_EXECUTOR.md"
    "docs/sejong/BUNDLE_VALIDATOR.md"
    "docs/sejong/TEAM_EXECUTOR.md"
    "docs/sejong/scripts/king_sejong_hooks.py"
    "docs/sejong/scripts/sejong_context.py"
    "docs/sejong/scripts/sillok_trace.py"
    "docs/sejong/scripts/test_king_sejong_hooks.py"
    "docs/sejong/scripts/test_king_sejong_e2e.py"
    "docs/sejong/scripts/test_sejong_context.py"
    "docs/sejong/scripts/test_sillok_trace.py"
    "docs/sejong/scripts/test_team_executor.py"
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
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/jangyeongsil" "$root/.agents/skills/jangyeongsil" ".agents/skills/jangyeongsil/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/jiphyeonjeon" "$root/.agents/skills/jiphyeonjeon" ".agents/skills/jiphyeonjeon/" || drift=1
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
    "skills/jangyeongsil/SKILL.md"
    "skills/jiphyeonjeon/SKILL.md"
    "skills/sejong/docs/README.md"
    "skills/sejong/docs/ROUTER.md"
    "skills/sejong/docs/REPO_CONTEXT.md"
    "skills/sejong/docs/HOOKS.md"
    "skills/sejong/docs/SECURITY.md"
    "skills/sejong/docs/SILLOK_TRACE.md"
    "skills/sejong/docs/king-sejong-context.schema.json"
    "skills/sejong/docs/sillok-trace-event.schema.json"
    "skills/sejong/docs/PROMPT_OVERLAYS.md"
    "skills/sejong/docs/PROTOCOL.md"
    "skills/sejong/docs/SEUNGJEONGWON_EXECUTOR.md"
    "skills/sejong/docs/BUNDLE_VALIDATOR.md"
    "skills/sejong/docs/TEAM_EXECUTOR.md"
    "skills/sejong/docs/scripts/king_sejong_hooks.py"
    "skills/sejong/docs/scripts/sejong_context.py"
    "skills/sejong/docs/scripts/sillok_trace.py"
    "skills/sejong/docs/scripts/test_king_sejong_hooks.py"
    "skills/sejong/docs/scripts/test_king_sejong_e2e.py"
    "skills/sejong/docs/scripts/test_sejong_context.py"
    "skills/sejong/docs/scripts/test_sillok_trace.py"
    "skills/sejong/docs/scripts/test_team_executor.py"
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
  verify_rewritten_skill_matches "$SOURCE_ROOT/.agents/skills/jangyeongsil/SKILL.md" "$root/skills/jangyeongsil/SKILL.md" "../sejong/docs/" "skills/jangyeongsil/SKILL.md" || drift=1
  verify_rewritten_skill_matches "$SOURCE_ROOT/.agents/skills/jiphyeonjeon/SKILL.md" "$root/skills/jiphyeonjeon/SKILL.md" "../sejong/docs/" "skills/jiphyeonjeon/SKILL.md" || drift=1
  verify_rewritten_skill_matches "$SOURCE_ROOT/.agents/skills/uigwe/SKILL.md" "$root/skills/uigwe/SKILL.md" "../sejong/docs/" "skills/uigwe/SKILL.md" || drift=1
  verify_rewritten_skill_matches "$SOURCE_ROOT/.agents/skills/seungjeongwon/SKILL.md" "$root/skills/seungjeongwon/SKILL.md" "../sejong/docs/" "skills/seungjeongwon/SKILL.md" || drift=1
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/sejong/agents" "$root/skills/sejong/agents" "skills/sejong/agents/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/jangyeongsil/agents" "$root/skills/jangyeongsil/agents" "skills/jangyeongsil/agents/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/jiphyeonjeon/agents" "$root/skills/jiphyeonjeon/agents" "skills/jiphyeonjeon/agents/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/uigwe/agents" "$root/skills/uigwe/agents" "skills/uigwe/agents/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/seungjeongwon/agents" "$root/skills/seungjeongwon/agents" "skills/seungjeongwon/agents/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/docs/sejong" "$root/skills/sejong/docs" "skills/sejong/docs/" || drift=1
  verify_user_hooks_config "$root" || drift=1

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

  target_root=$(canonical_path "$target_repo")

  if [[ ! -d "$target_root/.git" && ! -f "$target_root/.git" ]]; then
    echo "target is not a git repository: $target_root" >&2
    exit 1
  fi

  if [[ "$VERIFY_ONLY" -eq 1 ]]; then
    verify_repo_install "$target_root"
    exit 0
  fi

  if same_path "$target_root" "$SOURCE_ROOT"; then
    echo "King Sejong is already present in this repository."
    verify_repo_install "$target_root"
    exit 0
  fi

  copy_dir "$SOURCE_ROOT/.agents/skills/sejong" "$target_root/.agents/skills/sejong"
  copy_dir "$SOURCE_ROOT/.agents/skills/jangyeongsil" "$target_root/.agents/skills/jangyeongsil"
  copy_dir "$SOURCE_ROOT/.agents/skills/jiphyeonjeon" "$target_root/.agents/skills/jiphyeonjeon"
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
  .agents/skills/jangyeongsil/
  .agents/skills/jiphyeonjeon/
  .agents/skills/uigwe/
  .agents/skills/seungjeongwon/
  docs/sejong/

Invoke with:
  \$sejong <broad request>
  \$jangyeongsil <research request>
  \$jiphyeonjeon <decision request>
  \$uigwe <formal planning request>
  \$seungjeongwon <execution request>
EOF
}

install_user_scope() {
  local codex_home=${CODEX_HOME:-$HOME/.codex}
  local skill_root="$codex_home/skills"

  codex_home=$(canonical_path "$codex_home")
  skill_root="$codex_home/skills"

  if [[ "$VERIFY_ONLY" -eq 1 ]]; then
    verify_user_install "$codex_home"
    exit 0
  fi

  copy_dir "$SOURCE_ROOT/.agents/skills/sejong" "$skill_root/sejong"
  copy_dir "$SOURCE_ROOT/.agents/skills/jangyeongsil" "$skill_root/jangyeongsil"
  copy_dir "$SOURCE_ROOT/.agents/skills/jiphyeonjeon" "$skill_root/jiphyeonjeon"
  copy_dir "$SOURCE_ROOT/.agents/skills/uigwe" "$skill_root/uigwe"
  copy_dir "$SOURCE_ROOT/.agents/skills/seungjeongwon" "$skill_root/seungjeongwon"
  copy_dir "$SOURCE_ROOT/docs/sejong" "$skill_root/sejong/docs"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "would rewrite repo-local doc paths for user-scope skill layout"
    echo "Dry run complete. No files were copied."
    exit 0
  fi

  rewrite_skill_doc_paths "$skill_root/sejong/SKILL.md" "docs/"
  rewrite_skill_doc_paths "$skill_root/jangyeongsil/SKILL.md" "../sejong/docs/"
  rewrite_skill_doc_paths "$skill_root/jiphyeonjeon/SKILL.md" "../sejong/docs/"
  rewrite_skill_doc_paths "$skill_root/uigwe/SKILL.md" "../sejong/docs/"
  rewrite_skill_doc_paths "$skill_root/seungjeongwon/SKILL.md" "../sejong/docs/"
  configure_user_hooks "$codex_home"

  verify_user_install "$codex_home"

  cat <<EOF
Installed King Sejong into Codex user scope:
  $codex_home

Managed paths:
  skills/sejong/
  skills/jangyeongsil/
  skills/jiphyeonjeon/
  skills/uigwe/
  skills/seungjeongwon/

Managed hooks:
  $codex_home/config.toml
  $codex_home/sejong/state/active-context.json

Invoke from any Codex workspace with:
  \$sejong <broad request>
  \$jangyeongsil <research request>
  \$jiphyeonjeon <decision request>
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
