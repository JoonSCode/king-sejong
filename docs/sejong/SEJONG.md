# Sejong Router Naming Contract

`Sejong` is the all-in-one broad front door that decides whether a request needs research, decision support, formal Uigwe planning, execution, verification, evidence recording, or direct action.

Uigwe/의궤 is the formal planning protocol inside Sejong, not the whole product. The public surfaces are `JangYeongsil`, `Jiphyeonjeon`, `Uigwe`, `Seungjeongwon`, `Sillok`, and `Danjong`. Compact internal ids may use `jangyeongsil`, `jiphyeonjeon`, `uigwe`, `seungjeongwon`, and `sejong-direct`, but public docs should prefer the surface names.

New user-facing invocations should use `$sejong`; the source-of-truth routing contract lives in `docs/sejong/ROUTER.md`.

## Surface Map

| Name | Use it for | Internal handle |
| --- | --- | --- |
| `Sejong` | All-in-one front door | chained or direct surface execution |
| `JangYeongsil` / `장영실` | Research, evidence gathering, experiments, and unknown discovery | `jangyeongsil` |
| `Jiphyeonjeon` / `집현전` | Debate, option comparison, recommendations, and decision support | `jiphyeonjeon` |
| `Uigwe` / `의궤` | Formal planning with `full`, `design-to-plan`, or `decompose-only` | `uigwe` |
| `Seungjeongwon` / `승정원` | Native execution and verification after a scope or bundle is approved | `seungjeongwon` |
| `Sillok` / `실록` | Evidence, scorecards, promotion reports, and decision records | evidence artifacts |
| `Danjong` / `단종` | Retired, rejected, or deposed options | rejected-alternative or archive semantics |

## Boundaries

- Do not collapse Uigwe's packet rules into Sejong.
- Do not expose old English brief names in public README surfaces.
- Do not create a `Danjong` execution lane.
- Do not duplicate Uigwe packet rules in the router.
- Route formal planning through Uigwe's `1단계: 기획 명확화`, `2단계: 설계 명확화`, and `3단계: 실행 계획화`.
- Execute clear work directly through Codex when planning is not needed.
- Route execution through Seungjeongwon after a scope or bundle is approved.
- Keep legacy handoff compatibility out of the normal public path.
- Verify execution before claiming an end-to-end Sejong request is complete.

## Examples

| User request | Router result |
| --- | --- |
| `장영실처럼 이 히스토리 조사해봐` | `JangYeongsil` |
| `집현전에서 이 선택지 토론해봐` | `Jiphyeonjeon` |
| `세종으로 이 앱 아이디어 기획부터 잡아줘` | `Uigwe` with `full` |
| `bundle 있으니 승정원으로 실행 넘겨` | `Seungjeongwon` |
| `이 선택지는 단종 처리해` | `Danjong` record inside a Jiphyeonjeon decision |

`Sillok` belongs in evidence records such as scorecards, baseline notes, promotion reports, and retained alternatives. It is not a replacement for execution or planning.
