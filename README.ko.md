![대왕 세종 배너](docs/sejong/assets/king-sejong-banner.png)

# 대왕 세종

[English](README.md)

이 문서는 조선 말투로 적은 한글 안내서이옵니다. 말투는 옛스럽게 하였으나, 명령과 경로는 모두 지금 쓰는 참된 것이니 그대로 행하시면 되옵니다.

King Sejong은 **Codex**가 "분석"에서 멈추지 않고, 사용자가 바란 결과까지 가도록 길목과 검증을 더하는 skill 꾸러미이옵니다.

이는 실제 저장소에서 Codex를 쓰는 maintainer를 위하여 만들었사옵니다. Pull request 검토, issue triage, release 준비, 설치 검증, 보안 guardrail, 문서 일관성 점검처럼 agent가 고치기 전에 증거를 모아야 하는 open-source 유지보수 일을 돕고자 함이옵니다.

한 에이전트에게 `$sejong`이라는 넓은 정문을 내려, 조사하고, 의논하여 정하고, 의궤로 기획하고, 승정원으로 실행하며, 검증하고, 실록처럼 증거를 남기게 하려는 물건이옵니다. 한 번 `$sejong`을 부른 뒤에는, 사용자가 세종을 그만 쓰라 하거나 다른 비-Sejong workflow로 옮기라 하기 전까지 이어지는 답변도 Sejong 맥락으로 보옵니다.

일이 흐리고, 선택지가 여럿이고, 여러 파일과 검증을 건드리며, 끝났다는 증거가 필요한 때에 쓰기 좋사옵니다. 이는 새로운 runtime이 아니옵니다. Codex가 model loop, tool, shell, file, approval을 맡고, King Sejong은 길목 결정, gate, handoff, 검증 모양, 증거 기록을 맡사옵니다.

## 어찌 쓸 때 빛나나이까

- 넓은 부탁을 무조건 한 기획 양식에 넣지 않고, 지금 필요한 길목으로 보냅니다.
- 조사, 논의, 기획, 실행, 검증을 이어지는 맥락 안에 묶어 둡니다.
- 오래 남길 기획 꾸러미가 값어치 있을 때에만 의궤를 엽니다.
- 허락된 일은 승정원으로 넘겨 실행, 검증, 재시도, 증거 보고까지 잇습니다.
- 큰 병렬 작업이나 workflow 실험은 worker 동의가 아니라 discipline gate, outcome check, workflow-run 증거로 살핍니다.
- 조사, 기획, 실행 중 기록, 증거 산출물은 기본으로 대상 저장소 밖에 두고, 사용자가 명시할 때만 git에 남기며, 끝난 뒤에는 정책대로 작게 접고 정리합니다.
- 저장소마다 들이거나 `${CODEX_HOME:-~/.codex}/skills`에 한 번 들여 여러 workspace에서 함께 쓸 수 있사옵니다.

## 어느 때 부르나이까

| 일이 필요로 하는 것 | 먼저 부를 말 | 이어지는 일 |
| --- | --- | --- |
| 결정 전 증거 | `$sejong` 또는 `$jangyeongsil` | 아는 것, 추정, 모르는 것, 다음 결정을 가릅니다. |
| 선택지 사이의 권고 | `$sejong` 또는 `$jiphyeonjeon` | 장단점, 버린 길, 위험, 다음 길목을 종합합니다. |
| 오래 남길 기획 | `$sejong` 또는 `$uigwe` | 의궤 산출물과 성공 기준에 묶인 handoff leaf를 만듭니다. |
| 증거 있는 구현 | `$sejong` 또는 `$seungjeongwon` | 범위를 쪼개 실행하고, 검증하고, 증거를 아룁니다. |
| 큰 병렬 workflow 실험 | `$sejong` | worker 산출물은 증거로만 쓰고, workflow-run과 outcome 증거로 유지할 값을 따집니다. |
| 작고 분명한 일 | `$sejong` | 곧장 처리하고 끝낸 일과 검증을 보고합니다. |

기본으로 Sejong은 조사, 기획, 실행 중 기록과 증거를 `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}` 아래 대상 저장소 밖에 두옵니다. 끝난 실행은 `run-summary.json`과 실록 증거로 작게 접은 뒤, 원자료와 임시 파일을 dry-run 먼저 보이는 정리 도구로 치울 수 있사옵니다.

