# 모드 0개 로드 — 조사 정리

대상: HOI4 1.19.3.0 (사용자 PC). 증상: 모드를 켜고 실행해도 `game.log` 에 `Active Mod Count: 0`.
대균열(`daegyunyeol`)과 기본 중점 변경 모드(`gibon_jungjeom` / PC 설치명 `new_focus`) 모두 게임에서
로드가 확인된 적이 없다. 두 모드에 공통인 **환경·런처 쪽 원인**을 먼저 의심한다.

## 1. 게임이 모드를 고르는 과정 (HOI4 위키 「Modding」 기준)

```
런처 [플레이]
  └─ 활성 플레이세트(launcher-v2.sqlite) → dlc_load.json 을 다시 쓴다
hoi4.exe
  ├─ 사용자 폴더 = 게임 설치 폴더의 launcher-settings.json 의 gameDataPath
  ├─ <사용자 폴더>\dlc_load.json 의 enabled_mods ("mod/xxx.mod") 를 읽는다
  ├─ <사용자 폴더>\mod\xxx.mod 의 path 로 모드 폴더를 찾는다
  └─ 같은 name 의 모드가 둘이면 먼저 읽힌 쪽만 쓴다
```

위키가 직접 적은 규칙:
- 사용자 폴더 위치는 **`launcher-settings.json` 의 `gameDataPath`** 로 정해진다 (`userdir.txt` 가 아니다).
- 사용자 폴더 경로에 ASCII 가 아닌 글자가 있으면 `error.log` 를 못 열고 그곳의 모드가 로드되지 않을 수 있다.
- `path` 는 슬래시만, ASCII 만. `.mod` 파일 이름에 공백 불가.
- 모드 `name` 은 고유해야 한다. 같으면 먼저 읽힌 쪽만 파일이 잡힌다.
- `supported_version` 은 런처의 "구버전" 표시용이다(로드 자체를 막는다는 기술은 없다).
- 런처는 실행 직전에 `dlc_load.json` 을 다시 쓴다. 손으로 고쳐서 런처 없이 켤 수도 있다.
- 로컬 모드는 기본 플레이세트에 자동으로 들어가지 않는다(워크숍·Paradox Mods 는 자동).

## 2. 지금까지 확인한 것 (GPT, 사용자 PC)

| 항목 | 결과 |
|---|---|
| 실행 경로 | 정상 Steam 경로, 모드 끄는 실행 옵션 없음 |
| `dlc_load.json` | BOM 없음, `new_focus` 항목 있음, 실행 29초 전(22:01:12) 저장 |
| `userdir.txt` | 없음 |
| 경로의 한글 · `.mod.txt` · `path` 오류 · UTF-16 | 모두 해당 없음 |
| Windows 접근 차단 기록 | 없음 |
| 결과 | 22:01:41 `Active Mod Count: 0` |

## 3. 아직 확인하지 않은 것 (우선순위 순)

| # | 확인 | 왜 | 방법 |
|---|---|---|---|
| A | **`launcher-settings.json` 의 `gameDataPath`** | 게임이 읽는 `dlc_load.json` 의 위치를 정하는 실제 설정. 런처와 게임이 서로 다른 폴더를 쓰면 지금 증상과 같다 | 게임 설치 폴더의 파일을 열어 값 확인. `%USER_DOCUMENTS%` 가 OneDrive 문서로 풀리는지. `Check-Hoi4Mod.ps1` 이 이제 자동 비교한다 |
| B | **`Active Mod Count` 가 찍힌 로그의 폴더 = `dlc_load.json` 폴더인가** | 게임은 자기 사용자 폴더에 로그를 쓴다. 두 폴더가 다르면 A 가 원인 | 두 파일의 전체 경로 비교 |
| C | **같은 `name` 의 `.mod` 가 여럿** | 시험판 `gibon_jungjeom.mod` 와 `new_focus.mod` 가 둘 다 `name="기본 중점 변경 모드"` 일 수 있다 | `mod\*.mod` 의 `name` 줄 비교. 스크립트가 자동 검사 |
| D | **워크숍 모드로 대조 시험** | 아무 작은 워크숍 모드 1개만 켜고 실행. 이것도 0개면 **로컬 모드와 무관한 환경 문제**, 1개면 **우리 로컬 모드 쪽** | 결정적이고 쉽다 |
| E | **런처 데이터 초기화** | 런처 DB(`launcher-v2.sqlite`)·`mods_registry.json` 손상은 커뮤니티에서 가장 흔한 해결 사례 | 게임·런처 종료 → 사용자 폴더를 통째로 옆으로 옮겨 이름 변경(세이브 백업) → 런처가 빈 상태로 뜨는지 → 모드 하나만 다시 넣고 시험 |
| F | **OneDrive 동기화 간섭** | 런처가 쓰는 순간 OneDrive 가 파일을 잠그거나 되돌릴 수 있다 | 동기화 일시 중지 후 재시험 |
| G | **게임·모드 드라이브가 다름** | 다른 드라이브에 둔 모드가 안 읽히다가 게임을 같은 드라이브로 옮기자 해결된 사례(일화) | 게임 설치 드라이브 확인 |
| H | **파일 접근 추적** | 위가 다 정상이면 게임이 실제로 어느 경로를 열고 어떤 결과를 받는지 본다 | `design/generic_tree/POSTMORTEM.md` 의 Process Monitor 절차 |

D 와 A·B 는 몇 분이면 끝나고 범위를 크게 줄인다. E 는 되돌릴 수 있지만 런처 설정이 초기화되므로 백업 후 한다.

## 4. 진단 스크립트

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Check-Hoi4Mod.ps1 -ModName new_focus
```

추가된 검사: `dlc_load.json` BOM, `gameDataPath` 해석 결과와 실제 사용자 폴더 비교·비ASCII 경로, `.mod` 이름 중복.

## 출처

- [Modding – Hearts of Iron 4 Wiki](https://hoi4.paradoxwikis.com/Modding)
- [Mods showing up, but not turning on (Paradox forum)](https://forum.paradoxplaza.com/forum/threads/mods-showing-up-but-not-turning-on.1290632/)
- [Mods selected, not loading properly (Steam)](https://steamcommunity.com/app/394360/discussions/0/3115897447370823041/)
- [Steam 토론: 런처 데이터 초기화](https://steamcommunity.com/app/394360/discussions/0/4334229587332046860)
- [Steam 토론: 다른 드라이브의 모드](https://steamcommunity.com/app/394360/discussions/0/3092275748073599481)
