"""구성 데이터 검사기.

    python3 design/generic_tree/check.py

data/*.json 을 읽어 규격(SPEC.md)에 맞는지 본다. 빈 소갈래(focuses = [])는 '미작성'으로 세고 오류로 보지 않는다.
하나라도 채워진 소갈래는 칸 수가 target 과 정확히 같아야 한다. 오류가 있으면 종료 코드 1.
"""
import json
import sys
import unicodedata
from pathlib import Path

DATA = Path(__file__).parent / "data"
GROUP_KEYS = {"id", "title", "after", "exclusive", "condition", "target", "focuses"}
FOCUS_KEYS = {"name", "effect", "days"}
MAX_CHAIN = 5  # 한 소갈래의 최대 칸 수. 넓고 얕은 트리를 유지한다


def pad(text, width):
    """한글이 두 칸을 차지하는 터미널에서 왼쪽 정렬한다."""
    used = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return text + " " * max(0, width - used)


def main():
    errors = []
    group_ids = {}
    names = {}
    rows = []

    for path in sorted(DATA.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{path.name}: JSON 구문 오류 {e.lineno}행: {e.msg}")
            continue

        local_ids = {g.get("id") for g in data.get("groups", [])}
        done = target = 0

        for g in data.get("groups", []):
            gid = g.get("id")
            where = f"{path.name}:{gid}"
            if set(g) != GROUP_KEYS:
                errors.append(f"{where}: 키가 규격과 다름 {sorted(set(g) ^ GROUP_KEYS)}")
            if gid in group_ids:
                errors.append(f"{where}: 소갈래 id 중복 ({group_ids[gid]})")
            group_ids[gid] = path.name
            after = g.get("after")
            for a in ([] if after is None else [after] if isinstance(after, str) else after):
                if a not in local_ids:
                    errors.append(f"{where}: after '{a}' 가 같은 파일에 없음")

            if g.get("target", 0) > MAX_CHAIN:
                errors.append(f"{where}: 소갈래가 {g['target']}칸. 트리가 아래로 늘어지지 않게 {MAX_CHAIN}칸 이하로 쪼갠다")

            focuses = g.get("focuses", [])
            target += g.get("target", 0)
            if not focuses:
                continue
            if len(focuses) != g.get("target"):
                errors.append(f"{where}: 칸 수 {len(focuses)} ≠ 목표 {g.get('target')}")
            done += len(focuses)

            for i, f in enumerate(focuses, 1):
                fw = f"{where}#{i}"
                if set(f) != FOCUS_KEYS:
                    errors.append(f"{fw}: 키가 규격과 다름 {sorted(set(f) ^ FOCUS_KEYS)}")
                name = str(f.get("name", ""))
                if not 2 <= len(name) <= 12:
                    errors.append(f"{fw}: 이름 길이 {len(name)}자 (2~12자)")
                if len(str(f.get("effect", ""))) > 30:
                    errors.append(f"{fw}: 효과 설명이 30자 초과")
                if f.get("days") not in (35, 70):
                    errors.append(f"{fw}: days 는 35 또는 70")
                if name in names:
                    errors.append(f"{fw}: 이름 '{name}' 중복 ({names[name]})")
                names[name] = fw

        rows.append((data.get("title", path.stem), done, target))

    width = 18
    for title, done, target in rows:
        bar = "#" * round(20 * done / target) if target else ""
        print(f"{pad(title, width)}{done:>4} / {target:<4} {bar}")
    done = sum(r[1] for r in rows)
    target = sum(r[2] for r in rows)
    print(f"{pad('합계', width)}{done:>4} / {target}")

    if errors:
        print(f"\n오류 {len(errors)}건")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("\n오류 없음")


if __name__ == "__main__":
    main()