## Maintainer 일을 어찌 돕나이까

King Sejong은 아직 이른 public project이오나, 보여주기용 agent loop가 아니라 되풀이되는 maintainer 일을 위하여 짜였사옵니다.

- 고치기 전에 증거, rationale, verification 기대치를 두고 change를 검토하옵니다.
- Issue를 조사, 결정, 기획, 실행, 보류 길로 가르옵니다.
- 승인된 design을 Seungjeongwon 검증이 가능한 executable leaf로 풀어내옵니다.
- Release 전에 install surface, hook, schema, example, instruction contract를 검증하옵니다.
- Maintainer가 명하지 않는 한 runtime artifact를 대상 저장소 밖에 두옵니다.

자세한 예시는 [OSS maintainer workflows](docs/sejong/OSS_MAINTAINER_WORKFLOWS.md)를 보시옵소서.

## 이름을 어찌 쓰리이까

이름은 **Sejong**이라 쓰시옵소서.

`SeJong`이라 쓰지 마옵소서. 통용되는 표기는 `King Sejong`의 `Sejong`이옵니다.

- 사람에게 보이는 이름: `King Sejong`
- skill 이름: `sejong`
- 부르는 말: `$sejong`
- 저장소 이름: `king-sejong`

## 속히 들이는 법

지금 머무른 저장소에 들이고자 하면 이리 하시옵소서.

```bash
tmp=$(mktemp -d)
git clone --depth 1 https://github.com/JoonSCode/king-sejong.git "$tmp/king-sejong"
bash "$tmp/king-sejong/scripts/install-sejong.sh" "$PWD"
bash "$tmp/king-sejong/scripts/install-sejong.sh" --verify "$PWD"
rm -rf "$tmp"
```

어느 저장소에서나 쓰는 Codex 사용자 범위에 들이고자 하면 이리 하시옵소서.

```bash
tmp=$(mktemp -d)
git clone --depth 1 https://github.com/JoonSCode/king-sejong.git "$tmp/king-sejong"
bash "$tmp/king-sejong/scripts/install-sejong.sh" --scope user
bash "$tmp/king-sejong/scripts/install-sejong.sh" --scope user --verify
rm -rf "$tmp"
```

사용자 범위 설치는 기본으로 `${CODEX_HOME:-~/.codex}/AGENTS.md`에 킹 세종 안내 블록도 쓰옵니다. 이로써 어느 Codex 작업 공간에서나 리서치, 분석, 토론, 기획, 실행, 검증의 상시 규율로 킹 세종을 떠올리게 하옵니다. 스킬, 훅, 활성 맥락만 들이고자 하면 `--codex-guidance none`을 쓰시옵소서.

들인 뒤에는 이처럼 부르시면 되옵니다.

```text
$sejong 이 버그를 조사하고, 가장 안전한 고침을 고르고, 구현한 뒤 검증해줘
$sejong 이 구현 선택지들을 비교하고, 고른 길을 실행 가능한 일로 풀어줘
$uigwe design-to-plan 이 승인된 기능 개요를 실행 계획으로 세워줘
```

에이전트에게 맡기고자 하면 이리 명하시면 되옵니다.

```text
Install King Sejong into this repository from https://github.com/JoonSCode/king-sejong.
Run scripts/install-sejong.sh against the current repo, then verify the install with --verify.
```

## 손수 들이는 법

먼저 이 저장소를 받아오시옵소서.

```bash
git clone https://github.com/JoonSCode/king-sejong.git
cd king-sejong
bash scripts/install-sejong.sh /path/to/your-repo
```

이미 든 것을 갈아 넣으려면 이리 하시옵소서.

```bash
bash scripts/install-sejong.sh --force /path/to/your-repo
```

제대로 들었는지만 살피려면 이리 하시옵소서.

```bash
bash scripts/install-sejong.sh --verify /path/to/your-repo
```

킹 세종 원본 체크아웃에 원격 업데이트가 있는지 살피려면 이리 하시옵소서.

```bash
bash scripts/install-sejong.sh --check-updates
```

킹 세종 원본 체크아웃을 fast-forward로 당긴 뒤 Codex 사용자 범위 설치까지 갈아 넣으려면 이리 하시옵소서.

