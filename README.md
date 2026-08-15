# 대균열 — HOI4 모드

기존 모드가 "런처는 인식하는데 게임에는 아무것도 안 뜨는" 상태였기 때문에,
로딩 실패 요인을 제거한 구조로 **처음부터 다시 만든 재작성본**이다.

원본 파일이 남아 있지 않아 내용은 설명대로(대한민국 전용 포커스트리 / 이벤트 9개 /
일본 디시전 '대균열 발동' / 어드바이저 3종) 새로 작성했다.

## 설치

저장소를 받은 뒤 저장소 폴더에서 한 줄이면 된다. 기존 설치는 덮어쓴다.

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Install-Mod.ps1 -Enable
```

하는 일:

- `mod\daegyunyeol` 을 `문서\Paradox Interactive\Hearts of Iron IV\mod\` 로 복사
- **설치된 게임 버전을 읽어 `supported_version` 을 자동으로 맞춤** (기존 실패의 유력 원인)
- `mod\daegyunyeol.mod`(폴더 옆)와 `descriptor.mod`(폴더 안)를 **둘 다** 작성
- OneDrive 때문에 문서 폴더가 두 개인 경우를 감지해 `dlc_load.json` 이 있는 쪽에 설치
- `-Enable` 을 주면 `dlc_load.json` 에 등록 (백업 생성)

예전 한글 이름 모드를 같이 정리하려면 `-RemoveOld "대균열"` 을 추가한다.

## 확인 절차

1. `문서\Paradox Interactive\Hearts of Iron IV\logs\error.log` 삭제
2. 런처에서 **대균열** 체크 → [플레이]
3. **1936 새 게임**(세이브 불러오기 아님), 일본 선택
4. 디시전 탭 → `대균열` 카테고리 → **대균열 발동**
5. 콘솔(`~`)에서 `tag KOR` → 포커스트리 확인

안 되면 진단 스크립트 출력을 그대로 전달하면 된다.

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Check-Hoi4Mod.ps1 -ModName daegyunyeol | Tee-Object -FilePath report.txt
```

---

## 이전 실패와 무엇이 다른가

| 항목 | 이전 | 지금 |
|---|---|---|
| 폴더/파일명 | `대균열` (한글) | `daegyunyeol` (영문). `name="대균열"` 은 런처 표시용으로 유지 |
| `supported_version` | 불명 | 설치 시 게임 버전에서 자동 생성 |
| `.mod` 파일 | 불명 | 폴더 옆 + 폴더 안 **양쪽** 작성, `path="mod/daegyunyeol"` 슬래시 |
| 인코딩 | 불명 (메모장 기본 저장 시 CP949) | `.txt` = BOM 없는 UTF-8, `.yml` = BOM 포함 UTF-8 로 커밋 |
| 신규 국가 태그 | 불명 | 없음. 새 tag/깃발(.tga)이 없으므로 실패 지점 자체가 없다 |
| 디시전 카테고리 | 불명 | `common/decisions/categories/` 에 정의됨 |
| 어드바이저 | ideas 방식 추정 | 1.12+ `common/characters/` 방식 |

## 구조

```
mod/
├── daegyunyeol.mod                              # 폴더 옆 디스크립터 (path= 포함)
└── daegyunyeol/
    ├── descriptor.mod                           # 폴더 안 디스크립터
    ├── common/
    │   ├── national_focus/kor_daegyunyeol.txt   # 포커스 16개, country 블록으로 KOR 배정
    │   ├── decisions/jap_daegyunyeol.txt        # 일본 '대균열 발동'
    │   ├── decisions/categories/…               # 카테고리 정의
    │   ├── ideas/daegyunyeol_ideas.txt          # 지구 이념 3 + 공화국 이념 1
    │   └── characters/daegyunyeol_characters.txt# 어드바이저 3
    ├── events/daegyunyeol_events.txt            # daegyunyeol.1 ~ .9
    └── localisation/english/…_l_english.yml     # UTF-8 BOM
```

포커스트리는 도입 2 → 세 지구 각 3 → 통합/공화국/군·산업/봉인 5, 총 16개다.
"포커스트리 11개"를 트리 11그루가 아니라 하나의 트리 안 분기로 해석했다.
별도의 트리 11개가 필요했던 거라면 알려주면 분리한다.

흐름: 일본 디시전 → `daegyunyeol.1` → `release = KOR` + `load_focus_tree` →
`daegyunyeol.2` 수립 → 세 지구 접촉/흡수(`.3`~`.8`) → 삼지구 통합 뉴스(`.9`) → 대균열 봉인.

