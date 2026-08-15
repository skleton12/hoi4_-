# 대균열 — HOI4 모드 디버깅

> 증상: 파일 문법은 문제없고 런처도 모드를 인식하는데, 게임 안에서 포커스트리·디시전이 **하나도** 반영되지 않는다.

## 이 저장소의 상태

현재 저장소는 비어 있다. 모드 파일이 여기 없으면 원격 세션에서는 파일을 직접 볼 수 없다.
`문서\Paradox Interactive\Hearts of Iron IV\mod\대균열` 폴더를 통째로 이 저장소에 올리면 한 줄씩 감사할 수 있다.

```powershell
cd "$env:USERPROFILE\Documents\Paradox Interactive\Hearts of Iron IV\mod\대균열"
git init
git remote add origin https://github.com/skleton12/hoi4_-
git checkout -b claude/hoi4-mod-debug-glq466
git add -A
git commit -m "mod snapshot"
git push -u origin claude/hoi4-mod-debug-glq466
```

## 먼저 할 것: 진단 스크립트

`tools/Check-Hoi4Mod.ps1` 을 PC에서 실행하고 출력 전체를 붙여넣으면 된다.
PowerShell 외에 아무것도 설치할 필요 없다.

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Check-Hoi4Mod.ps1 | Tee-Object -FilePath report.txt
```

검사 항목: 사용자 데이터 폴더 중복(OneDrive), `dlc_load.json` 실제 활성화 여부, `.mod` 디스크립터와 `path=`,
게임 버전 대 `supported_version`, 폴더 구조, 파일 인코딩(CP949/BOM), 중괄호 균형,
포커스트리 `country` 블록, 디시전 카테고리 정의 여부, 이벤트 `add_namespace`, 그리고 `error.log` 꼬리.

---

## 원인 후보 (가능성 순)

"문법은 맞는데 **전부** 안 나온다"는 건 대개 문법 문제가 아니다. 게임이 폴더를 아예 읽지 않았다는 뜻이다.
일부만 깨졌다면 `error.log` 에 흔적이 남고 나머지는 작동한다. 전부 없으면 로딩 자체가 안 된 것이다.

### A. 모드가 실제로 로드되지 않는 경우

1. **`dlc_load.json` 에 모드가 없다.**
   `문서\Paradox Interactive\Hearts of Iron IV\dlc_load.json` 을 열어 `enabled_mods` 에
   `"mod/대균열.mod"` 가 있는지 본다. 런처 **목록에 보이는 것**과 **플레이세트에서 켜진 것**은 별개다.
   여기 없으면 게임은 모드를 모른 채 실행된다. 반드시 런처의 [플레이] 버튼으로 실행할 것.

2. **`supported_version` 이 현재 게임 버전보다 낮다.**
   예: `"1.12.*"` 인데 게임은 1.16.x. 런처는 모드를 목록에 계속 보여주면서 "호환되지 않음"으로
   표시하고 플레이세트에서 조용히 제외한다. 증상이 정확히 이것과 일치한다.
   → 현재 버전(`launcher-settings.json` 의 `rawVersion`)에 맞춰 `1.16.*` 로 수정.

3. **`.mod` 파일 자체가 없거나 `path=` 가 어긋났다.**
   폴더형 모드는 두 개가 **모두** 필요하다.
   - `mod\대균열.mod` ← 폴더와 나란히
   - `mod\대균열\descriptor.mod` ← 폴더 안
   `path=` 는 슬래시를 쓴다. `path="mod/대균열"` (역슬래시 `\` 는 파싱 실패).
   `archive=` 와 `path=` 를 같이 쓰면 안 된다.

4. **경로에 한글이 들어 있다.**
   Paradox 런처는 비ASCII 경로에서 문제를 일으킨 사례가 많다. Windows 사용자명이 한글이면 더 그렇다.
   폴더명과 `.mod` 파일명을 영문으로 바꿔서 테스트한다 — `mod\daegyunyeol`, `mod\daegyunyeol.mod`,
   `path="mod/daegyunyeol"`. 런처에 표시되는 `name="대균열"` 은 한글로 둬도 된다.
   재등록 후 런처에서 플레이세트를 다시 확인할 것.

5. **OneDrive 리디렉션으로 문서 폴더가 두 개다.**
   `C:\Users\X\Documents\...` 와 `C:\Users\X\OneDrive\문서\...` 가 동시에 존재하면
   런처가 쓰는 폴더와 게임이 읽는 폴더가 갈릴 수 있다. 스크립트가 이걸 잡아준다.

6. **파일 인코딩이 UTF-8 이 아니다.**
   한글이 든 파일을 Windows 메모장에서 기본값으로 저장하면 CP949(ANSI)가 된다.
   게임은 파싱에 실패하고 파일을 통째로 버린다. 스크립트가 파일별로 판정한다.
   - `common/`, `events/` 스크립트: **BOM 없는 UTF-8**
   - `localisation/*.yml`: **BOM 포함 UTF-8** (반대로 하면 안 된다)

**로드 여부 1분 판정:** 메인 메뉴 우하단 체크섬을 본다. 바닐라와 동일하면 모드는 로드되지 않은 것이다.

### B. 로드는 되는데 내용이 안 보이는 경우

7. **KOR 은 1936년 바닐라에 존재하지 않는 국가다.**
   한반도는 일본 코어다. 일본 디시전으로 해방시키기 전에는 플레이할 수도, 트리를 볼 수도 없다.
   콘솔(`~`)에서 `tag KOR` 로 강제 전환해 트리가 뜨는지 먼저 확인한다.

8. **포커스트리에 `country` 블록이 없다.**
   이게 없으면 트리는 어떤 나라에도 배정되지 않는다. 문법 오류는 나지 않는다.
   ```
   focus_tree = {
       id = kor_daegyunyeol
       country = {
           factor = 0
           modifier = { add = 100  tag = KOR }
       }
       default = no
       ...
   }
   ```
   경로는 반드시 `common/national_focus/` 다.

9. **저장된 게임을 불러왔다.**
   포커스트리 배정은 게임 시작 시점에 결정된다. 반드시 **새 게임(1936)** 으로 테스트할 것.

10. **디시전 카테고리가 정의되지 않았다.**
    새 카테고리를 쓰면서 `common/decisions/categories/` 에 정의하지 않으면
    디시전 탭에 아무것도 뜨지 않고 에러도 안 난다.

11. **`allowed = { }` 가 false 다.**
    `allowed` 는 게임 시작 시점에 단 한 번 평가된다. 여기서 걸리면 그 디시전은 영원히 존재하지 않는다.
    조건부 표시는 `visible`, 실행 가능 여부는 `available` 로 나눠 쓴다.

12. **이벤트에 `add_namespace` 가 없다.** 파일 전체가 거부된다.

13. **어드바이저를 구형 방식으로 정의했다.**
    1.12 이후 캐릭터/어드바이저는 `common/characters/` 에서 `advisor = { slot = ... }` 로 정의한다.
    `common/ideas/` 에만 넣은 구형 포맷은 조용히 무시될 수 있다.

---

## error.log 읽는 법

`문서\Paradox Interactive\Hearts of Iron IV\logs\error.log` 하나로 대부분 끝난다.

1. `error.log` 를 삭제한다
2. 런처에서 게임 실행
3. 1936 새 게임 시작
4. 종료 후 `error.log` 를 연다

`Unexpected token`, `not found`, `failed to load` 같은 줄에 파일명과 줄 번호가 찍힌다.
로그가 아예 새로 생기지 않거나 모드 파일 이름이 한 번도 안 나오면 → A 항목 문제다.

## 참고

이 원격 세션은 클라우드 컨테이너에서 실행되므로 PC의 게임 폴더와 로그에 접근할 수 없다.
로그를 실시간으로 보면서 고치려면 PC에 Claude Code 를 직접 설치하는 쪽이 맞다 — https://claude.com/claude-code
