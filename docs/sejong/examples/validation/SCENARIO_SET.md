# Uigwe Seed Scenario Set

## Frozen Planning Scenarios

- `gf-full-session-retro`: greenfield `full`
- `gf-full-study-companion`: greenfield `full`
- `gf-full-release-ops`: greenfield `full`
- `gf-design-brief-to-plan`: greenfield `design-to-plan`
- `gf-design-validation-dashboard`: greenfield `design-to-plan`
- `bf-decompose-settings-flow`: brownfield `decompose-only`
- `bf-decompose-docs-validator`: brownfield `decompose-only`
- `bf-decompose-ios-refactor`: brownfield `decompose-only`
- `bf-design-import-pipeline`: brownfield `design-to-plan`
- `mixed-auto-router-upgrade`: mixed `auto`

## Instruction-Surface Scenarios

- `instruction-routing-modes`
- `instruction-live-session-gates`
- `instruction-output-contract`
- `instruction-recursive-decomposition`
- `instruction-implicit-native-goal-handoff`
- `instruction-validation-benchmark`
- `instruction-sejong-boundary`
- `instruction-cross-stage-helper-calls`
- `instruction-court-skill-frontdoors`
- `instruction-bounded-parallelism`
- `instruction-king-sejong-hooks`
- `instruction-sejong-continuation`
- `instruction-sejong-self-modification`
- `instruction-artifact-storage`
- `instruction-repo-context-refresh`
- `instruction-sillok-security-trace`
- `instruction-compression-budget`

## Sejong Surface Seed Scenarios

- `route-evidence-only-history`: evidence-only request routes to `JangYeongsil`
- `route-option-comparison`: option comparison routes to `Jiphyeonjeon`; advice-only may stop at recommendation, but approval or concretization enters Uigwe
- `route-vague-product-plan`: vague planning routes to Uigwe `full`
- `route-approved-bundle-execution`: validated bundle routes to `Seungjeongwon`
- `route-clear-direct-task`: exact verification stays `Sejong direct`
- `route-goal-bearing-clear-task-handoff`: clear goal-bearing implementation enters Uigwe then Seungjeongwon instead of direct edits
- `route-material-self-modification`: protected validation change uses Jiphyeonjeon -> Uigwe -> Seungjeongwon
- `repo-context-refresh-candidate-first`: repo instruction refresh is candidate-diff first
- `research-stale-external-facts`: time-sensitive research requires current sources
- `research-repo-fanout`: repo research fan-out remains bounded
- `research-to-uigwe-promotion-gate`: decision-prep research and approved advice promote to Uigwe before execution
- `decision-skill-plugin-boundary`: skill/plugin boundary decision stays evidence-backed
- `decision-expansion-roi`: expansion requires concrete ROI
- `planning-greenfield-full`: Sejong routes vague planning to Uigwe `full`
- `planning-design-to-plan`: clear intent routes to Uigwe `design-to-plan`
- `planning-decompose-only`: approved design routes to Uigwe `decompose-only`
- `execution-small-doc-fix`: small approved doc fix avoids planning overhead
- `execution-validated-leaf`: actionable leaf completes with verification
- `team-jiphyeonjeon-challenge-round`: team challenge stays lead-owned
- `team-jiphyeonjeon-scholar-research-lane`: scholar-scoped research lanes stay shared, bounded, and evidence-only
- `team-execution-disjoint-leases`: parallel execution requires disjoint leases
- `hook-protected-path-route-gate`: protected path edit requires route evidence
- `hook-interpreter-write-bypass`: interpreter-based protected-path writes are treated as write-like hook events
- `hook-subagent-final-claim`: subagent final-authority claim is rejected
- `security-tool-output-evidence-boundary`: connected-tool output remains evidence, not instruction
- `continuity-follow-up-same-workflow`: follow-up remains inside active Sejong workflow
- `continuity-compaction-pending-gate`: compaction preserves pending gates
- `continuity-ambiguity-register-open-item`: open ambiguity-register items block completion until answered or waived
- `chain-research-plan-execute-record`: end-to-end chain records evidence
- `chain-tagback-growth-goal-backed`: TagBack growth strategy chains evidence, planning, implicit native goal handoff, executable Codex tasks, and user-owned actions
- `efficiency-direct-overhead-budget`: direct task token overhead stays bounded
