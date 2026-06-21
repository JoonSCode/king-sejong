#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/install-sejong.sh [--scope repo|user] [--force] [--dry-run] [--legacy-direct-hooks] [--codex-guidance default|none|print|user] [target-repo]
  scripts/install-sejong.sh --verify [--scope repo|user] [--codex-guidance default|none|user] [target-repo]
  scripts/install-sejong.sh --check-updates
  scripts/install-sejong.sh --auto-update [--scope repo|user] [target-repo]
  scripts/install-sejong.sh --print-codex-guidance

Examples:
  scripts/install-sejong.sh /path/to/your-repo
  scripts/install-sejong.sh --force /path/to/your-repo
  scripts/install-sejong.sh --verify /path/to/your-repo
  scripts/install-sejong.sh --check-updates
  scripts/install-sejong.sh --auto-update --scope user
  scripts/install-sejong.sh --scope user
  scripts/install-sejong.sh --scope user --codex-guidance none
  scripts/install-sejong.sh --scope user --legacy-direct-hooks --force
  scripts/install-sejong.sh --scope user --verify
  scripts/install-sejong.sh --print-codex-guidance
  CODEX_HOME=/path/to/codex-home scripts/install-sejong.sh --scope user --force

Installs:
  repo scope:
    .agents/skills/sejong/
    .agents/skills/jangyeongsil/
    .agents/skills/jiphyeonjeon/
    .agents/skills/uigwe/
    .agents/skills/seungjeongwon/
    .agents/skills/why-gate/
    docs/sejong/
  user scope:
    ${CODEX_HOME:-~/.codex}/skills/sejong/
    ${CODEX_HOME:-~/.codex}/skills/jangyeongsil/
    ${CODEX_HOME:-~/.codex}/skills/jiphyeonjeon/
    ${CODEX_HOME:-~/.codex}/skills/uigwe/
    ${CODEX_HOME:-~/.codex}/skills/seungjeongwon/
    ${CODEX_HOME:-~/.codex}/skills/why-gate/
    ${CODEX_HOME:-~/.codex}/plugins/cache/king-sejong-local/king-sejong/0.1.0/
    ${CODEX_HOME:-~/.codex}/config.toml managed King Sejong plugin block
    ${CODEX_HOME:-~/.codex}/sejong/state/active-context.json

Source-only:
  AGENTS.md is maintainer guidance for this source repository and is never installed.

Codex guidance:
  User-scope install writes a compact generic AGENTS.md block by default.
  --codex-guidance none skips writing ${CODEX_HOME:-~/.codex}/AGENTS.md.
  --codex-guidance print prints a compact generic AGENTS.md block.
  --codex-guidance user writes that block to ${CODEX_HOME:-~/.codex}/AGENTS.md.
  The block is generic Codex guidance and does not depend on external runtime or repo-local state.
EOF
}

FORCE=0
DRY_RUN=0
VERIFY_ONLY=0
UPDATE_CHECK=0
AUTO_UPDATE=0
LEGACY_DIRECT_HOOKS=0
CODEX_GUIDANCE=default
CODEX_GUIDANCE_EXPLICIT=0
PRINT_CODEX_GUIDANCE=0
SCOPE=repo
TARGET_REPO="."
PLUGIN_MARKETPLACE="king-sejong-local"
PLUGIN_NAME="king-sejong"
PLUGIN_VERSION="0.1.0"

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
    --legacy-direct-hooks)
      LEGACY_DIRECT_HOOKS=1
      shift
      ;;
    --verify|--check)
      VERIFY_ONLY=1
      shift
      ;;
    --check-update|--check-updates)
      UPDATE_CHECK=1
      shift
      ;;
    --update|--auto-update)
      AUTO_UPDATE=1
      shift
      ;;
    --codex-guidance)
      if [[ $# -lt 2 ]]; then
        echo "--codex-guidance requires one of: default, none, print, user" >&2
        exit 1
      fi
      case "$2" in
        default|none|print|user)
          CODEX_GUIDANCE=$2
          CODEX_GUIDANCE_EXPLICIT=1
          ;;
        *)
          echo "unsupported codex guidance mode: $2" >&2
          echo "expected one of: default, none, print, user" >&2
          exit 1
          ;;
      esac
      shift 2
      ;;
    --print-codex-guidance)
      CODEX_GUIDANCE=print
      CODEX_GUIDANCE_EXPLICIT=1
      PRINT_CODEX_GUIDANCE=1
      shift
      ;;
    --install-codex-guidance)
      CODEX_GUIDANCE=user
      CODEX_GUIDANCE_EXPLICIT=1
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