세 지구는 **새 국가가 아니라 포커스 분기 + 이념 + 이벤트**로 구현했다.
새 tag 를 만들면 `common/country_tags`, `history/countries`, 그리고 `.tga` 깃발 3종이
전부 필요해지고 그중 하나만 틀려도 로딩이 깨진다. 첫 동작 확인 뒤에 올려도 되는 부분이다.

## 알려진 주의점

- **한글 폰트.** HOI4 바닐라 폰트에는 한글 글리프가 없다. 모드는 정상 로드되는데
  포커스 이름만 빈칸/네모로 보인다면 그건 폰트 문제이지 로딩 문제가 아니다.
  한글 폰트를 제공하는 한국어 패치 모드를 같이 켜거나, 로컬라이제이션을 영문으로 바꾸면 된다.
- **GFX 이름.** 포커스 아이콘과 어드바이저 초상은 바닐라 스프라이트를 참조한다.
  버전에 따라 이름이 다르면 `error.log` 에 한 줄씩 찍히고 아이콘만 비어 보인다. 기능에는 영향이 없다.
- **이벤트 그림 없음.** 실패 지점을 줄이려고 `picture` 를 넣지 않았다. 나중에 추가하면 된다.
- **디시전 조건.** 지금은 일본이면 게임 시작부터 바로 보이도록 `available = { always = yes }` 다.
  동작 확인용이므로 원하는 조건으로 바꾸면 된다. 단 `allowed` 는 게임 시작 시 한 번만
  평가되므로 조건은 `visible` / `available` 에 넣을 것.

---

## 참고: 로딩 실패 원인 체크리스트

"문법은 맞는데 **전부** 안 나온다"는 건 대개 문법 문제가 아니다. 게임이 폴더를 아예 읽지 않은 것이다.
일부만 깨졌다면 `error.log` 에 흔적이 남고 나머지는 작동한다.

### A. 모드가 로드되지 않는 경우

1. **`dlc_load.json` 의 `enabled_mods` 에 없음.** 런처 목록에 보이는 것과 실제 활성화는 별개다.
2. **`supported_version` 이 게임 버전보다 낮음.** 런처는 목록에 계속 보여주면서 "호환 안 됨"으로
   플레이세트에서 조용히 제외한다. 증상이 정확히 이것과 일치했다.
3. **`.mod` 누락 또는 `path=` 오류.** 폴더 옆 `.mod` 와 폴더 안 `descriptor.mod` 가 **둘 다** 필요하다.
   `path` 는 슬래시(`/`). 역슬래시는 파싱 실패. `archive=` 와 `path=` 동시 사용 불가.
4. **경로에 한글.** Paradox 런처는 비ASCII 경로에서 문제를 일으킨 사례가 많다.
5. **OneDrive 리디렉션으로 문서 폴더가 두 개.** 런처가 쓰는 폴더와 게임이 읽는 폴더가 갈린다.
6. **CP949(ANSI) 인코딩.** 한글이 든 파일을 메모장 기본값으로 저장하면 이렇게 된다. 게임이 파일을 버린다.

**1분 판정:** 메인 메뉴 우하단 체크섬이 바닐라와 같으면 모드는 로드되지 않은 것이다.

### B. 로드는 되는데 안 보이는 경우

7. **KOR 은 1936년 바닐라에 존재하지 않는다.** 해방 전에는 트리를 볼 수 없다. `tag KOR` 로 확인.
8. **포커스트리에 `country` 블록 없음.** 어떤 나라에도 배정되지 않는다. 에러도 안 난다.
9. **세이브를 불러옴.** 트리 배정은 게임 시작 시점에 결정된다. 반드시 새 게임.
10. **디시전 카테고리 미정의.** 탭에 아무것도 안 뜨고 에러도 없다.
11. **`allowed = { }` 가 false.** 게임 시작 시 한 번만 평가되며, 걸리면 영원히 존재하지 않는다.
12. **이벤트에 `add_namespace` 없음.** 파일 전체가 거부된다.
13. **구형 어드바이저 포맷.** 1.12+ 는 `common/characters/` 에서 정의한다.

### error.log

`문서\Paradox Interactive\Hearts of Iron IV\logs\error.log` 하나로 대부분 끝난다.
삭제 → 실행 → 새 게임 → 종료 → 열어본다.
모드 파일 이름이 한 번도 안 나오면 A 항목 문제다.

---

이 원격 세션은 클라우드 컨테이너에서 실행되므로 PC의 게임 폴더와 로그에 직접 접근할 수 없다.
로그를 실시간으로 보면서 고치려면 PC에 Claude Code 를 설치하는 쪽이 맞다 — https://claude.com/claude-code
