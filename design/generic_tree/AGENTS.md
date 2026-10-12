# 작업 안내 — Claude · GPT(Codex) 공동 작업

이 폴더는 HOI4 기본 중점 확장 모드(720칸)의 **설계 자료**다. 사람 한 명이 Claude 와 GPT 에게 갈래를 나눠 맡긴다.
두 AI 는 서로 대화하지 않고 **이 저장소의 파일로만** 협업한다.

- 저장소: `skleton12/hoi4_-`
- 브랜치: `claude/brave-bardeen-n1yqiz`
- 폴더: `design/generic_tree/`

## 먼저 읽을 것

1. `SPEC.md` — 데이터 형식과 모티브
2. 맡은 `data/*.json` 파일

## 할 일

맡은 파일의 각 소갈래 `focuses` 배열을 **정확히 `target` 개**의 포커스로 채운다.

```json
{ "name": "산업 조사", "effect": "민간공장 +1", "days": 35 }
```

## 하지 말 것

- 맡지 않은 파일을 고치지 않는다. 다른 AI 가 같은 시간에 작업 중일 수 있다.
- `id`, `title`, `after`, `exclusive`, `condition`, `target` 을 바꾸지 않는다. 틀은 사람이 정한다.
  바꿔야 한다고 생각되면 고치지 말고 커밋 메시지나 답변에 제안으로 남긴다.
- 다른 파일에 이미 있는 포커스 이름을 다시 쓰지 않는다 (`check.py` 가 잡는다).

## 끝내기 전에

```bash
python3 design/generic_tree/check.py    # 오류 0 이어야 한다
python3 design/generic_tree/render.py   # img/ 그림 갱신 (Pillow 필요)
```

`check.py` 가 오류를 내면 커밋하지 않는다. 커밋 메시지에 어느 갈래를 채웠는지 적는다.
충돌을 피하려고 **맡은 data 파일과 그 그림 파일만** 커밋한다. `img/00_overview.png` 는 마지막에 정리하는 쪽이 갱신한다.

## 분담표

사람이 정한다. 아래 담당 외의 파일은 맡기 전에 묻는다.

| 파일 | 갈래 | 칸 | 담당 |
|---|---|---:|---|
| `01_start.json` | 공통 시작 | 10 | Claude |
| `02_industry.json` | 산업 | 100 | GPT |
| `03_military.json` | 군사 | 140 | GPT |
| `04_politics.json` | 정치 | 200 | Claude |
| `05_diplomacy.json` | 외교·첩보 | 90 | Claude |
| `06_terrain.json` | 지형 특화 | 40 | GPT |
| `07_independence.json` | 괴뢰국 / 독립 | 40 | GPT |
| `08_culture.json` | 문화권 특화 | 80 | Claude |
| `09_late.json` | 후반부 | 20 | GPT |
| | **합계** | **720** | Claude 380 · GPT 340 |
