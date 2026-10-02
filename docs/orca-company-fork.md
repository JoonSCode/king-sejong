# Core for Orca-specialized Agent Company

This source-only direction applies to the dedicated Core of the independent
Orca Company fork. It is
not an installed skill contract or evidence of a working Orca backend.

## Purpose and permitted divergence

The user selected the already-created B branch as the workspace for option C:
independent Orca-specific development. Existing Core is source material for this
work, not a required shared dependency or preserved architecture.

Design directly for the approved Orca organization and execution behavior.
Reuse, redesign, simplify, remove, or replace Core components according to fit
and total burden. Dedicated Core work is not restricted to a thin adapter or to
changes justified by an already-observed Codex blocker. Upstream API/packaging
compatibility, shared implementation, existing layer boundaries, and eventual
merge-back are not acceptance requirements. A rewrite is available when it is
the better implementation choice, rather than mandatory because this is a fork.

Company organizational policy, governing contracts, and Orca execution are
responsibilities that must be covered; the internal module boundaries may change.
Orca supplies its supported execution and worker lifecycle. The
integration must have one authoritative Task attempt, explicit resource ownership,
and no duplicate execution caused by competing Core and Orca dispatchers.

## First concrete investigation areas

- Codex process contracts and worker identity: distinguish reusable evidence
  requirements from `codex-process://`-specific representation.
- Dispatch, lease, retry, fan-in, and resource cleanup: consume the actual Orca
  Task/Dispatch state without inferring exit from timeout or silence.
- Host hooks and context injection: do not assume Codex hooks protect other
  providers. State the enforcement mechanism and gaps on each supported path.
- Model and provider routing: preserve requested-versus-effective settings,
  existing subscription authorization, tool constraints, and unknown usage.
- Source and installation binding: keep experimental source and state distinct
  from the existing installation; later pins require exact source identity and
  verification, not just an experiment branch name.

No item in this list is claimed implemented by branch preparation.

## Rules that remain invariant

The user owns the goal and consequential unresolved decisions. Workers operate
within inherited authority and budget. An actual accepted owner must survive
handoffs through explicit records and a resume path. A worker cannot approve its
own outcome. Technical completion, observed user behavior, and business effect
remain distinct. Evidence refers to the exact candidate and relevant originals.

Additional providers are allowed through the user's authorized supported paths;
the current task still determines data scope, actual authentication, available
tools, spending boundaries, and the required verification. General support in a
CLI guide is not evidence that a specific account/model launch worked.

## First slice and validation

The first slice remains operating guidance, record design, and synthetic cases.
It does not change Core execution code, hooks, installed guidance, or installer
behavior. Meaningful behavior changes must follow their focused source,
contract, and end-to-end checks, including existing test-first requirements where
applicable. Relaxing Codex compatibility does not relax verification quality.

The critical failure cases are duplicate attempts after an unknown exit, changed
authority through child delegation, team-level success masking overall failure,
and claimed token savings with missing usage. Synthetic success does not prove
actual cross-provider execution or persistent bridge reliability.

The accepted cost is independent maintenance of the Orca fork, including its
Core. Selectively reuse upstream improvements where helpful; synchronization and
merge-back are optional. Simplify components that add burden without improving
the approved workflow. Returning to a shared-product strategy is a separate
user-owned decision, not the default exit from an experiment.
