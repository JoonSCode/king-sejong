#!/usr/bin/env bash

set -euo pipefail

ORIGINAL_ARGS=("$@")

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
    ${CODEX_HOME:-~/.codex}/sejong/state/
    ${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/core-install-identity.json

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
RUNTIME_AUTHORITY_EPOCH=2
INSTALL_SOURCE_ROOT=""
USER_INSTALL_SOURCE_SNAPSHOT=""
USER_INSTALL_STAGED_CANONICAL=""

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

BOOTSTRAP_SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
PYTHON_RUNNER="$BOOTSTRAP_SCRIPT_DIR/../docs/sejong/scripts/run_with_supported_python.sh"
if [[ ! -f "$PYTHON_RUNNER" ]]; then
  echo "King Sejong Python launcher is missing: $PYTHON_RUNNER" >&2
  exit 1
fi
# shellcheck source=../docs/sejong/scripts/run_with_supported_python.sh
source "$PYTHON_RUNNER"
sejong_select_python
export PYTHONDONTWRITEBYTECODE=1

canonical_path() {
  sejong_run_python - "$1" <<'PY'
import sys
from pathlib import Path

print(Path(sys.argv[1]).expanduser().resolve())
PY
}

same_path() {
  sejong_run_python - "$1" "$2" <<'PY'
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
  sejong_run_python - "$1" "$2" <<'PY'
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
for candidate in re.findall(r'python3\s+"([^"]+)"', text):
    if path_key(candidate) == expected:
        raise SystemExit(0)
raise SystemExit(1)
PY
}

SCRIPT_DIR=$(canonical_path "$(dirname "${BASH_SOURCE[0]}")")
SOURCE_ROOT=$(canonical_path "$SCRIPT_DIR/..")
INSTALL_SOURCE_ROOT="$SOURCE_ROOT"
SOURCE_ONLY_PATHS=(
  "AGENTS.md"
)
CORE_IDENTITY_RELATIVE_PATH="state/core-install-identity.json"

cleanup_user_install_staging() {
  if [[ -n "$USER_INSTALL_STAGED_CANONICAL" && -f "$USER_INSTALL_STAGED_CANONICAL" ]]; then
    rm -f -- "$USER_INSTALL_STAGED_CANONICAL"
  fi
  if [[ -n "$USER_INSTALL_SOURCE_SNAPSHOT" && -d "$USER_INSTALL_SOURCE_SNAPSHOT" ]]; then
    case "$USER_INSTALL_SOURCE_SNAPSHOT" in
      */sejong/state/install-staging/source.*)
        rm -rf -- "$USER_INSTALL_SOURCE_SNAPSHOT"
        ;;
      *)
        echo "refusing to remove unexpected install staging path: $USER_INSTALL_SOURCE_SNAPSHOT" >&2
        ;;
    esac
  fi
}

trap cleanup_user_install_staging EXIT

acquire_user_install_lock_and_reexec() {
  local codex_home=$1
  shift
  local lock_path="$codex_home/sejong/state/locks/user-install.lock"

  mkdir -p "$(dirname "$lock_path")"
  sejong_run_python - "$lock_path" "${BASH_SOURCE[0]}" "$@" <<'PY'
import fcntl
import math
import os
import subprocess
import sys
import time
from pathlib import Path

lock_path = Path(sys.argv[1])
installer = sys.argv[2]
installer_args = sys.argv[3:]
raw_timeout = os.environ.get("SEJONG_INSTALL_LOCK_TIMEOUT_SECONDS", "5.0")
try:
    timeout_seconds = float(raw_timeout)
except ValueError:
    raise SystemExit(f"invalid SEJONG_INSTALL_LOCK_TIMEOUT_SECONDS={raw_timeout!r}")
if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
    raise SystemExit(f"invalid SEJONG_INSTALL_LOCK_TIMEOUT_SECONDS={raw_timeout!r}")

started = time.monotonic()


def publish_test_pid(environment_name, process_id):
    configured = os.environ.get(environment_name)
    if not configured:
        return
    target = Path(configured)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(f"{process_id}\n", encoding="utf-8")
    os.replace(temporary, target)


with lock_path.open("a+", encoding="utf-8") as handle:
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() - started >= timeout_seconds:
                raise SystemExit(
                    f"timed out acquiring King Sejong user install lock: {lock_path}"
                )
            time.sleep(min(0.05, timeout_seconds))
    publish_test_pid("SEJONG_INSTALL_TEST_LOCK_OWNER_PID_FILE", os.getpid())
    environment = os.environ.copy()
    environment["SEJONG_INSTALL_LOCK_HELD"] = "1"
    environment["SEJONG_INSTALL_LOCK_FD"] = str(handle.fileno())
    child = subprocess.Popen(
        ["bash", installer, *installer_args],
        env=environment,
        pass_fds=(handle.fileno(),),
    )
    publish_test_pid("SEJONG_INSTALL_TEST_MUTATOR_PID_FILE", child.pid)
    raise SystemExit(child.wait())
PY
}

validate_inherited_user_install_lock() {
  local codex_home=$1
  local lock_path="$codex_home/sejong/state/locks/user-install.lock"
  local lock_fd=${SEJONG_INSTALL_LOCK_FD:-}

  sejong_run_python - "$lock_path" "$lock_fd" <<'PY'
import fcntl
import os
import sys
from pathlib import Path

lock_path = Path(sys.argv[1])
try:
    lock_fd = int(sys.argv[2])
    descriptor_stat = os.fstat(lock_fd)
    path_stat = lock_path.stat()
except (IndexError, OSError, TypeError, ValueError) as error:
    raise SystemExit(f"invalid inherited King Sejong user install lock: {error}")
if (descriptor_stat.st_dev, descriptor_stat.st_ino) != (path_stat.st_dev, path_stat.st_ino):
    raise SystemExit("inherited King Sejong user install lock does not match the target path")
try:
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit("inherited King Sejong user install descriptor does not own the lock")
PY
}