```bash
bash scripts/install-sejong.sh --auto-update --scope user
```

`--auto-update`는 원본 체크아웃에 작업 중 변경이 있거나 브랜치가 갈라졌으면 멈추며, `git pull --ff-only` 뒤 선택된 관리 설치 경로를 force 의미로 새로 쓰고 평소 검증을 거치옵니다. 킹 세종 훅은 일반 세션 중 조용히 자기 자신을 자동 업데이트하지 않사옵니다.

Codex 사용자 범위에 들이고자 하면 이리 하시옵소서.

```bash
bash scripts/install-sejong.sh --scope user
bash scripts/install-sejong.sh --scope user --verify
```

Codex 집이 `~/.codex`가 아니면 먼저 `CODEX_HOME`을 정하시옵소서.

관리되는 `${CODEX_HOME:-~/.codex}/AGENTS.md` 안내 블록을 건너뛰려면 `bash scripts/install-sejong.sh --scope user --codex-guidance none`을 쓰시옵소서.

저장소 범위에서 설치관이 옮기는 길은 이러하옵니다.

- `.agents/skills/sejong/`
- `.agents/skills/jangyeongsil/`
- `.agents/skills/jiphyeonjeon/`
- `.agents/skills/uigwe/`
- `.agents/skills/seungjeongwon/`
- `.agents/skills/why-gate/`
- `docs/sejong/`

사용자 범위에서는 `${CODEX_HOME:-~/.codex}/skills` 아래 이 길을 옮기옵니다.

- `sejong/`
- `jangyeongsil/`
- `jiphyeonjeon/`
- `uigwe/`
- `seungjeongwon/`
- `why-gate/`

사용자 범위에서는 함께 쓰는 Sejong 문서를 `skills/sejong/docs/` 아래 두고, 설치된 skill 파일들이 그 문서를 읽도록 길을 고쳐 두옵니다.
또한 Codex plugin 어댑터를 `${CODEX_HOME:-~/.codex}/plugins/cache/king-sejong-local/king-sejong/0.1.0/` 아래 두고, `${CODEX_HOME:-~/.codex}/config.toml`의 King Sejong plugin 블록으로 켜 두옵니다.
이 plugin hook이 사용자 범위의 기본 hook 길이옵니다. 사용자 범위 재설치는 예전의 직접 hook 블록을 기본으로 걷어 내며, `--legacy-direct-hooks`는 plugin hook을 쓸 수 없을 때만 명시하여 쓰는 물림 길이옵니다.

각 범위의 길은 한 몸이니 흩지 마옵소서. Skill 문서는 짧게 두고, 자세한 법도와 문서는 함께 설치된 Sejong 문서에서 불러 보게 하였나이다. Plugin 어댑터는 hook metadata만 맡으므로 사람이 부르는 skill은 `$sejong` 하나로 두옵니다.

## Runtime 산출물 정리

외부 실행 산출물은 `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/runs` 아래에 남사옵니다. 저장소에 git-tracked 파일을 만들지 않고 이 실행 디렉터리들을 살피고, 끝난 run을 접고, 오래된 것을 치우려면 이 도구를 쓰시옵소서.

```bash
python3 docs/sejong/scripts/sejong_cleanup.py report
python3 docs/sejong/scripts/sejong_cleanup.py finalize-run ~/.codex/sejong/runs/<repo-id>/<run-id> --status success
python3 docs/sejong/scripts/sejong_cleanup.py prune-runs
```

정리는 보수적으로 움직이옵니다. 기본으로는 무엇을 지울지 보고만 하며, 실제 삭제는 `--execute`를 붙여야 하옵니다. Sejong runs root 밖의 길은 거절하고, active run이나 `promoted-artifacts.json` 또는 `.sejong-promoted`가 있는 run은 지우지 않사옵니다.

## 어느 곳에서 쓰나이까

King Sejong은 Codex skill과 얇은 Codex plugin 어댑터로 나누는 물건이옵니다. npm, Python 패키지, 홀로 서는 CLI가 아니옵니다.

