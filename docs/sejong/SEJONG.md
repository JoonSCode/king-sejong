# Sejong Router Naming Contract

`Sejong` is the router: the broad front door that decides whether a request needs research, decision support, formal Uigwe planning, executor handoff, evidence recording, or direct action.

This is a naming layer only. Uigwe/의궤 is the formal planning protocol. The router's canonical machine lane ids are `research-brief`, `decision-brief`, `uigwe-plan`, `executor-handoff`, and `direct-action`.

New user-facing invocations should use `$sejong`; the source-of-truth routing contract lives in `docs/sejong/ROUTER.md`.

## Alias Map

| Name | Use it for | Canonical surface |
| --- | --- | --- |
| `Sejong` | The router/front door | existing router lane selection |
| `JangYeongsil` | Research, evidence gathering, experiments, and unknown discovery | `research-brief` |
| `Jiphyeonjeon` | Debate, option comparison, recommendations, and decision support | `decision-brief` |
| `Seungjeongwon` | Execution handoff after a validated Uigwe bundle exists | `executor-handoff` via RalphExecutor |
| `Sillok` | Evidence, scorecards, promotion reports, and decision records | validation and promotion artifacts |
| `Danjong` | Retired, rejected, or deposed options | rejected-alternative or archive semantics only |

## Boundaries

- Do not collapse Uigwe into Sejong.
- Do not replace `research-brief`, `decision-brief`, `uigwe-plan`, `executor-handoff`, or `direct-action`.
- Do not create a `Danjong` active lane.
- Do not duplicate Uigwe packet rules in the router.
- Route formal planning through Uigwe's `1단계: 기획 명확화`, `2단계: 설계 명확화`, and `3단계: 실행 계획화`.
- Route execution through RalphExecutor only after a validated bundle exists.

## Examples

| User request | Router result |
| --- | --- |
| `장영실처럼 이 히스토리 조사해봐` | `research-brief` |
| `집현전에서 이 선택지 토론해봐` | `decision-brief` |
| `세종으로 이 앱 아이디어 기획부터 잡아줘` | `uigwe-plan` with `full` |
| `bundle 있으니 승정원으로 실행 넘겨` | `executor-handoff` through RalphExecutor |
| `이 선택지는 단종 처리해` | `decision-brief` rejected or retired option semantics |

`Sillok` belongs in evidence records such as scorecards, baseline notes, promotion reports, and retained alternatives. It is not a replacement for the router lane model.
