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
LOC = "localisation/english/daegyunyeol_l_english.yml"


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


# (이름, 변이, 출력에 반드시 나와야 할 문구[, "warn"])
# 네 번째 항목이 "warn" 이면 종료 코드는 0 이어도 되고 경고로 나오기만 하면 통과다.
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
        sub(EVENTS, "load_focus_tree = kor_daegyunyeol_tree", "load_focus_tree = wrong_tree_id"),
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
        "실제 폴더명과 다르다",
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
        sub(EVENTS, "KOR_disband_all_units = yes\n", ""),
        "아무도 호출하지 않는다",
        "warn",
    ),
    (
        "정의만 하고 쓰지 않는 이념",
        sub(EVENTS, "add_ideas = KOR_rift_demilitarization\n", ""),
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
            if kind == "error" and code == 0:
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