| 자리 | 됨됨이 | 비고 |
| --- | --- | --- |
| repo-local `.agents/skills`를 읽는 Codex | 받듦 | 저장소마다 다른 법도에 맞출 때 으뜸이옵니다. |
| 사용자 범위 `${CODEX_HOME:-~/.codex}/skills`와 local plugin cache를 읽는 Codex | 받듦 | `$sejong`, `$jangyeongsil`, `$jiphyeonjeon`, `$uigwe`, `$seungjeongwon`을 여러 저장소에서 함께 쓰고, plugin hook metadata도 함께 쓰고자 할 때 쓰시옵소서. |
| `.agents/skills`와 repo 문서를 읽는 Codex식 환경 | 가히 될 수 있음 | 같은 길을 설치하고 그 자리에서 검증하옵소서. |
| OpenCode, Claude Code, Gemini CLI, Cursor | 아직 꾸러미 아님 | 각자의 plugin/extension 법도에 맞춘 어댑터가 따로 필요하옵니다. |

## Codex와 실행

이 꾸러미는 Codex식 skill을 위하여 만들었사옵니다.

- 저장소 범위에서는 Codex가 `$sejong`에 `.agents/skills/sejong/SKILL.md`를 읽사옵니다.
- 사용자 범위에서는 Codex가 `$sejong`에 `${CODEX_HOME:-~/.codex}/skills/sejong/SKILL.md`를 읽사옵니다.
- `king-sejong` plugin은 hook metadata만 보이게 하며, plugin 쪽에 두 번째 `$sejong` skill을 만들지 않사옵니다.
- `$jangyeongsil`, `$jiphyeonjeon`, `$uigwe`, `$seungjeongwon`도 같은 범위 안에 함께 들사옵니다.
- 일이 분명하면 Sejong이 의궤를 열지 않고 곧장 실행하옵니다.
- 실행 뒤에는 검증과 증거를 남기는 계약을 문서로 두었사옵니다.

실행은 Sejong의 직분 안에 있사오며, 이 꾸러미 안의 실행관은 이러하옵니다.

- `Seungjeongwon` / `승정원`

승정원은 King Sejong의 본래 실행 고리이옵니다. 허락된 범위나 검증된 의궤 꾸러미를 실행하고, 결과를 검증하며, 증거를 아뢰옵니다.

## 일의 차례

사용자가 결과를 원하면 Sejong은 이 길을 끝까지 밟을 수 있사옵니다.

```text
장영실 조사 -> 집현전 논의 -> 의궤 기획 -> 승정원 실행 -> 검증 -> 실록 증거
```

다만 증거가 모자라거나, 사용자의 재가가 필요하거나, 선택이 갈리는 곳에서는 멈추어 묻사옵니다.

## 부르는 법

무슨 길로 가야 할지 아직 분명치 않으면 Sejong을 부르시옵소서.

```text
$sejong 이 일을 조사하고 의궤로 넘길지 논의해줘
$sejong 이 선택지들을 집현전에서 논의하고 다음 길목을 정해줘
$sejong 승인된 설계를 실행 가능한 일로 풀어줘
```

이미 의궤 기획이 필요함을 아시면 곧장 Uigwe를 부르시옵소서.

```text
$uigwe full 비동기 면접 연습용 브라우저 MVP를 기획해줘
$uigwe design-to-plan 이 기능 개요를 실행 계획으로 세워줘
$uigwe decompose-only docs/specs/approved-design.md
```

## 길목

| 길목 | 언제 쓰나이까 | 무엇을 내나이까 |
| --- | --- | --- |
| `장영실` / `JangYeongsil` | 사실, 내력, 증거가 아직 흐릴 때 | 아는 것, 추정, 모르는 것, 다음 결정 |
| `집현전` / `Jiphyeonjeon` | 여러 길을 놓고 논의하여 방향을 정해야 할 때 | 찬반, 버린 길, 권하는 길, 위험 |
| `의궤` / `Uigwe` | 오래 남길 기획 꾸러미가 필요할 때 | 의궤 packet, `spec.md`, `rationale.md`, `goal-tree.json` |
| `승정원` / `Seungjeongwon` | 검증된 범위나 꾸러미를 실행해야 할 때 | 실행, 검증, 보고 |
| `실록` / `Sillok` | 증거를 남겨야 할 때 | scorecard, 승격 기록, 결정의 내력 |
| `단종` / `Danjong` | 한 선택지를 물리거나 폐해야 할 때 | 버린 까닭의 기록 |
| `세종 직행` | 일이 이미 분명하여 곧장 해도 될 때 | 끝낸 일과 검증 증거 |