reject_unsupported_authority_downgrade() {
  local codex_home=$1
  local transaction_path="$codex_home/sejong/state/install-transaction.json"

  sejong_run_python - "$transaction_path" "$RUNTIME_AUTHORITY_EPOCH" <<'PY'
import json
import sys
from pathlib import Path

transaction_path = Path(sys.argv[1])
target_epoch = int(sys.argv[2])
try:
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
except FileNotFoundError:
    raise SystemExit(0)
except (json.JSONDecodeError, OSError, UnicodeError):
    raise SystemExit("existing King Sejong install transaction is unreadable; no files were modified")
if not isinstance(transaction, dict):
    raise SystemExit("existing King Sejong install transaction is invalid; no files were modified")
minimum_epoch = transaction.get(
    "minimum_runtime_authority_epoch",
    transaction.get("runtime_authority_epoch", 0),
)
runtime_epoch = transaction.get("runtime_authority_epoch", 0)
if (
    type(minimum_epoch) is not int
    or minimum_epoch < 0
    or type(runtime_epoch) is not int
    or runtime_epoch < 0
):
    raise SystemExit("existing King Sejong runtime authority epoch is invalid; no files were modified")
minimum_epoch = max(minimum_epoch, runtime_epoch)
if minimum_epoch >= 2 and target_epoch < minimum_epoch:
    raise SystemExit(
        "Legacy-authority rollback is unsupported because V2 state exists. No files were modified."
    )
PY
}

create_user_install_source_snapshot() {
  local codex_home=$1
  local staging_root="$codex_home/sejong/state/install-staging"

  mkdir -p "$staging_root"
  USER_INSTALL_SOURCE_SNAPSHOT=$(mktemp -d "$staging_root/source.XXXXXX")
  mkdir -p "$USER_INSTALL_SOURCE_SNAPSHOT/.agents/skills" "$USER_INSTALL_SOURCE_SNAPSHOT/docs" "$USER_INSTALL_SOURCE_SNAPSHOT/plugins"
  cp -R "$SOURCE_ROOT/.agents/skills/." "$USER_INSTALL_SOURCE_SNAPSHOT/.agents/skills/"
  cp -R "$SOURCE_ROOT/docs/sejong" "$USER_INSTALL_SOURCE_SNAPSHOT/docs/sejong"
  cp -R "$SOURCE_ROOT/plugins/king-sejong" "$USER_INSTALL_SOURCE_SNAPSHOT/plugins/king-sejong"
  find "$USER_INSTALL_SOURCE_SNAPSHOT" -type d -name __pycache__ -prune -exec rm -rf {} +
  find "$USER_INSTALL_SOURCE_SNAPSHOT" -type f -name .DS_Store -delete
  INSTALL_SOURCE_ROOT="$USER_INSTALL_SOURCE_SNAPSHOT"
}

wait_for_user_install_test_snapshot_release() {
  local ready_path=${SEJONG_INSTALL_TEST_SNAPSHOT_READY_FILE:-}
  local release_path=${SEJONG_INSTALL_TEST_SNAPSHOT_RELEASE_FILE:-}

  if [[ -z "$ready_path" && -z "$release_path" ]]; then
    return
  fi
  if [[ -z "$ready_path" || -z "$release_path" ]]; then
    echo "both snapshot test barrier paths are required" >&2
    exit 1
  fi
  sejong_run_python - "$ready_path" "$release_path" <<'PY'
import os
import sys
import time
from pathlib import Path

ready_path = Path(sys.argv[1])
release_path = Path(sys.argv[2])
ready_path.parent.mkdir(parents=True, exist_ok=True)
tmp_path = ready_path.with_name(f".{ready_path.name}.{os.getpid()}.tmp")
tmp_path.write_text("snapshot-ready\n", encoding="utf-8")
os.replace(tmp_path, ready_path)
deadline = time.monotonic() + 10.0
while not release_path.exists():
    if time.monotonic() >= deadline:
        raise SystemExit("timed out waiting for snapshot test release")
    time.sleep(0.02)
PY
}

wait_for_user_install_test_maintenance_release() {
  local ready_path=${SEJONG_INSTALL_TEST_MAINTENANCE_READY_FILE:-}
  local release_path=${SEJONG_INSTALL_TEST_MAINTENANCE_RELEASE_FILE:-}

  if [[ -z "$ready_path" && -z "$release_path" ]]; then
    return
  fi
  if [[ -z "$ready_path" || -z "$release_path" ]]; then
    echo "both maintenance test barrier paths are required" >&2
    exit 1
  fi
  sejong_run_python - "$ready_path" "$release_path" <<'PY'
import os
import sys
import time
from pathlib import Path

ready_path = Path(sys.argv[1])
release_path = Path(sys.argv[2])
ready_path.parent.mkdir(parents=True, exist_ok=True)
tmp_path = ready_path.with_name(f".{ready_path.name}.{os.getpid()}.tmp")
tmp_path.write_text("maintenance-ready\n", encoding="utf-8")
os.replace(tmp_path, ready_path)
deadline = time.monotonic() + 15.0
while not release_path.exists():
    if time.monotonic() >= deadline:
        raise SystemExit("timed out waiting for maintenance test release")
    time.sleep(0.02)
PY
}

atomic_publish_file() {
  local tmp_file=$1
  local target_file=$2

  sejong_run_python - "$tmp_file" "$target_file" <<'PY'
import os
import sys
from pathlib import Path

tmp_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
with tmp_path.open("rb") as handle:
    os.fsync(handle.fileno())
os.replace(tmp_path, target_path)
directory_fd = os.open(target_path.parent, os.O_RDONLY)
try:
    os.fsync(directory_fd)
finally:
    os.close(directory_fd)
PY
}