if [[ "$AUTO_UPDATE" -eq 1 ]]; then
  if [[ "$VERIFY_ONLY" -eq 1 ]]; then
    echo "--auto-update cannot be combined with --verify" >&2
    exit 1
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "--auto-update cannot be combined with --dry-run; use --check-updates to inspect remote state" >&2
    exit 1
  fi
  FORCE=1
fi

if [[ "$UPDATE_CHECK" -eq 1 && "$VERIFY_ONLY" -eq 1 ]]; then
  echo "--check-updates cannot be combined with --verify" >&2
  exit 1
fi

if [[ "$VERIFY_ONLY" -eq 1 && "$CODEX_GUIDANCE" == "print" ]]; then
  echo "--codex-guidance print cannot be combined with --verify" >&2
  exit 1
fi

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

print_codex_guidance_block() {
  cat <<'EOF'
<!-- BEGIN King Sejong Codex Guidance -->
# King Sejong Codex Guidance

King Sejong is a Codex-native skill and protocol distribution. It does not replace Codex, shell tools, user permissions, or host-native subagents.

Always treat King Sejong as available for broad, uncertain, strategic, or goal-bearing work, even when the user does not type `$sejong`.

For work that needs research, analysis, debate, planning, execution, or verification:
- Route broad or goal-bearing work through Sejong lead synthesis.
- Use JangYeongsil for bounded evidence gathering.
- Use Jiphyeonjeon for bounded multi-perspective debate; workers may persuade each other, but Sejong lead owns synthesis.
- Use Uigwe to clarify ambiguous ideas and designs into success criteria, verification bars, and handoff leaves.
- Use Seungjeongwon to decompose, execute, retry, and verify until the Uigwe pass criteria are met or a real blocker is recorded.
- Iterate through research, analysis, and discussion when evidence is thin or options are unsettled; do not collapse those states into one answer.
- Store Sejong runtime artifacts under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}` unless the user explicitly asks to promote a tracked artifact.
- Do not use non-Sejong runtime paths as Sejong state.

Hooks and schemas are guardrails, not a sandbox. Completion still requires fresh verification evidence.
<!-- END King Sejong Codex Guidance -->
EOF
}

write_codex_guidance_block() {
  local codex_home=$1
  local agents_file="$codex_home/AGENTS.md"
  local tmp_file

  mkdir -p "$codex_home"
  touch "$agents_file"
  tmp_file=$(mktemp)
  awk '
    /^<!-- BEGIN King Sejong Codex Guidance -->$/ { skip = 1; next }
    /^<!-- END King Sejong Codex Guidance -->$/ { skip = 0; next }
    !skip { print }
  ' "$agents_file" > "$tmp_file"
  {
    sed '/^[[:space:]]*$/N;/^\n$/D' "$tmp_file"
    echo
    print_codex_guidance_block
  } > "$agents_file"
  rm -f "$tmp_file"
}

require_source_git_repo() {
  if ! git -C "$SOURCE_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "King Sejong update check requires a git checkout: $SOURCE_ROOT" >&2
    exit 1
  fi
}

source_tree_dirty() {
  [[ -n "$(git -C "$SOURCE_ROOT" status --porcelain)" ]]
}

load_update_state() {
  require_source_git_repo

  if ! UPDATE_UPSTREAM=$(git -C "$SOURCE_ROOT" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null); then
    echo "King Sejong source branch has no upstream; cannot check for updates." >&2
    exit 1
  fi

  if ! git -C "$SOURCE_ROOT" fetch --quiet; then
    echo "failed to fetch King Sejong upstream: $UPDATE_UPSTREAM" >&2
    exit 1
  fi

  read -r UPDATE_AHEAD UPDATE_BEHIND < <(git -C "$SOURCE_ROOT" rev-list --left-right --count "HEAD...$UPDATE_UPSTREAM")
  UPDATE_HEAD=$(git -C "$SOURCE_ROOT" rev-parse --short HEAD)
  UPDATE_UPSTREAM_HEAD=$(git -C "$SOURCE_ROOT" rev-parse --short "$UPDATE_UPSTREAM")
}

report_update_state() {
  load_update_state

  echo "King Sejong source update check:"
  echo "  source: $SOURCE_ROOT"
  echo "  upstream: $UPDATE_UPSTREAM"
  echo "  local HEAD: $UPDATE_HEAD"
  echo "  upstream HEAD: $UPDATE_UPSTREAM_HEAD"

  if source_tree_dirty; then
    echo "  status: local changes present; auto-update will refuse until the source tree is clean"
  elif [[ "$UPDATE_AHEAD" -eq 0 && "$UPDATE_BEHIND" -eq 0 ]]; then
    echo "  status: up to date"
  elif [[ "$UPDATE_AHEAD" -eq 0 ]]; then
    echo "  status: update available; behind by $UPDATE_BEHIND commit(s)"
    echo "  next: scripts/install-sejong.sh --auto-update --scope user"
  elif [[ "$UPDATE_BEHIND" -eq 0 ]]; then
    echo "  status: local branch is ahead by $UPDATE_AHEAD commit(s); nothing to auto-update"
  else
    echo "  status: local branch diverged; resolve git history before auto-update"
  fi
}

auto_update_source() {
  require_source_git_repo

  if source_tree_dirty; then
    echo "King Sejong source has local changes; refusing auto-update:" >&2
    git -C "$SOURCE_ROOT" status --short >&2
    exit 1
  fi

  load_update_state

  if [[ "$UPDATE_AHEAD" -gt 0 && "$UPDATE_BEHIND" -gt 0 ]]; then
    echo "King Sejong source diverged from $UPDATE_UPSTREAM; refusing auto-update." >&2
    exit 1
  fi
  if [[ "$UPDATE_AHEAD" -gt 0 ]]; then
    echo "King Sejong source is ahead of $UPDATE_UPSTREAM; refusing auto-update." >&2
    exit 1
  fi

  if [[ "$UPDATE_BEHIND" -gt 0 ]]; then
    echo "Updating King Sejong source from $UPDATE_UPSTREAM..."
    git -C "$SOURCE_ROOT" pull --ff-only
  else
    echo "King Sejong source is already up to date with $UPDATE_UPSTREAM."
  fi

  echo "Refreshing managed install with --force semantics."
}

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

remove_managed_hooks_block() {
  local config_file=$1
  local tmp_file

  [[ -f "$config_file" ]] || return 0
  tmp_file=$(mktemp)

  awk '
    /^# BEGIN King Sejong hooks$/ { skip = 1; next }
    /^# END King Sejong hooks$/ { skip = 0; next }
    !skip { print }
  ' "$config_file" > "$tmp_file"

  mv "$tmp_file" "$config_file"
}

config_has_managed_hooks_block() {
  local config_file=$1

  [[ -f "$config_file" ]] || return 1
  grep -q "# BEGIN King Sejong hooks" "$config_file" && grep -q "# END King Sejong hooks" "$config_file"
}

config_has_king_sejong_plugin_enabled() {
  local config_file=$1

  [[ -f "$config_file" ]] || return 1
  awk -v header="[plugins.\"$PLUGIN_NAME@$PLUGIN_MARKETPLACE\"]" '
    $0 == header {
      in_plugin = 1
      next
    }
    in_plugin && /^\[/ {
      in_plugin = 0
    }
    in_plugin && /^[[:space:]]*enabled[[:space:]]*=[[:space:]]*true[[:space:]]*$/ {
      found = 1
      exit
    }
    END {
      exit found ? 0 : 1
    }
  ' "$config_file"
}

append_managed_plugin_block() {
  local config_file=$1
  local codex_home=$2
  local tmp_file
  local plugin_cache_root
  local timestamp

  plugin_cache_root="$codex_home/plugins/cache/$PLUGIN_MARKETPLACE"
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  tmp_file=$(mktemp)

  awk '
    /^# BEGIN King Sejong plugin$/ { skip = 1; next }
    /^# END King Sejong plugin$/ { skip = 0; next }
    !skip { print }
  ' "$config_file" > "$tmp_file"

  cat >> "$tmp_file" <<EOF

# BEGIN King Sejong plugin
[marketplaces.$PLUGIN_MARKETPLACE]
last_updated = "$timestamp"
source_type = "local"
source = "$plugin_cache_root"

[plugins."$PLUGIN_NAME@$PLUGIN_MARKETPLACE"]
enabled = true
# END King Sejong plugin
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
    ".agents/skills/why-gate/",
    "plugins/king-sejong/",
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
    ".agents/skills/why-gate/",
    "plugins/king-sejong/",
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
  if [[ "$LEGACY_DIRECT_HOOKS" -eq 1 ]]; then
    append_managed_hooks_block "$config_file" "$hook_script"
  else
    remove_managed_hooks_block "$config_file"
  fi
  write_active_context_if_missing "$codex_home"
}

configure_user_plugin() {
  local codex_home=$1
  local config_file="$codex_home/config.toml"

  write_user_plugin_marketplace_manifest "$codex_home"
  append_managed_plugin_block "$config_file" "$codex_home"
}

write_user_plugin_marketplace_manifest() {
  local codex_home=$1
  local marketplace_file="$codex_home/plugins/cache/$PLUGIN_MARKETPLACE/.agents/plugins/marketplace.json"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "would install: $marketplace_file"
    return
  fi

  mkdir -p "$(dirname "$marketplace_file")"
  cat > "$marketplace_file" <<EOF
{
  "name": "$PLUGIN_MARKETPLACE",
  "interface": {
    "displayName": "King Sejong Local Plugins"
  },
  "plugins": [
    {
      "name": "$PLUGIN_NAME",
      "source": {
        "source": "local",
        "path": "./$PLUGIN_NAME/$PLUGIN_VERSION"
      }
    }
  ]
}
EOF
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
  if config_has_managed_hooks_block "$config_file"; then
    if config_has_king_sejong_plugin_enabled "$config_file"; then
      echo "duplicate King Sejong hook registration: remove the legacy direct hooks block or disable the King Sejong plugin hook" >&2
      return 1
    fi
    if ! verify_hook_script_reference "$config_file" "$hook_script"; then
      echo "King Sejong hook block does not reference installed hook script" >&2
      return 1
    fi
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

verify_user_plugin_adapter() {
  local codex_home=$1
  local config_file="$codex_home/config.toml"
  local plugin_root="$codex_home/plugins/cache/$PLUGIN_MARKETPLACE/$PLUGIN_NAME/$PLUGIN_VERSION"
  local marketplace_file="$codex_home/plugins/cache/$PLUGIN_MARKETPLACE/.agents/plugins/marketplace.json"

  if [[ ! -f "$marketplace_file" ]]; then
    echo "missing King Sejong cached marketplace manifest: $marketplace_file" >&2
    return 1
  fi
  if [[ ! -f "$plugin_root/.codex-plugin/plugin.json" ]]; then
    echo "missing King Sejong plugin manifest: $plugin_root/.codex-plugin/plugin.json" >&2
    return 1
  fi
  if [[ ! -f "$plugin_root/hooks/hooks.json" ]]; then
    echo "missing King Sejong plugin hooks: $plugin_root/hooks/hooks.json" >&2
    return 1
  fi
  if [[ ! -f "$plugin_root/hooks/king-sejong-hook.py" ]]; then
    echo "missing King Sejong plugin hook runner: $plugin_root/hooks/king-sejong-hook.py" >&2
    return 1
  fi
  if ! grep -q "\\[marketplaces\\.$PLUGIN_MARKETPLACE\\]" "$config_file"; then
    echo "King Sejong plugin marketplace block is missing from config.toml" >&2
    return 1
  fi
  if ! grep -q "\\[plugins\\.\"$PLUGIN_NAME@$PLUGIN_MARKETPLACE\"\\]" "$config_file"; then
    echo "King Sejong plugin enable block is missing from config.toml" >&2
    return 1
  fi
}

verify_user_codex_guidance() {
  local codex_home=$1
  local agents_file="$codex_home/AGENTS.md"

  if [[ "$CODEX_GUIDANCE" == "none" ]]; then
    return 0
  fi
  if [[ ! -f "$agents_file" ]]; then
    echo "missing Codex AGENTS.md guidance file: $agents_file" >&2
    return 1
  fi
  if ! grep -q "BEGIN King Sejong Codex Guidance" "$agents_file" || ! grep -q "END King Sejong Codex Guidance" "$agents_file"; then
    echo "King Sejong Codex guidance block is missing from AGENTS.md" >&2
    return 1
  fi
  if ! grep -q 'Do not use non-Sejong runtime paths as Sejong state.' "$agents_file"; then
    echo "King Sejong Codex guidance block is missing external-runtime-independent state rule" >&2
    return 1
  fi
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
    ".agents/skills/why-gate/SKILL.md"
    "docs/sejong/README.md"
    "docs/sejong/RUNTIME_CONTRACT.md"
    "docs/sejong/ROLE_SEPARATION.md"
    "docs/sejong/OUTCOME_EVALUATION.md"
    "docs/sejong/ROUTER.md"
    "docs/sejong/REPO_CONTEXT.md"
    "docs/sejong/HOOKS.md"
    "docs/sejong/SECURITY.md"
    "docs/sejong/SILLOK_TRACE.md"
    "docs/sejong/king-sejong-context.schema.json"
    "docs/sejong/seungjeongwon-run.schema.json"
    "docs/sejong/outcome-quality.schema.json"
    "docs/sejong/product-evidence.schema.json"
    "docs/sejong/sillok-trace-event.schema.json"
    "docs/sejong/PROMPT_OVERLAYS.md"
    "docs/sejong/PROTOCOL.md"
    "docs/sejong/SEUNGJEONGWON_EXECUTOR.md"
    "docs/sejong/BUNDLE_VALIDATOR.md"
    "docs/sejong/TEAM_EXECUTOR.md"
    "docs/sejong/scripts/king_sejong_hooks.py"
    "docs/sejong/scripts/sejong_integrated_quality_gate.py"
    "docs/sejong/scripts/seungjeongwon_run.py"
    "docs/sejong/scripts/outcome_quality_evaluator.py"
    "docs/sejong/scripts/product_evidence_gate.py"
    "docs/sejong/scripts/sejong_context.py"
    "docs/sejong/scripts/sillok_trace.py"
    "docs/sejong/scripts/test_king_sejong_hooks.py"
    "docs/sejong/scripts/test_sejong_integrated_quality_gate.py"
    "docs/sejong/scripts/test_seungjeongwon_run.py"
    "docs/sejong/scripts/test_outcome_quality_evaluator.py"
    "docs/sejong/scripts/test_product_evidence_gate.py"
    "docs/sejong/scripts/test_install_sejong.py"
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
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/why-gate" "$root/.agents/skills/why-gate" ".agents/skills/why-gate/" || drift=1
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
    "skills/sejong/docs/RUNTIME_CONTRACT.md"
    "skills/sejong/docs/ROLE_SEPARATION.md"
    "skills/sejong/docs/OUTCOME_EVALUATION.md"
    "skills/sejong/docs/ROUTER.md"
    "skills/sejong/docs/REPO_CONTEXT.md"
    "skills/sejong/docs/HOOKS.md"
    "skills/sejong/docs/SECURITY.md"
    "skills/sejong/docs/SILLOK_TRACE.md"
    "skills/sejong/docs/king-sejong-context.schema.json"
    "skills/sejong/docs/seungjeongwon-run.schema.json"
    "skills/sejong/docs/outcome-quality.schema.json"
    "skills/sejong/docs/product-evidence.schema.json"
    "skills/sejong/docs/sillok-trace-event.schema.json"
    "skills/sejong/docs/PROMPT_OVERLAYS.md"
    "skills/sejong/docs/PROTOCOL.md"
    "skills/sejong/docs/SEUNGJEONGWON_EXECUTOR.md"
    "skills/sejong/docs/BUNDLE_VALIDATOR.md"
    "skills/sejong/docs/TEAM_EXECUTOR.md"
    "skills/sejong/docs/scripts/king_sejong_hooks.py"
    "skills/sejong/docs/scripts/sejong_integrated_quality_gate.py"
    "skills/sejong/docs/scripts/seungjeongwon_run.py"
    "skills/sejong/docs/scripts/outcome_quality_evaluator.py"
    "skills/sejong/docs/scripts/product_evidence_gate.py"
    "skills/sejong/docs/scripts/sejong_context.py"
    "skills/sejong/docs/scripts/sillok_trace.py"
    "skills/sejong/docs/scripts/test_king_sejong_hooks.py"
    "skills/sejong/docs/scripts/test_sejong_integrated_quality_gate.py"
    "skills/sejong/docs/scripts/test_seungjeongwon_run.py"
    "skills/sejong/docs/scripts/test_outcome_quality_evaluator.py"
    "skills/sejong/docs/scripts/test_product_evidence_gate.py"
    "skills/sejong/docs/scripts/test_install_sejong.py"
    "skills/sejong/docs/scripts/test_king_sejong_e2e.py"
    "skills/sejong/docs/scripts/test_sejong_context.py"
    "skills/sejong/docs/scripts/test_sillok_trace.py"
    "skills/sejong/docs/scripts/test_team_executor.py"
    "skills/sejong/docs/scripts/team_executor.py"
    "skills/sejong/docs/scripts/validate_json_contracts.py"
    "skills/uigwe/SKILL.md"
    "skills/seungjeongwon/SKILL.md"
    "skills/why-gate/SKILL.md"
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
  verify_tree_matches "$SOURCE_ROOT/.agents/skills/why-gate" "$root/skills/why-gate" "skills/why-gate/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/docs/sejong" "$root/skills/sejong/docs" "skills/sejong/docs/" || drift=1
  verify_tree_matches "$SOURCE_ROOT/plugins/king-sejong" "$root/plugins/cache/$PLUGIN_MARKETPLACE/$PLUGIN_NAME/$PLUGIN_VERSION" "plugins/cache/$PLUGIN_MARKETPLACE/$PLUGIN_NAME/$PLUGIN_VERSION/" || drift=1
  verify_user_hooks_config "$root" || drift=1
  if [[ "$LEGACY_DIRECT_HOOKS" -eq 0 ]]; then
    verify_user_plugin_adapter "$root" || drift=1
  fi
  verify_user_codex_guidance "$root" || drift=1

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
  copy_dir "$SOURCE_ROOT/.agents/skills/why-gate" "$target_root/.agents/skills/why-gate"
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
  .agents/skills/why-gate/
  docs/sejong/

Invoke with:
  \$sejong <broad request>
  \$jangyeongsil <research request>
  \$jiphyeonjeon <decision request>
  \$uigwe <formal planning request>
  \$seungjeongwon <execution request>
  \$why-gate <rationale checkpoint>
EOF
}

install_user_scope() {
  local codex_home=${CODEX_HOME:-$HOME/.codex}
  local skill_root="$codex_home/skills"
  local managed_guidance_block=""

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
  copy_dir "$SOURCE_ROOT/.agents/skills/why-gate" "$skill_root/why-gate"
  copy_dir "$SOURCE_ROOT/docs/sejong" "$skill_root/sejong/docs"
  copy_dir "$SOURCE_ROOT/plugins/king-sejong" "$codex_home/plugins/cache/$PLUGIN_MARKETPLACE/$PLUGIN_NAME/$PLUGIN_VERSION"

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
  if [[ "$LEGACY_DIRECT_HOOKS" -eq 0 ]]; then
    configure_user_plugin "$codex_home"
  fi
  if [[ "$CODEX_GUIDANCE" != "none" ]]; then
    write_codex_guidance_block "$codex_home"
    managed_guidance_block="
Managed guidance:
  $codex_home/AGENTS.md"
  fi

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
  skills/why-gate/
  plugins/cache/$PLUGIN_MARKETPLACE/$PLUGIN_NAME/$PLUGIN_VERSION/

Managed hooks:
  $codex_home/config.toml
  $codex_home/sejong/state/active-context.json
$managed_guidance_block

Invoke from any Codex workspace with:
  \$sejong <broad request>
  \$jangyeongsil <research request>
  \$jiphyeonjeon <decision request>
  \$uigwe <formal planning request>
  \$seungjeongwon <execution request>
  \$why-gate <rationale checkpoint>
EOF
}

if [[ "$UPDATE_CHECK" -eq 1 ]]; then
  report_update_state
  exit 0
fi

if [[ "$AUTO_UPDATE" -eq 1 ]]; then
  auto_update_source
fi

if [[ "$CODEX_GUIDANCE" == "print" || "$PRINT_CODEX_GUIDANCE" -eq 1 ]]; then
  print_codex_guidance_block
  exit 0
fi

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
