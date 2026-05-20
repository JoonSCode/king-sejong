![대왕 세종 배너](docs/sejong/assets/king-sejong-banner.png)

# 대왕 세종

[English](README.md)

이 문서는 조선 말투로 적은 한글 안내서이옵니다. 말투는 옛스럽게 하였으나, 명령과 경로는 모두 지금 쓰는 참된 것이니 그대로 행하시면 되옵니다.

King Sejong은 **Codex**와 Codex와 같은 repo-local skill 환경에 들이는 기술 꾸러미이옵니다.

한 에이전트에게 `$sejong`이라는 넓은 정문을 내려, 조사하고, 의논하여 정하고, 의궤로 기획하고, 승정원으로 실행하며, 검증하고, 실록처럼 증거를 남기게 하려는 물건이옵니다.

이는 홀로 서는 CLI나 Python 패키지가 아니옵니다. 쓰고자 하는 저장소에 `.agents/skills`와 `docs/sejong` 문서를 함께 옮겨, Codex가 그 skill을 읽게 하는 방식이옵니다.

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

설치관이 옮기는 길은 이러하옵니다.

- `.agents/skills/sejong/`
- `.agents/skills/uigwe/`
- `.agents/skills/seungjeongwon/`
- `docs/sejong/`

이 네 길은 한 몸이니 흩지 마옵소서. Skill 문서는 짧게 두고, 자세한 법도와 문서는 `docs/sejong`에서 불러 보게 하였나이다.

## 어느 곳에서 쓰나이까

King Sejong은 Codex repo-local skill로 나누는 물건이옵니다. npm, Python 패키지, 홀로 서는 CLI가 아니옵니다.

| 자리 | 됨됨이 | 비고 |
| --- | --- | --- |
| repo-local `.agents/skills`를 읽는 Codex | 받듦 | 으뜸 대상이옵니다. |
| `.agents/skills`와 repo 문서를 읽는 Codex식 환경 | 가히 될 수 있음 | 같은 길을 설치하고 그 자리에서 검증하옵소서. |
| OpenCode, Claude Code, Gemini CLI, Cursor | 아직 꾸러미 아님 | 각자의 plugin/extension 법도에 맞춘 어댑터가 따로 필요하옵니다. |

## Codex와 실행

이 꾸러미는 Codex식 repo-local skill을 위하여 만들었사옵니다.

- Codex는 `$sejong`에 `.agents/skills/sejong/SKILL.md`를 읽사옵니다.
- Codex는 `$uigwe`에 `.agents/skills/uigwe/SKILL.md`를 읽사옵니다.
- Codex는 `$seungjeongwon`에 `.agents/skills/seungjeongwon/SKILL.md`를 읽사옵니다.
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

## 더 살필 문서

- [Sejong router contract](docs/sejong/ROUTER.md)
- [Uigwe protocol](docs/sejong/PROTOCOL.md)
- [Uigwe wrapper](docs/sejong/WRAPPER.md)
- [Seungjeongwon executor](docs/sejong/SEUNGJEONGWON_EXECUTOR.md)
- [Bundle validator](docs/sejong/BUNDLE_VALIDATOR.md)

## 허락 문서

MIT이옵니다. 개인, 내부, 공개 agent workflow 어디에든 가볍게 들여 쓰기 좋게 하였사옵니다.
