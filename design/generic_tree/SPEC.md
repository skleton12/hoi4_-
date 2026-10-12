# 기본 중점 확장 — 구성 데이터 규격

HOI4 기본(제네릭) 포커스 트리를 648칸으로 새로 짜는 **설계 단계** 자료다. 게임 코드가 아니라 구성안이다.
`data/*.json` 을 `check.py` 가 검사하고 `render.py` 가 읽어 `img/` 에 트리 그림을 만든다.
작업 분담과 절차는 `AGENTS.md` 에 있다.

## 모티브

- **Very good generic focus policy reset** (640칸): 이념마다 역사 모델로 갈래를 나눔
  (공산: 스탈린·트로츠키·부하린·아나키스트·자주 / 민주: 사민·자유·기독교 민주 /
  파시즘: 프랑코형·국가 조합주의·국가사회주의 / 비동맹: 군사 독재·대통령 독재·왕정 복고), 발칸 전용 트리
- **Better Generic Focus Tree**: 비밀 예산(정예 부대·밀수·무허가 채굴), 주 개수 비례 효과
- **Improved Generic Focus Tree**: 의용군 파견, 전쟁 특수, 도시화↔농촌화, 육·해·공 우선주의
- **Minor Nations Reborn**: 괴뢰국 갈래, 지역별 자리 갈래
- 바닐라 소국 트리: 스위스 국가 요새, 핀란드 만네르헤임 선, 에티오피아 항전, 멕시코 석유 국유화,
  소협상·발트 협상, 영연방 자치령 독립, 헝가리 왕정 복고

## 파일 형식

```json
{
  "branch": "industry",
  "title": "산업",
  "groups": [
    {
      "id": "ind_base",
      "title": "기초 산업",
      "after": null,
      "exclusive": null,
      "condition": null,
      "target": 10,
      "focuses": [
        { "name": "산업 조사", "effect": "민간공장 +1", "days": 35 }
      ]
    }
  ]
}
```

- `groups`: 한 갈래 안의 소갈래. 각 소갈래의 `focuses` 는 **위에서 아래로 이어지는 사슬**이다.
- `after`: 이 소갈래가 이어 붙는 소갈래의 `id` (그 소갈래의 마지막 칸 다음에 온다). `null` 이면 갈래 뿌리에 붙는다.
  같은 파일 안의 id 만 쓴다. **목록**(`["a", "b"]`)이면 "그중 하나만 끝내도 된다"는 합류다.
  목록의 소갈래들은 같은 부모를 가져야 한다 (예: 합법 집권 ↔ 무장 봉기 → 정부).
- `exclusive`: 서로 상호배타인 소갈래끼리 같은 문자열 태그를 준다. 아니면 `null`.
- `condition`: 이 소갈래가 보이는 조건(한국어 짧게, 예 "해안 주 보유"). 없으면 `null`.
- `target`: 이 소갈래의 목표 칸 수. **바꾸지 않는다.** `focuses` 는 비어 있거나(미작성) 정확히 `target` 개여야 한다.
- `name`: 한국어 포커스 이름, 2~12자.
- `effect`: 한국어 효과 요약, 30자 이내. HOI4 에 실제 있는 종류의 효과로 (공장, 연구 보너스, 국가 정신, 정치력,
  안정도, 전쟁 지원, 징집 인력, 교리 비용, 장비 생산, 동맹·보장, 전쟁 목표, 고문 영입, 디시전 해금 등).
- `days`: 35 또는 70. 대부분 35, 큰 칸만 70.

## 설계 원칙

- **넓고 얕게.** 소갈래는 최대 5칸(`check.py` 가 막는다), 트리 전체 깊이는 10줄 안팎.
- **합칠 수 있으면 합친다.** 35일 포커스로도 한 판에 90칸 남짓밖에 못 끝낸다. "조사"·"검토"처럼 효과가 작은
  준비 칸, 효과가 비슷한 칸은 한 칸으로 묶는다. 참고 규모: 바닐라 56 · Minor Nations Reborn 160 ·
  Generic Focus Tree Rework 223 · Very good generic focus policy reset 640.
- 문화권 갈래는 따로 두지 않는다. 지역색은 외교의 「지역 맹주」 아래 조건부 소갈래로 둔다.

이름은 소갈래 안에서 이야기가 흐르게, 전체에서 중복 없이. 과장된 판타지 없이 1936~1945 역사 분위기.

## 모드

사용자 지정 대상 빌드: **1.19.3.0.c01a (5632)**. 두 디스크립터의 호환 표기는
`supported_version="1.19.3.*"`이며, 설치 스크립트도 이 범위를 유지한다.

설계가 들어갈 모드는 `mod/gibon_jungjeom` 이다. 런처에 보이는 이름은 **「기본 중점 변경 모드」**,
폴더·파일 이름은 영문이다(한글 폴더 이름은 런처에서 로딩 실패의 원인이 된다).
설치: `powershell -ExecutionPolicy Bypass -File .\tools\Install-Mod.ps1 -ModName gibon_jungjeom -Enable`
모드 파일 만들기: `python3 design/generic_tree/build_mod.py` → `generic.txt` 와 로컬라이제이션을 다시 쓴다.
검사: `python3 tools/validate.py mod/gibon_jungjeom`. 조건 문구를 새로 쓰면 `build_mod.py` 의 `CONDITIONS` 에 트리거를 추가해야 한다.