print_codex_guidance_block() {
  cat <<'EOF'
<!-- BEGIN King Sejong Codex Guidance -->
# King Sejong Codex Guidance

King Sejong provides Codex-native skills and protocols. Follow host instructions, tool conditions, and the user's scope and authorization.

Always treat King Sejong as available for broad, uncertain, strategic, or goal-bearing work, even when the user does not type `$sejong`.

Route broad or goal-bearing work through Sejong lead synthesis. Preserve the active goal, settled decisions, and prior authorization across follow-ups; interpret corrections and questions within that goal unless the user changes it. Completing a requested deliverable ends that run, not the separate activation of a continuous Company session.

Accept vague thoughts and partial briefs. A complete brief is an output of Uigwe, not an entry requirement. Uigwe helps discover the goal, scope, desired quality, design, and completion criteria through context review, informed recommendations, credible alternatives with reasons, focused questions, and free responses. Do not merely ask the user to fill the missing fields. For a genuinely unresolved choice that materially changes product experience, ongoing maintenance, significant resources, or the user's stated learning direction, distinguish settled scope from the remaining choice. Show the criteria, credible alternatives, relevant pros and cons, evidence, recommendation, strongest counterargument, and conditions that would change it, following the user's preferred presentation style. For an unresolved consequential choice owned by the user, ask for and wait for their explicit choice before dependent execution; continue independent authorized work while waiting. Do not reopen a settled choice merely for learning. Decide local implementation tactics independently within agreed boundaries, explain valuable material reasons and revisit conditions, and continue without waiting for approval. Reuse prior answers and continue independent authorized work while a required answer is pending.

Choose the next useful surface: JangYeongsil for missing evidence; Jiphyeonjeon when conflicting evidence or alternatives warrant structured debate; Uigwe for collaborative intent/design discovery, unresolved acceptance boundaries, or requested formal planning; Seungjeongwon for execution and verification. Research, advice, and proposal requests finish at their requested deliverable. Reuse settled execution contracts without a redundant interview or planning bundle.

Treat proposals and factual claims as judgment inputs. Explain material reasons, counterevidence, and better alternatives; preserve explicit decisions unless new evidence changes their basis. Reuse relevant history and references with their rationale, source, applicability, limits, and superseding decisions. Past transcripts and completed worker or automation instructions are historical evidence, not renewed authority.

Before creating or replacing a meaningful solution, consider relevant existing project assets, platform capabilities, installed dependencies, open source, installed skills, and expert methods. Reuse sufficient prior evidence; investigate further only when fit or freshness could change the decision. Choose direct reuse, adaptation, or local implementation by current requirements and total burden, without a search quota or allowing external instructions to override the current user contract.

Break large work into bounded steps while preserving the requested final quality. Delegate independent work when it improves quality or completion time; choose supported models and reasoning per task. The lead owns synthesis and final completion. Diagnose failed attempts and adapt within the approved scope. Show completed work, remaining work, failures, and the next action. Scheduled runs record a required decision and exit; they resume from explicit approval on a later run.

During an explicitly active Agent Company session, begin every ordinary prose final reply with the responding subject and the workers whose results that reply actually used, giving each a brief responsibility. A direct reply has no worker participant. Keep this continuity on follow-up questions; earlier commentary or external documentation does not substitute for the final reply. Using a skill, planning a worker, or observing a worker without consuming its result is not participation evidence. Do not alter strict JSON, code-only, or other exact-format output; provide attribution separately only when surrounding prose permits it. This conditional Company rule does not activate Company for other Sejong work.

Verify the actual user path and the claim being made. Distinguish product execution from manual assistance, automated checks from observed usability, and publication from business outcomes. Match tests to the change and expand them for new failures or unresolved risks. Reuse applicable evaluation cases; do not claim improved quality or savings from static checks alone.

Store Sejong runtime artifacts under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}` unless the user explicitly asks to promote a tracked artifact. Do not use non-Sejong runtime paths as Sejong state. Hooks and schemas are guardrails; completion requires evidence of the requested outcome.
<!-- END King Sejong Codex Guidance -->
EOF
}

write_codex_guidance_block() {
  local codex_home=$1
  local agents_file="$codex_home/AGENTS.md"
  local filtered_file
  local tmp_file

  mkdir -p "$codex_home"
  touch "$agents_file"
  filtered_file=$(mktemp "${agents_file}.filtered.XXXXXX")
  tmp_file=$(mktemp "${agents_file}.tmp.XXXXXX")
  awk '
    /^<!-- BEGIN King Sejong Codex Guidance -->$/ { skip = 1; next }
    /^<!-- END King Sejong Codex Guidance -->$/ { skip = 0; next }
    !skip { print }
  ' "$agents_file" > "$filtered_file"
  {
    sed '/^[[:space:]]*$/N;/^\n$/D' "$filtered_file"
    echo
    print_codex_guidance_block
  } > "$tmp_file"
  mv "$tmp_file" "$agents_file"
  rm -f "$filtered_file"
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

verify_tree_matches_without_canonical_hook() {
  local src=$1
  local dest=$2
  local label=$3

  if ! diff -qr -x '.DS_Store' -x '__pycache__' -x 'king_sejong_hooks.py' "$src" "$dest" >/dev/null; then
    echo "managed install differs from source before canonical publish: $label" >&2
    diff -qr -x '.DS_Store' -x '__pycache__' -x 'king_sejong_hooks.py' "$src" "$dest" >&2 || true
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

core_identity_runtime_root() {
  local codex_home=$1

  if [[ -n "${SEJONG_HOME:-}" ]]; then
    canonical_path "$SEJONG_HOME"
  else
    canonical_path "$codex_home/sejong"
  fi
}

core_identity_path() {
  local codex_home=$1
  local runtime_root

  runtime_root=$(core_identity_runtime_root "$codex_home")
  echo "$runtime_root/$CORE_IDENTITY_RELATIVE_PATH"
}

core_identity_source_commit() {
  if git -C "$SOURCE_ROOT" rev-parse HEAD >/dev/null 2>&1; then
    git -C "$SOURCE_ROOT" rev-parse HEAD
    return
  fi
  sejong_run_python - "$INSTALL_SOURCE_ROOT" "$INSTALL_SOURCE_ROOT/docs/sejong/scripts" <<'PY'
import sys
from pathlib import Path

source_root = Path(sys.argv[1])
sys.path.insert(0, sys.argv[2])
from core_install_identity import SOURCE_MANAGED_SURFACES, snapshot_managed_surfaces

print(snapshot_managed_surfaces(source_root, SOURCE_MANAGED_SURFACES)["managed_content_sha256"])
PY
}

core_identity_source_tree_state() {
  if ! git -C "$SOURCE_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "dirty"
  elif source_tree_dirty; then
    echo "dirty"
  else
    echo "clean"
  fi
}

write_user_core_identity() {
  local codex_home=$1
  local identity_path
  local identity_helper="$INSTALL_SOURCE_ROOT/docs/sejong/scripts/core_install_identity.py"
  local source_commit
  local source_tree_state

  identity_path=$(core_identity_path "$codex_home")
  source_commit=$(core_identity_source_commit)
  source_tree_state=$(core_identity_source_tree_state)
  sejong_run_python "$identity_helper" write \
    --source-root "$INSTALL_SOURCE_ROOT" \
    --installed-root "$codex_home" \
    --output "$identity_path" \
    --source-commit "$source_commit" \
    --source-tree-state "$source_tree_state"
}

verify_user_core_identity() {
  local codex_home=$1
  local identity_path
  local identity_helper="$INSTALL_SOURCE_ROOT/docs/sejong/scripts/core_install_identity.py"
  local source_commit
  local source_tree_state

  identity_path=$(core_identity_path "$codex_home")
  source_commit=$(core_identity_source_commit)
  source_tree_state=$(core_identity_source_tree_state)
  sejong_run_python "$identity_helper" verify \
    --identity "$identity_path" \
    --source-root "$INSTALL_SOURCE_ROOT" \
    --installed-root "$codex_home" \
    --source-commit "$source_commit" \
    --source-tree-state "$source_tree_state"
}

ensure_hooks_feature_enabled() {
  local config_file=$1
  local tmp_file

  mkdir -p "$(dirname "$config_file")"
  touch "$config_file"
  tmp_file=$(mktemp "${config_file}.tmp.XXXXXX")

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
  tmp_file=$(mktemp "${config_file}.tmp.XXXXXX")

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
# END King Sejong hooks
EOF

  mv "$tmp_file" "$config_file"
}

remove_managed_hooks_block() {
  local config_file=$1
  local tmp_file

  [[ -f "$config_file" ]] || return 0
  tmp_file=$(mktemp "${config_file}.tmp.XXXXXX")

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
  tmp_file=$(mktemp "${config_file}.tmp.XXXXXX")

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

ensure_sejong_state_dir() {
  local codex_home=$1
  mkdir -p "$codex_home/sejong/state"
}

runtime_authority_digest() {
  sejong_run_python - "$INSTALL_SOURCE_ROOT" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
files = (
    ("canonical-hook", root / "docs/sejong/scripts/king_sejong_hooks.py"),
    ("context", root / "docs/sejong/scripts/sejong_context.py"),
    ("session-binding", root / "docs/sejong/scripts/sejong_session_binding.py"),
    ("paths", root / "docs/sejong/scripts/sejong_paths.py"),
    ("runtime-lock", root / "docs/sejong/scripts/sejong_runtime_lock.py"),
    ("plugin-runner", root / "plugins/king-sejong/hooks/king-sejong-hook.py"),
    ("plugin-hooks", root / "plugins/king-sejong/hooks/hooks.json"),
)
digest = hashlib.sha256()
for label, path in files:
    digest.update(label.encode("utf-8"))
    digest.update(b"\0")
    digest.update(hashlib.sha256(path.read_bytes()).digest())
print(digest.hexdigest())
PY
}

managed_source_digest() {
  sejong_run_python - "$INSTALL_SOURCE_ROOT" <<'PY'
import hashlib
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
managed_roots = (
    root / ".agents/skills/sejong",
    root / ".agents/skills/jangyeongsil",
    root / ".agents/skills/jiphyeonjeon",
    root / ".agents/skills/uigwe",
    root / ".agents/skills/seungjeongwon",
    root / ".agents/skills/why-gate",
    root / "docs/sejong",
    root / "plugins/king-sejong",
)
digest = hashlib.sha256()
for managed_root in managed_roots:
    if not managed_root.is_dir():
        raise SystemExit(f"missing managed source root: {managed_root}")
    for path in sorted(managed_root.rglob("*"), key=lambda item: os.fsencode(str(item.relative_to(root)))):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.name == ".DS_Store" or not path.is_file():
            continue
        digest.update(os.fsencode(str(relative)))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
print(digest.hexdigest())
PY
}

source_canonical_digest() {
  sejong_run_python - "$INSTALL_SOURCE_ROOT/docs/sejong/scripts/king_sejong_hooks.py" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
}

write_install_transaction() {
  local codex_home=$1
  local status=$2
  local authority_digest=${3:-}
  local managed_digest=${4:-}
  local transaction_path="$codex_home/sejong/state/install-transaction.json"
  local tmp_file
  local source_commit="unavailable"
  local source_dirty=false
  local timestamp

  mkdir -p "$(dirname "$transaction_path")"
  if [[ -z "$authority_digest" ]]; then
    authority_digest=$(runtime_authority_digest)
  fi
  if [[ -z "$managed_digest" ]]; then
    managed_digest=$(managed_source_digest)
  fi
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  if git -C "$SOURCE_ROOT" rev-parse HEAD >/dev/null 2>&1; then
    source_commit=$(git -C "$SOURCE_ROOT" rev-parse HEAD)
    if [[ -n "$(git -C "$SOURCE_ROOT" status --porcelain)" ]]; then
      source_dirty=true
    fi
  fi
  tmp_file=$(mktemp "${transaction_path}.tmp.XXXXXX")
  cat > "$tmp_file" <<EOF
{
  "format": "king-sejong.install-transaction/v0.1",
  "status": "$status",
  "runtime_authority_epoch": $RUNTIME_AUTHORITY_EPOCH,
  "minimum_runtime_authority_epoch": $RUNTIME_AUTHORITY_EPOCH,
  "runtime_authority_sha256": "$authority_digest",
  "managed_source_sha256": "$managed_digest",
  "source_commit": "$source_commit",
  "source_dirty": $source_dirty,
  "updated_at": "$timestamp"
}
EOF
  chmod 0600 "$tmp_file"
  atomic_publish_file "$tmp_file" "$transaction_path"
}

publish_user_install_maintenance_guard() {
  local codex_home=$1
  local authority_digest=$2
  local managed_digest=$3
  local hook_script="$codex_home/skills/sejong/docs/scripts/king_sejong_hooks.py"
  local tmp_file

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "would publish fail-closed install maintenance hook: $hook_script"
    return
  fi
  mkdir -p "$(dirname "$hook_script")"
  tmp_file=$(mktemp "${hook_script}.maintenance.XXXXXX")
  cat > "$tmp_file" <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import sys

PROTECTED_EVENTS = {"PermissionRequest", "PreCompact", "PreToolUse", "Stop"}

event_name = sys.argv[1] if len(sys.argv) > 1 else ""
if event_name in PROTECTED_EVENTS:
    print("King Sejong install maintenance is in progress", file=sys.stderr)
    raise SystemExit(127)
raise SystemExit(0)
PY
  chmod 0755 "$tmp_file"
  atomic_publish_file "$tmp_file" "$hook_script"
  write_install_transaction "$codex_home" "in_progress" "$authority_digest" "$managed_digest"
  if [[ "${SEJONG_INSTALL_TEST_FAIL_AFTER_MAINTENANCE_GUARD:-0}" == "1" ]]; then
    echo "injected failure after King Sejong install maintenance guard" >&2
    exit 75
  fi
}

maybe_fail_user_install_step() {
  local step=$1

  if [[ "${SEJONG_INSTALL_TEST_FAIL_AFTER_STEP:-}" == "$step" ]]; then
    echo "injected failure after King Sejong user install step: $step" >&2
    exit 75
  fi
}

verify_install_transaction() {
  local codex_home=$1
  local transaction_path="$codex_home/sejong/state/install-transaction.json"
  local expected_digest

  expected_digest=$(runtime_authority_digest)
  sejong_run_python - "$transaction_path" "$expected_digest" "$codex_home" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

transaction_path = Path(sys.argv[1])
expected_digest = sys.argv[2]
codex_home = Path(sys.argv[3])
try:
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeError) as error:
    raise SystemExit(f"invalid King Sejong install transaction: {error}")
if transaction.get("format") != "king-sejong.install-transaction/v0.1":
    raise SystemExit("King Sejong install transaction format mismatch")
if (
    transaction.get("status") != "complete"
    or transaction.get("runtime_authority_epoch") != 2
    or transaction.get("minimum_runtime_authority_epoch") != 2
):
    raise SystemExit("King Sejong install transaction is not complete")
if transaction.get("runtime_authority_sha256") != expected_digest:
    raise SystemExit("King Sejong source and transaction authority digests differ")
scripts = codex_home / "skills/sejong/docs/scripts"
plugin = codex_home / "plugins/cache/king-sejong-local/king-sejong/0.1.0/hooks"
files = (
    ("canonical-hook", scripts / "king_sejong_hooks.py"),
    ("context", scripts / "sejong_context.py"),
    ("session-binding", scripts / "sejong_session_binding.py"),
    ("paths", scripts / "sejong_paths.py"),
    ("runtime-lock", scripts / "sejong_runtime_lock.py"),
    ("plugin-runner", plugin / "king-sejong-hook.py"),
    ("plugin-hooks", plugin / "hooks.json"),
)
digest = hashlib.sha256()
for label, path in files:
    digest.update(label.encode("utf-8"))
    digest.update(b"\0")
    digest.update(hashlib.sha256(path.read_bytes()).digest())
if digest.hexdigest() != expected_digest:
    raise SystemExit("King Sejong installed runtime authority digest mismatch")
PY
}

configure_user_hooks() {
  local codex_home=$1
  local config_file="$codex_home/config.toml"
  local hook_script="$codex_home/plugins/cache/$PLUGIN_MARKETPLACE/$PLUGIN_NAME/$PLUGIN_VERSION/hooks/king-sejong-hook.py"

  ensure_hooks_feature_enabled "$config_file"
  if [[ "$LEGACY_DIRECT_HOOKS" -eq 1 ]]; then
    append_managed_hooks_block "$config_file" "$hook_script"
  else
    remove_managed_hooks_block "$config_file"
  fi
  ensure_sejong_state_dir "$codex_home"
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
  local tmp_file

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "would install: $marketplace_file"
    return
  fi

  mkdir -p "$(dirname "$marketplace_file")"
  tmp_file=$(mktemp "${marketplace_file}.tmp.XXXXXX")
  cat > "$tmp_file" <<EOF
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
  mv "$tmp_file" "$marketplace_file"
}

verify_user_hooks_config() {
  local codex_home=$1
  local config_file="$codex_home/config.toml"
  local hook_script="$codex_home/plugins/cache/$PLUGIN_MARKETPLACE/$PLUGIN_NAME/$PLUGIN_VERSION/hooks/king-sejong-hook.py"

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
  if [[ ! -d "$codex_home/sejong/state" ]]; then
    echo "missing King Sejong state directory: $codex_home/sejong/state" >&2
    return 1
  fi
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
  if ! grep -q 'During an explicitly active Agent Company session' "$agents_file"; then
    echo "King Sejong Codex guidance block is missing Company final-reply attribution rule" >&2
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
    "docs/sejong/DELEGATION_RUNTIME.md"
    "docs/sejong/WORK_LIFECYCLE.md"
    "docs/sejong/king-sejong-context.schema.json"
    "docs/sejong/session-binding.schema.json"
    "docs/sejong/repo-index.schema.json"
    "docs/sejong/delegation-run.schema.json"
    "docs/sejong/worker-resource-lease.schema.json"
    "docs/sejong/worker-cleanup-receipt.schema.json"
    "docs/sejong/core-install-identity.schema.json"
    "docs/sejong/external-action-receipt.schema.json"
    "docs/sejong/seungjeongwon-run.schema.json"
    "docs/sejong/outcome-quality.schema.json"
    "docs/sejong/product-evidence.schema.json"
    "docs/sejong/sillok-trace-event.schema.json"
    "docs/sejong/work-event.schema.json"
    "docs/sejong/lesson-candidate.schema.json"
    "docs/sejong/PROMPT_OVERLAYS.md"
    "docs/sejong/PROTOCOL.md"
    "docs/sejong/SEUNGJEONGWON_EXECUTOR.md"
    "docs/sejong/BUNDLE_VALIDATOR.md"
    "docs/sejong/TEAM_EXECUTOR.md"
    "docs/sejong/scripts/king_sejong_hooks.py"
    "docs/sejong/scripts/sejong_integrated_quality_gate.py"
    "docs/sejong/scripts/seungjeongwon_run.py"
    "docs/sejong/scripts/delegation_cleanup.py"
    "docs/sejong/scripts/delegation_receipt_validation.py"
    "docs/sejong/scripts/worker_resource_lease.py"
    "docs/sejong/scripts/worker_resource_model.py"
    "docs/sejong/scripts/worker_resource_validation.py"
    "docs/sejong/scripts/outcome_quality_evaluator.py"
    "docs/sejong/scripts/product_evidence_gate.py"
    "docs/sejong/scripts/sejong_context.py"
    "docs/sejong/scripts/sejong_session_binding.py"
    "docs/sejong/scripts/sejong_paths.py"
    "docs/sejong/scripts/sejong_runtime_lock.py"
    "docs/sejong/scripts/sillok_trace.py"
    "docs/sejong/scripts/delegation_run.py"
    "docs/sejong/scripts/delegation_run_model.py"
    "docs/sejong/scripts/delegation_wave.py"
    "docs/sejong/scripts/delegation_wave_validation.py"
    "docs/sejong/scripts/core_install_identity.py"
    "docs/sejong/scripts/external_action_contract.py"
    "docs/sejong/scripts/external_action_storage.py"
    "docs/sejong/scripts/external_action_receipt.py"
    "docs/sejong/scripts/work_lifecycle.py"
    "docs/sejong/scripts/work_lifecycle_model.py"
    "docs/sejong/scripts/work_lifecycle_summary.py"
    "docs/sejong/scripts/test_king_sejong_hooks.py"
    "docs/sejong/scripts/test_sejong_integrated_quality_gate.py"
    "docs/sejong/scripts/test_seungjeongwon_run.py"
    "docs/sejong/scripts/test_outcome_quality_evaluator.py"
    "docs/sejong/scripts/test_product_evidence_gate.py"
    "docs/sejong/scripts/test_install_sejong.py"
    "docs/sejong/scripts/test_king_sejong_e2e.py"
    "docs/sejong/scripts/test_sejong_context.py"
    "docs/sejong/scripts/test_sejong_doctor.py"
    "docs/sejong/scripts/test_session_binding_context.py"
    "docs/sejong/scripts/test_king_sejong_multisession_e2e.py"
    "docs/sejong/scripts/test_sillok_trace.py"
    "docs/sejong/scripts/test_delegation_run.py"
    "docs/sejong/scripts/test_delegation_wave_validation.py"
    "docs/sejong/scripts/test_core_install_identity.py"
    "docs/sejong/scripts/test_external_action_receipt.py"
    "docs/sejong/scripts/test_team_executor.py"
    "docs/sejong/scripts/test_work_lifecycle.py"
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
  local verification_mode=${2:-complete}
  local source_root=$INSTALL_SOURCE_ROOT
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
    "skills/sejong/docs/DELEGATION_RUNTIME.md"
    "skills/sejong/docs/WORK_LIFECYCLE.md"
    "skills/sejong/docs/king-sejong-context.schema.json"
    "skills/sejong/docs/session-binding.schema.json"
    "skills/sejong/docs/repo-index.schema.json"
    "skills/sejong/docs/delegation-run.schema.json"
    "skills/sejong/docs/worker-resource-lease.schema.json"
    "skills/sejong/docs/worker-cleanup-receipt.schema.json"
    "skills/sejong/docs/core-install-identity.schema.json"
    "skills/sejong/docs/external-action-receipt.schema.json"
    "skills/sejong/docs/seungjeongwon-run.schema.json"
    "skills/sejong/docs/outcome-quality.schema.json"
    "skills/sejong/docs/product-evidence.schema.json"
    "skills/sejong/docs/sillok-trace-event.schema.json"
    "skills/sejong/docs/work-event.schema.json"
    "skills/sejong/docs/lesson-candidate.schema.json"
    "skills/sejong/docs/PROMPT_OVERLAYS.md"
    "skills/sejong/docs/PROTOCOL.md"
    "skills/sejong/docs/SEUNGJEONGWON_EXECUTOR.md"
    "skills/sejong/docs/BUNDLE_VALIDATOR.md"
    "skills/sejong/docs/TEAM_EXECUTOR.md"
    "skills/sejong/docs/scripts/king_sejong_hooks.py"
    "skills/sejong/docs/scripts/sejong_integrated_quality_gate.py"
    "skills/sejong/docs/scripts/seungjeongwon_run.py"
    "skills/sejong/docs/scripts/delegation_cleanup.py"
    "skills/sejong/docs/scripts/delegation_receipt_validation.py"
    "skills/sejong/docs/scripts/worker_resource_lease.py"
    "skills/sejong/docs/scripts/worker_resource_model.py"
    "skills/sejong/docs/scripts/worker_resource_validation.py"
    "skills/sejong/docs/scripts/outcome_quality_evaluator.py"
    "skills/sejong/docs/scripts/product_evidence_gate.py"
    "skills/sejong/docs/scripts/sejong_context.py"
    "skills/sejong/docs/scripts/sejong_session_binding.py"
    "skills/sejong/docs/scripts/sejong_paths.py"
    "skills/sejong/docs/scripts/sejong_runtime_lock.py"
    "skills/sejong/docs/scripts/sillok_trace.py"
    "skills/sejong/docs/scripts/delegation_run.py"
    "skills/sejong/docs/scripts/delegation_run_model.py"
    "skills/sejong/docs/scripts/delegation_wave.py"
    "skills/sejong/docs/scripts/delegation_wave_validation.py"
    "skills/sejong/docs/scripts/core_install_identity.py"
    "skills/sejong/docs/scripts/external_action_contract.py"
    "skills/sejong/docs/scripts/external_action_storage.py"
    "skills/sejong/docs/scripts/external_action_receipt.py"
    "skills/sejong/docs/scripts/work_lifecycle.py"
    "skills/sejong/docs/scripts/work_lifecycle_model.py"
    "skills/sejong/docs/scripts/work_lifecycle_summary.py"
    "skills/sejong/docs/scripts/test_king_sejong_hooks.py"
    "skills/sejong/docs/scripts/test_sejong_integrated_quality_gate.py"
    "skills/sejong/docs/scripts/test_seungjeongwon_run.py"
    "skills/sejong/docs/scripts/test_outcome_quality_evaluator.py"
    "skills/sejong/docs/scripts/test_product_evidence_gate.py"
    "skills/sejong/docs/scripts/test_install_sejong.py"
    "skills/sejong/docs/scripts/test_king_sejong_e2e.py"
    "skills/sejong/docs/scripts/test_sejong_context.py"
    "skills/sejong/docs/scripts/test_sejong_doctor.py"
    "skills/sejong/docs/scripts/test_session_binding_context.py"
    "skills/sejong/docs/scripts/test_king_sejong_multisession_e2e.py"
    "skills/sejong/docs/scripts/test_sillok_trace.py"
    "skills/sejong/docs/scripts/test_delegation_run.py"
    "skills/sejong/docs/scripts/test_delegation_wave_validation.py"
    "skills/sejong/docs/scripts/test_core_install_identity.py"
    "skills/sejong/docs/scripts/test_external_action_receipt.py"
    "skills/sejong/docs/scripts/test_team_executor.py"
    "skills/sejong/docs/scripts/test_work_lifecycle.py"
    "skills/sejong/docs/scripts/team_executor.py"
    "skills/sejong/docs/scripts/validate_json_contracts.py"
    "skills/uigwe/SKILL.md"
    "skills/seungjeongwon/SKILL.md"
    "skills/why-gate/SKILL.md"
  )

  for path in "${required_paths[@]}"; do
    if [[ "$verification_mode" == "pre-publish" && "$path" == "skills/sejong/docs/scripts/king_sejong_hooks.py" ]]; then
      continue
    fi
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

  verify_rewritten_skill_matches "$source_root/.agents/skills/sejong/SKILL.md" "$root/skills/sejong/SKILL.md" "docs/" "skills/sejong/SKILL.md" || drift=1
  verify_rewritten_skill_matches "$source_root/.agents/skills/jangyeongsil/SKILL.md" "$root/skills/jangyeongsil/SKILL.md" "../sejong/docs/" "skills/jangyeongsil/SKILL.md" || drift=1
  verify_rewritten_skill_matches "$source_root/.agents/skills/jiphyeonjeon/SKILL.md" "$root/skills/jiphyeonjeon/SKILL.md" "../sejong/docs/" "skills/jiphyeonjeon/SKILL.md" || drift=1
  verify_rewritten_skill_matches "$source_root/.agents/skills/uigwe/SKILL.md" "$root/skills/uigwe/SKILL.md" "../sejong/docs/" "skills/uigwe/SKILL.md" || drift=1
  verify_rewritten_skill_matches "$source_root/.agents/skills/seungjeongwon/SKILL.md" "$root/skills/seungjeongwon/SKILL.md" "../sejong/docs/" "skills/seungjeongwon/SKILL.md" || drift=1
  verify_tree_matches "$source_root/.agents/skills/sejong/agents" "$root/skills/sejong/agents" "skills/sejong/agents/" || drift=1
  verify_tree_matches "$source_root/.agents/skills/jangyeongsil/agents" "$root/skills/jangyeongsil/agents" "skills/jangyeongsil/agents/" || drift=1
  verify_tree_matches "$source_root/.agents/skills/jiphyeonjeon/agents" "$root/skills/jiphyeonjeon/agents" "skills/jiphyeonjeon/agents/" || drift=1
  verify_tree_matches "$source_root/.agents/skills/uigwe/agents" "$root/skills/uigwe/agents" "skills/uigwe/agents/" || drift=1
  verify_tree_matches "$source_root/.agents/skills/seungjeongwon/agents" "$root/skills/seungjeongwon/agents" "skills/seungjeongwon/agents/" || drift=1
  verify_tree_matches "$source_root/.agents/skills/why-gate" "$root/skills/why-gate" "skills/why-gate/" || drift=1
  if [[ "$verification_mode" == "pre-publish" ]]; then
    verify_tree_matches_without_canonical_hook "$source_root/docs/sejong" "$root/skills/sejong/docs" "skills/sejong/docs/" || drift=1
  else
    verify_tree_matches "$source_root/docs/sejong" "$root/skills/sejong/docs" "skills/sejong/docs/" || drift=1
  fi
  verify_tree_matches "$source_root/plugins/king-sejong" "$root/plugins/cache/$PLUGIN_MARKETPLACE/$PLUGIN_NAME/$PLUGIN_VERSION" "plugins/cache/$PLUGIN_MARKETPLACE/$PLUGIN_NAME/$PLUGIN_VERSION/" || drift=1
  verify_user_hooks_config "$root" || drift=1
  if [[ "$LEGACY_DIRECT_HOOKS" -eq 0 ]]; then
    verify_user_plugin_adapter "$root" || drift=1
  fi
  verify_user_codex_guidance "$root" || drift=1
  if [[ "$verification_mode" != "pre-publish" ]]; then
    verify_user_core_identity "$root" || drift=1
  fi

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
    rsync -a --delete --delete-excluded \
      --exclude '.DS_Store' \
      --exclude '__pycache__/' \
      "$src/" "$dest/"
  else
    rm -rf "$dest"
    cp -R "$src" "$dest"
  fi
}

ensure_user_install_destinations_available() {
  local codex_home=$1
  local managed_paths=(
    "$codex_home/skills/sejong"
    "$codex_home/skills/jangyeongsil"
    "$codex_home/skills/jiphyeonjeon"
    "$codex_home/skills/uigwe"
    "$codex_home/skills/seungjeongwon"
    "$codex_home/skills/why-gate"
    "$codex_home/plugins/cache/$PLUGIN_MARKETPLACE/$PLUGIN_NAME/$PLUGIN_VERSION"
  )

  if [[ "$FORCE" -eq 1 ]]; then
    return
  fi
  for managed_path in "${managed_paths[@]}"; do
    if [[ -e "$managed_path" ]]; then
      echo "destination already exists: $managed_path" >&2
      echo "rerun with --force to replace the managed install path" >&2
      exit 1
    fi
  done
}

stage_user_install_canonical() {
  local codex_home=$1
  local expected_digest=$2
  local staging_root="$codex_home/sejong/state/install-staging"
  local actual_digest

  mkdir -p "$staging_root"
  USER_INSTALL_STAGED_CANONICAL=$(mktemp "$staging_root/king_sejong_hooks.py.XXXXXX")
  cp "$INSTALL_SOURCE_ROOT/docs/sejong/scripts/king_sejong_hooks.py" "$USER_INSTALL_STAGED_CANONICAL"
  chmod 0755 "$USER_INSTALL_STAGED_CANONICAL"
  actual_digest=$(sejong_run_python - "$USER_INSTALL_STAGED_CANONICAL" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)
  if [[ "$actual_digest" != "$expected_digest" ]]; then
    echo "staged canonical hook digest differs from the frozen source snapshot" >&2
    exit 1
  fi
}

copy_user_docs_without_canonical_hook() {
  local src=$1
  local dest=$2
  local parent
  local staged_docs

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "would install without publishing canonical hook: $dest"
    return
  fi
  parent=$(dirname "$dest")
  mkdir -p "$parent"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude '.DS_Store' \
      --exclude '__pycache__/' \
      --exclude 'scripts/king_sejong_hooks.py' \
      "$src/" "$dest/"
    return
  fi

  staged_docs=$(mktemp -d "$parent/.sejong-docs.XXXXXX")
  cp -R "$src/." "$staged_docs/"
  rm -f "$staged_docs/scripts/king_sejong_hooks.py"
  mkdir -p "$staged_docs/scripts"
  if [[ -f "$dest/scripts/king_sejong_hooks.py" ]]; then
    cp "$dest/scripts/king_sejong_hooks.py" "$staged_docs/scripts/king_sejong_hooks.py"
  fi
  rm -rf "$dest"
  mv "$staged_docs" "$dest"
}

publish_user_install_canonical() {
  local codex_home=$1
  local expected_digest=$2
  local target="$codex_home/skills/sejong/docs/scripts/king_sejong_hooks.py"
  local tmp_file
  local actual_digest

  if [[ -z "$USER_INSTALL_STAGED_CANONICAL" || ! -f "$USER_INSTALL_STAGED_CANONICAL" ]]; then
    echo "missing staged canonical hook for final publish" >&2
    exit 1
  fi
  actual_digest=$(sejong_run_python - "$USER_INSTALL_STAGED_CANONICAL" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)
  if [[ "$actual_digest" != "$expected_digest" ]]; then
    echo "staged canonical hook changed before final publish" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$target")"
  tmp_file=$(mktemp "${target}.publish.XXXXXX")
  cp "$USER_INSTALL_STAGED_CANONICAL" "$tmp_file"
  chmod 0755 "$tmp_file"
  atomic_publish_file "$tmp_file" "$target"
  rm -f -- "$USER_INSTALL_STAGED_CANONICAL"
  USER_INSTALL_STAGED_CANONICAL=""
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
  local authority_digest
  local managed_digest
  local canonical_digest
  local identity_path

  codex_home=$(canonical_path "$codex_home")
  skill_root="$codex_home/skills"

  if [[ "${SEJONG_INSTALL_LOCK_HELD:-0}" == "1" ]]; then
    validate_inherited_user_install_lock "$codex_home"
  fi

  if [[ "$VERIFY_ONLY" -eq 1 ]]; then
    verify_user_install "$codex_home"
    verify_install_transaction "$codex_home"
    exit 0
  fi

  ensure_user_install_destinations_available "$codex_home"
  reject_unsupported_authority_downgrade "$codex_home"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    create_user_install_source_snapshot "$codex_home"
    wait_for_user_install_test_snapshot_release
  fi
  authority_digest=$(runtime_authority_digest)
  managed_digest=$(managed_source_digest)
  canonical_digest=$(source_canonical_digest)
  if [[ "$DRY_RUN" -eq 0 ]]; then
    stage_user_install_canonical "$codex_home" "$canonical_digest"
  fi

  publish_user_install_maintenance_guard "$codex_home" "$authority_digest" "$managed_digest"
  wait_for_user_install_test_maintenance_release
  maybe_fail_user_install_step "maintenance"

  copy_dir "$INSTALL_SOURCE_ROOT/.agents/skills/sejong" "$skill_root/sejong"
  copy_dir "$INSTALL_SOURCE_ROOT/.agents/skills/jangyeongsil" "$skill_root/jangyeongsil"
  copy_dir "$INSTALL_SOURCE_ROOT/.agents/skills/jiphyeonjeon" "$skill_root/jiphyeonjeon"
  copy_dir "$INSTALL_SOURCE_ROOT/.agents/skills/uigwe" "$skill_root/uigwe"
  copy_dir "$INSTALL_SOURCE_ROOT/.agents/skills/seungjeongwon" "$skill_root/seungjeongwon"
  copy_dir "$INSTALL_SOURCE_ROOT/.agents/skills/why-gate" "$skill_root/why-gate"
  maybe_fail_user_install_step "skills"
  copy_user_docs_without_canonical_hook "$INSTALL_SOURCE_ROOT/docs/sejong" "$skill_root/sejong/docs"
  maybe_fail_user_install_step "docs"
  copy_dir "$INSTALL_SOURCE_ROOT/plugins/king-sejong" "$codex_home/plugins/cache/$PLUGIN_MARKETPLACE/$PLUGIN_NAME/$PLUGIN_VERSION"
  maybe_fail_user_install_step "plugin"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    identity_path=$(core_identity_path "$codex_home")
    echo "would rewrite repo-local doc paths for user-scope skill layout"
    echo "would write Core install identity: $identity_path"
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
  maybe_fail_user_install_step "config"

  verify_user_install "$codex_home" "pre-publish"
  maybe_fail_user_install_step "verified"
  publish_user_install_canonical "$codex_home" "$canonical_digest"
  maybe_fail_user_install_step "canonical"
  write_user_core_identity "$codex_home"
  verify_user_install "$codex_home"
  write_install_transaction "$codex_home" "complete" "$authority_digest" "$managed_digest"
  verify_install_transaction "$codex_home"
  identity_path=$(core_identity_path "$codex_home")

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
  $codex_home/sejong/state/
$managed_guidance_block

Installed Core identity:
  $identity_path

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

if [[ "$AUTO_UPDATE" -eq 1 && "${SEJONG_INSTALL_LOCK_HELD:-0}" != "1" ]]; then
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
    if [[ "$VERIFY_ONLY" -eq 0 && "$DRY_RUN" -eq 0 && "${SEJONG_INSTALL_LOCK_HELD:-0}" != "1" ]]; then
      user_codex_home=$(canonical_path "${CODEX_HOME:-$HOME/.codex}")
      if acquire_user_install_lock_and_reexec "$user_codex_home" "${ORIGINAL_ARGS[@]}"; then
        exit 0
      else
        user_install_lock_status=$?
        exit "$user_install_lock_status"
      fi
    fi
    install_user_scope
    ;;
  *)
    echo "unsupported scope: $SCOPE" >&2
    exit 1
    ;;
esac
