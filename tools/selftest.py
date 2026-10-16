#!/usr/bin/env python3
"""
검증기 자체 테스트.

validate.py 가 "오류 0" 을 내는 게 실제로 검사를 통과한 결과인지,
아니면 그냥 아무것도 안 보고 있는 건지 확인한다.
정상 모드를 복사해 고의로 한 군데씩 망가뜨리고, 그 오류가 잡히는지 본다.

사용법:
    python3 tools/selftest.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MOD = REPO / "mod" / "daegyunyeol"
VALIDATE = REPO / "tools" / "validate.py"

FOCUS = "common/national_focus/kor_daegyunyeol.txt"
EVENTS = "events/daegyunyeol_events.txt"
DECISIONS = "common/decisions/jap_daegyunyeol.txt"
CATEGORIES = "common/decisions/categories/daegyunyeol_categories.txt"
EFFECTS = "common/scripted_effects/daegyunyeol_effects.txt"
LOC = "localisation/korean/daegyunyeol_l_korean.yml"
ENG = "localisation/english/daegyunyeol_l_english.yml"


def sub(path: str, old: str, new: str):
    """파일 안 문자열 치환 변이."""

    def mutate(root: Path):
        p = root / path
        enc = "utf-8-sig" if p.suffix == ".yml" else "utf-8"
        text = p.read_text(encoding=enc)
        if old not in text:
            raise AssertionError(f"변이 대상 문자열을 찾을 수 없다: {path} <- {old!r}")
        text = text.replace(old, new, 1)
        p.write_text(text, encoding=enc)

    return mutate


def raw(path: str, fn):
    def mutate(root: Path):
        p = root / path
        p.write_bytes(fn(p.read_bytes()))

    return mutate


def drop_file(path: str):
    def mutate(root: Path):
        (root / path).unlink()

    return mutate


def install_debug_markers(root: Path):
    target = root / "localisation" / "replace"
    target.mkdir(parents=True, exist_ok=True)
    for path in (REPO / "tools" / "debug_localisation").glob("*.yml"):
        shutil.copy(path, target / path.name)


def wrong_language_folder(root: Path):
    path = root / LOC
    target = root / "localisation" / "english" / path.name
    path.rename(target)


# (이름, 변이, 출력에 반드시 나와야 할 문구[, "warn"])
# "warn": 종료 코드 0과 지정 경고, "ok": 종료 코드 0과 지정 출력을 요구한다.
CASES = [
    (
        "포커스트리 country 블록 삭제",
        sub(FOCUS, "\tcountry = {\n\t\tfactor = 0\n\n\t\tmodifier = {\n\t\t\tadd = 100\n\t\t\ttag = KOR\n\t\t}\n\t}\n", ""),
        "country 블록이 없다",
    ),
    (
        "존재하지 않는 포커스를 선행조건으로",
        sub(FOCUS, "prerequisite = { focus = KOR_daegyunyeol_awakening }", "prerequisite = { focus = KOR_does_not_exist }"),
        "존재하지 않는 포커스",
    ),
    (
        "포커스 id 중복",
        sub(FOCUS, "id = KOR_nikke_contact", "id = KOR_investigate_rift"),
        "focus id 중복",
    ),
    (
        "존재하지 않는 이벤트 발동",
        sub(FOCUS, "country_event = { id = daegyunyeol.3 hours = 6 }", "country_event = { id = daegyunyeol.999 hours = 6 }"),
        "존재하지 않는 이벤트",
    ),
    (
        "정의되지 않은 이념 추가",
        sub(FOCUS, "add_ideas = KOR_nikke_district", "add_ideas = KOR_ghost_idea"),
        "정의되지 않은 이념",
    ),
    (
        "존재하지 않는 포커스트리 로드",
        sub(EFFECTS, "load_focus_tree = kor_daegyunyeol_tree", "load_focus_tree = wrong_tree_id"),
        "존재하지 않는 포커스트리",
    ),
    (
        "add_namespace 삭제",
        sub(EVENTS, "add_namespace = daegyunyeol", ""),
        "add_namespace 가 없다",
    ),
    (
        "이벤트 option 삭제",
        sub(
            EVENTS,
            "\toption = {\n\t\tname = daegyunyeol.2.a\n\t\tadd_stability = 0.10\n\t\tadd_war_support = 0.05\n\t}\n",
            "",
        ),
        "option 이 없다",
    ),
    (
        "디시전 카테고리 정의 파일 삭제",
        drop_file(CATEGORIES),
        "정의되지 않았다",
    ),
    (
        "정의되지 않은 캐릭터 승격",
        sub(FOCUS, "promote_character = KOR_leader_democratic", "promote_character = KOR_nobody"),
        "정의되지 않은 캐릭터",
    ),
    (
        "중괄호 불균형",
        sub(FOCUS, "focus_tree = {", "focus_tree = { {"),
        "닫히지 않은",
    ),
    (
        "로컬라이제이션 키 삭제",
        sub(LOC, ' KOR_seal_the_rift:0 "대균열 봉인"\n', ""),
        "키 누락: KOR_seal_the_rift",
    ),
    (
        "로컬라이제이션 BOM 제거",
        raw(LOC, lambda b: b[3:] if b.startswith(b"\xef\xbb\xbf") else b),
        "UTF-8 BOM 이 있어야",
    ),
    (
        "스크립트 파일을 CP949 로 저장",
        # CP949 에 없는 문자(엠대시 등)는 대체한다. 한글이 CP949 바이트로 나가는 것이 검사 대상이다.
        raw(FOCUS, lambda b: b.decode("utf-8").encode("cp949", errors="replace")),
        "UTF-8 이 아니다",
    ),
    (
        "스크립트 파일에 BOM 추가",
        raw(FOCUS, lambda b: b"\xef\xbb\xbf" + b),
        "BOM 이 붙어 있다",
    ),
    (
        "폴더 옆 .mod 의 path 를 역슬래시로",
        sub("../daegyunyeol.mod", 'path="mod/daegyunyeol"', 'path="mod\\daegyunyeol"'),
        "역슬래시",
    ),
    (
        "폴더 안 descriptor.mod 에 잘못된 path 추가",
        sub("descriptor.mod", 'name="대균열"', 'name="대균열"\npath="mod/wrong_name"'),
        "실제 설치 경로와 다르다",
    ),
    (
        "두 디스크립터의 supported_version 불일치",
        sub("descriptor.mod", 'supported_version="1.19.*"', 'supported_version="1.16.*"'),
        "supported_version 가",
    ),
    (
        "폴더 옆 .mod 의 path 삭제",
        sub("../daegyunyeol.mod", 'path="mod/daegyunyeol"\n', ""),
        "게임이 파일을 찾지 못한다",
    ),
    (
        "has_idea 오타 (무장 금지가 영원히 안 풀림)",
        sub(EFFECTS, "limit = { has_idea = KOR_rift_demilitarization }", "limit = { has_idea = KOR_rift_demilitarisation }"),
        "has_idea 로 검사한다",
    ),
    (
        "정의되지 않은 scripted effect 호출",
        sub(FOCUS, "KOR_lift_arms_ban = yes", "KOR_lift_arms_bans = yes"),
        "정의되지 않은 scripted effect",
    ),
    (
        "아무도 호출하지 않는 scripted effect",
        sub(EFFECTS, "KOR_disband_all_units = yes\n", ""),
        "아무도 호출하지 않는다",
        "warn",
    ),
    (
        "정의만 하고 쓰지 않는 이념",
        sub(EFFECTS, "add_ideas = KOR_rift_demilitarization\n", ""),
        "어디서도 추가하지 않는다",
        "warn",
    ),
    (
        "swap_ideas 가 없는 이념을 가리킴",
        sub(FOCUS, "add_idea = KOR_limited_rearmament", "add_idea = KOR_no_such_idea"),
        "정의되지 않은 이념",
    ),
    (
        "이벤트 id 중복",
        sub(EVENTS, "id = daegyunyeol.5", "id = daegyunyeol.3"),
        "이벤트 id 중복",
    ),
    (
        "로컬라이제이션 문법 오류",
        sub(LOC, ' KOR_seal_the_rift:0 "대균열 봉인"', ' KOR_seal_the_rift 대균열 봉인'),
        "해석 불가",
    ),
    ("한국어 파일 삭제", drop_file(LOC), "키 누락"),
    ("영어 파일 삭제", drop_file(ENG), "키 누락"),
    ("한국어 키 중복", sub(LOC, ' KOR_seal_the_rift:0', ' KOR_rift_army:0'), "키 중복"),
    ("영어/한국어 전용 키 불일치", sub(LOC, ' KOR_seal_the_rift:0', ' KOR_renamed_key:0'), "키 불일치"),
    ("파일명과 헤더 불일치", sub(LOC, 'l_korean:', 'l_english:'), "파일명과 언어 헤더 불일치"),
    ("잘못된 언어 헤더", sub(LOC, 'l_korean:', 'korean:'), "언어 헤더 오류"),
    ("UTF-8 손상", raw(LOC, lambda b: b + b"\xff"), "UTF-8 이 아니다"),
    ("이스케이프 없는 따옴표", sub(LOC, '"대균열 봉인"', '"대균열 "봉인""'), "해석 불가"),
    ("빈 번역", sub(LOC, '"대균열 봉인"', '""'), "값이 비어 있다"),
    ("연구 보너스 번역 누락", sub(LOC, ' KOR_rift_research:0', ' KOR_unused_research:0'), "키 누락: KOR_rift_research"),
    ("실제 이벤트 제목 참조 오타", sub(EVENTS, 'title = daegyunyeol.1.t', 'title = daegyunyeol.missing_title'), "키 누락: daegyunyeol.missing_title"),
    ("실제 이벤트 설명 참조 오타", sub(EVENTS, 'desc = daegyunyeol.1.d', 'desc = daegyunyeol.missing_desc'), "키 누락: daegyunyeol.missing_desc"),
    ("정치고문 영입 누락", sub(EFFECTS, '\t\trecruit_character = KOR_rift_commissar', ''), "정치고문 영입 누락"),
    ("캐릭터 id 중복", sub('common/characters/daegyunyeol_characters.txt', '\tKOR_district_liaison = {', '\tKOR_rift_commissar = {'), "캐릭터 id 중복"),

    ("폴더명만 맞고 부모 경로가 틀림", sub('../daegyunyeol.mod', 'path="mod/daegyunyeol"', 'path="wrong/daegyunyeol"'), "실제 설치 경로와 다르다"),
    ("영어 BOM 제거", raw(ENG, lambda b: b.removeprefix(b"\xef\xbb\xbf")), "BOM"),
    ("정상 이스케이프와 행말 주석", sub(LOC, '"대균열 봉인"', r'"대균열 \"봉인\"" # comment'), "오류 0개", "ok"),
    ("이벤트 사용자 지정 제목 키", sub(EVENTS, 'title = daegyunyeol.1.t', 'title = daegyunyeol.2.t'), "오류 0개", "ok"),

    ("선택적 진단 마커 충돌 경고", install_debug_markers, "다른 모드와 충돌 가능한 replace 키", "warn"),
    ("언어 폴더 불일치", wrong_language_folder, "언어 폴더와 언어 헤더 불일치"),
    ("미정의 번역 치환 참조", sub(LOC, '"대균열 봉인"', '"$DAEGYUNYEOL_MISSING$"'), "외부 또는 미정의 번역 참조", "warn"),

]


def run_validator(mod_dir: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(VALIDATE), str(mod_dir)],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    print("검증기 자체 테스트\n")

    code, out = run_validator(MOD)
    if code != 0:
        print("기준 상태부터 실패한다. 먼저 validate.py 출력을 확인할 것.")
        print(out)
        return 1
    print("  [ OK ] 기준: 정상 모드는 오류 0\n")

    failures = 0
    for i, case in enumerate(CASES, start=1):
        label, mutate, expect = case[0], case[1], case[2]
        kind = case[3] if len(case) > 3 else "error"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "daegyunyeol"
            shutil.copytree(MOD, root)
            shutil.copy(MOD.parent / "daegyunyeol.mod", root.parent / "daegyunyeol.mod")
            try:
                mutate(root)
            except AssertionError as exc:
                print(f"  [FAIL] {i:2}. {label}: {exc}")
                failures += 1
                continue

            code, out = run_validator(root)
            hit = [l.strip() for l in out.splitlines() if expect in l]
            if kind in ("ok", "warn") and code != 0:
                print(f"  [FAIL] {i:2}. {label}: 정상/경고 전용 사례에서 오류 발생\n{out}")
                failures += 1
            elif kind == "error" and code == 0:
                print(f"  [FAIL] {i:2}. {label}: 망가뜨렸는데 오류 0 으로 통과했다")
                failures += 1
            elif not hit:
                print(f"  [FAIL] {i:2}. {label}: '{expect}' 가 출력에 없다")
                for line in out.splitlines():
                    if "ERROR" in line or "WARN" in line:
                        print(f"           실제: {line.strip()}")
                failures += 1
            elif kind == "warn" and not any(l.startswith("WARN") for l in hit):
                print(f"  [FAIL] {i:2}. {label}: 경고로 나와야 하는데 아니다 -> {hit[0]}")
                failures += 1
            else:
                print(f"  [ OK ] {i:2}. {label}")

    print()
    print(f"  {len(CASES) - failures}/{len(CASES)} 통과")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