조정의 이름은 사람에게 보이는 별칭이옵니다.

- `JangYeongsil` / `장영실` -> 조사
- `Jiphyeonjeon` / `집현전` -> 논의와 결정 보좌
- `Uigwe` / `의궤` -> 기획
- `Seungjeongwon` / `승정원` -> 실행
- `Sillok` / `실록` -> 증거 기록
- `Danjong` / `단종` -> 버리거나 물린 선택지

증거가 모자라면 장영실이 먼저 살피고, 재료는 있으나 선택이 어렵다면 집현전에서 논의하며, 방향이 정해졌으면 의궤로 기획 문서를 세우옵니다.

집현전은 모든 길에 반드시 거치는 의식이 아니옵니다. 증거를 살핀 뒤에도 참으로 갈림길이 남았을 때 짧게 의논하는 자리로 쓰고, 길이 이미 분명하면 곧장 의궤나 승정원이나 세종 직행으로 나아가옵니다.

bounded worker는 독립된 조사 갈래, 선택지 검토, 나뉜 실행 범위, 검증 갈래가 있을 때 일을 빠르게 나누는 방편이옵니다. Codex native subagent도 한 가지 backend이고, `$team`으로 tmux pane에 띄운 Codex CLI나 Claude CLI worker도 또 다른 backend이옵니다. 반드시 부르는 절차는 아니며, 마지막 종합과 길목 결정과 검증은 으뜸 Sejong 에이전트가 맡사옵니다.

큰 일에서는 장영실이 증거 갈래를 나누어 살피고, 집현전이 찬성ㆍ반대ㆍ전문가ㆍ실행자ㆍ위험 검토의 짧은 상소를 병렬로 받으며, 의궤는 재가 전에는 준비 살핌만 하옵니다. 중대한 집현전 논의에서는 `$team` worker를 `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/team/<run-id>/` 아래 mailbox/state 파일로 조율하여 짧은 반박 회차를 둘 수 있사오나, 끝없는 대화방이나 투표로 만들지는 않사옵니다. 여러 worker가 뜻을 같이했다 하여 그것이 곧 증거, 재가, 검증이 되지는 않사옵니다.

`.codex/prompts/{role}.md` 파일은 반드시 필요하지 않사옵니다. King Sejong은 Codex의 본래 role prompt를 먼저 쓰고, 대상 저장소가 그 파일을 마련한 경우에만 repo-local 덧입힘으로 읽사옵니다.

저장소의 `AGENTS.md`를 처음 세우거나 새로 고칠 때에도 Sejong을 쓸 수 있사오나, 이는 후보 diff를 먼저 내고 명시 재가 뒤에만 tracked instruction 파일을 고치는 법도이옵니다. 조용히 늘 도는 자동 갱신관이 아니옵니다.

King Sejong 자신을 고칠 때에는 단순한 오자, 링크, 서식 고침이 아닌 한 온전한 세종 길을 따르옵니다. 길목, 의궤 기획, 승정원 실행, 설치관, 검증, 산출물 저장 법도가 바뀌는 일은 집현전에서 정하고, 의궤로 실행 일을 나누며, 승정원으로 고치고 검증하옵니다.

## 이름을 어찌 쓰리이까

이름은 **Sejong**이라 쓰시옵소서.

`SeJong`이라 쓰지 마옵소서. 통용되는 표기는 `King Sejong`의 `Sejong`이옵니다.

- 사람에게 보이는 이름: `King Sejong`
- skill 이름: `sejong`
- 부르는 말: `$sejong`
- 저장소 이름: `king-sejong`

## 다음 길

- 온 문서의 차례가 필요하면 [Sejong 문서 차례](docs/sejong/README.md)에서 시작하시옵소서.
- 설치하거나, 관리하거나, King Sejong 자체를 고칠 때에만 [runtime contract](docs/sejong/RUNTIME_CONTRACT.md)를 살피시옵소서.
- 설치관이나 관리 경로를 고친 뒤에는 `bash scripts/install-sejong.sh --verify .`로 검증하시옵소서.

## 허락 문서

MIT이옵니다. 개인, 내부, 공개 agent workflow 어디에든 가볍게 들여 쓰기 좋게 하였사옵니다.
