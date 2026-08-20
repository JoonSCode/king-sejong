# Work Lifecycle

**Status:** Draft

King Sejong Core owns the shared evidence boundary for learning from completed
work. It records sanitized structured events, derives review-only lesson
candidates from repeated independent runs, and projects lifecycle counts into
terminal cleanup summaries.

## Privacy Boundary

Core never copies raw transcripts, prompts, messages, secrets, or private
absolute paths into the lifecycle ledger. A work event stores only:

- a stable event and run identity
- an allowlisted event type and epistemic status
- a normalized pattern key
- short sanitized summary, response, and outcome fields
- source references and SHA-256 digests
- explicit privacy assertions

The JSON schema rejects unknown fields. The CLI also rejects secret-like text
and private home-directory paths before it creates or appends a ledger.
Rejected input is not quarantined because doing so would persist the unsafe
payload under a different name.

## Evidence Threshold

A single event cannot become a lesson candidate. `derive-candidate` requires
the same pattern key in at least two independent run IDs. Candidate identity,
event order, evidence digests, and generated time are deterministic for the
same ledger contents.

Lesson candidates have:

- `status: candidate`
- `verification: manual_review_required`
- `activation_authority: none`
- `source_evidence_policy: structured_sanitized_refs_only`

Core does not install a skill, activate a hook, change a repository policy, or
infer a root cause from a candidate. Consumers must rehash referenced evidence
and retain their own approval boundary.

## CLI

```bash
uv run docs/sejong/scripts/work_lifecycle.py record-event \
  --event <event.json> --ledger <work-events.jsonl>

uv run docs/sejong/scripts/work_lifecycle.py derive-candidate \
  --ledger <work-events.jsonl> \
  --pattern-key <normalized-pattern-key> \
  --output <lesson-candidate.json>
```

Ledger and candidate files are written with user-private permissions. Appends
use an exclusive file lock, and candidate replacement is atomic.

## Finalization

`sejong_cleanup.py finalize-run` includes a `lifecycle` object in
`run-summary.json` with:

- work event and lesson candidate counts
- compact relative references to the ledgers and candidates
- worker lease and cleanup receipt counts
- cleanup receipt status counts
- exact lease IDs whose released proof is missing

Malformed lifecycle artifacts fail finalization before destructive cleanup.
Standard `work-events.jsonl` and `lesson-candidate.json` names are compact
artifacts retained under the normal external-runtime retention policy.

## Ownership

King Sejong Core owns event and candidate schemas, deterministic derivation,
terminal summary projection, and retention behavior. Agent Company may consume
a validated candidate to create a company-scoped proposal, but it does not own
the Core ledger or cleanup authority. Product repositories may add adapters
later; they do not receive lifecycle authority by default.
