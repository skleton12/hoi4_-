"""설계 데이터(data/*.json)를 「기본 중점 변경 모드」 파일로 옮긴다.

    python3 design/generic_tree/build_mod.py

만드는 것 (mod/gibon_jungjeom/ 아래):
  common/national_focus/generic.txt                  바닐라 기본 트리를 같은 경로로 덮어쓴다
  localisation/english/gibon_jungjeom_l_english.yml  포커스 이름·설명·효과 안내 (UTF-8 BOM)

시험판이다. 효과 요약 중 확실히 옮길 수 있는 것(정치력, 공장, 안정도, 전쟁 지원, 경험치, 연구 슬롯,
정부 교체)만 실제 효과로 바꾸고, 나머지는 설계 문구를 효과 안내(custom_effect_tooltip)로 보여 준다.
"""
import json
import re
from pathlib import Path

from render import layout, parents_of

HERE = Path(__file__).parent
DATA = HERE / "data"
MOD = HERE.parent.parent / "mod" / "gibon_jungjeom"
PREFIX = "GJ"

ICONS = {
    "start": "GFX_GJ_political_pressure",
    "industry": "GFX_GJ_construct_civ_factory",
    "military": "GFX_GJ_army_doctrines",
    "politics": "GFX_GJ_political_pressure",
    "diplomacy": "GFX_GJ_major_alliance",
    "terrain": "GFX_GJ_construct_infrastructure",
    "independence": "GFX_GJ_political_pressure",
    "late": "GFX_GJ_production",
}

# 조건 문구 → (allow_branch | available, 트리거). allow_branch 는 트리를 처음 불러올 때 한 번만 보므로
# 지형·지역처럼 변하지 않는 조건에만 쓰고, 전쟁·속국 여부처럼 바뀌는 조건은 available 로 건다.
CONDITIONS = {
    "해안 주 보유": ("allow_branch", "any_owned_state = { is_coastal = yes }"),
    "해안 없음": ("allow_branch", "NOT = { any_owned_state = { is_coastal = yes } }"),
    "섬 국가": ("allow_branch", "capital_scope = { is_coastal = yes }"),
    "남미·중미": ("allow_branch", "capital_scope = { is_on_continent = south_america }"),
    "발칸·동유럽": ("allow_branch", "capital_scope = { is_on_continent = europe }"),
    "중동·북아프리카": ("allow_branch", "capital_scope = { OR = { is_on_continent = middle_east is_on_continent = africa } }"),
    "아시아": ("allow_branch", "capital_scope = { is_on_continent = asia }"),
    "옛 왕가 존재": ("available", "always = yes"),
    "국교 국가": ("available", "always = yes"),
    "숨은 조건": ("available", "always = yes"),
    "종주국 보유": ("available", "is_subject = yes"),
    "독립 달성 후": ("available", "is_subject = no"),
    "전쟁 종료 후": ("available", "has_war = no"),
    "전쟁 중": ("available", "has_war = yes"),
    "수도 피점령": ("available", "capital_scope = { NOT = { is_controlled_by = ROOT } }"),
    "본토 해방 후": ("available", "capital_scope = { is_controlled_by = ROOT }"),
    "전쟁 중 전쟁 지원 30% 미만": ("available", "has_war = yes has_war_support < 0.3"),
}
# 집권 경로 조건은 해당 경로의 마지막 칸을 끝냈는지로 본다
ROUTE_CONDITIONS = {"무장 봉기로 집권": "com_war", "군부 쿠데타로 집권": "neu_war"}

IDEOLOGY = {"공산주의": "communism", "민주주의": "democratic", "파시즘": "fascism", "비동맹": "neutrality"}


def num(text, pattern):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def rewards(effect):
    """효과 요약에서 확실한 것만 실제 효과로 바꾼다."""
    out = []
    if (n := num(effect, r"(?<!일일 )정치력 \+(\d+)(?!%)")):
        out.append(f"add_political_power = {n}")
    if (n := num(effect, r"민간공장 \+(\d+)(?!%)")) and "건설" not in effect.split("민간공장")[1][:4]:
        out.append(f"add_offsite_building = {{ type = industrial_complex level = {n} }}")
    if (n := num(effect, r"군수공장 \+(\d+)")):
        out.append(f"add_offsite_building = {{ type = arms_factory level = {n} }}")
    if (n := num(effect, r"안정도 \+(\d+)%")):
        out.append(f"add_stability = {n / 100:.2f}")
    if (n := num(effect, r"전쟁 지원 \+(\d+)%")):
        out.append(f"add_war_support = {n / 100:.2f}")
    if (n := num(effect, r"육군 경험 \+(\d+)")):
        out.append(f"army_experience = {n}")
    if (n := num(effect, r"해군 경험 \+(\d+)")):
        out.append(f"navy_experience = {n}")
    if (n := num(effect, r"공군 경험 \+(\d+)")):
        out.append(f"air_experience = {n}")
    if (n := num(effect, r"연구 슬롯 \+(\d+)")):
        out.append(f"add_research_slot = {n}")
    m = re.search(r"정부를 (공산주의|민주주의|파시즘|비동맹)(?:으)?로 교체", effect)
    if m:
        elections = "yes" if m.group(1) == "민주주의" else "no"
        out.append(f"set_politics = {{ ruling_party = {IDEOLOGY[m.group(1)]} elections_allowed = {elections} }}")
    return out


def rows_for(groups):
    """소갈래마다 시작 줄(y)을 정한다. 합류는 부모들이 모두 끝난 다음 줄."""
    by_id = {g["id"]: g for g in groups}
    start = {}

    def row(g):
        if g["id"] not in start:
            ps = parents_of(g)
            start[g["id"]] = max((row(by_id[p]) + len(by_id[p]["focuses"]) for p in ps), default=0)
        return start[g["id"]]

    for g in groups:
        row(g)
    return start


def focus_id(gid, i):
    return f"{PREFIX}_{gid}_{i}"


def build():
    branches = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DATA.glob("*.json"))]
    lines = [
        "# 「기본 중점 변경 모드」 — design/generic_tree/build_mod.py 가 만든 파일이다. 직접 고치지 말 것.",
        "# 바닐라 common/national_focus/generic.txt 를 같은 경로로 덮어써 기본 트리를 바꾼다.",
        "focus_tree = {",
        "\tid = generic_focus",
        "",
        "\tcountry = {",
        "\t\tfactor = 1",
        "\t}",
        "",
        "\tdefault = yes",
        "",
        "\tcontinuous_focus_position = { x = 50 y = 1600 }",
    ]
    loc = ["﻿l_english:"]
    x_offset = 0
    route_last = {}
    for b in branches:
        for g in b["groups"]:
            if g["id"] in ROUTE_CONDITIONS.values():
                route_last[g["id"]] = focus_id(g["id"], len(g["focuses"]))

    unknown = set()
    for b in branches:
        groups = b["groups"]
        pos, cols = layout(groups)
        start = rows_for(groups)
        icon = ICONS.get(b["branch"], "GFX_goal_unknown")
        lines += ["", "\t" + "#" * 60, f"\t# {b['title']}", "\t" + "#" * 60]

        siblings = {}
        for g in groups:
            if g["exclusive"]:
                siblings.setdefault((g["exclusive"], str(g["after"])), []).append(g["id"])

        for g in groups:
            x = x_offset + int(round(pos[g["id"]][0] * 2))
            for i, f in enumerate(g["focuses"], 1):
                fid = focus_id(g["id"], i)
                block = [f"\tfocus = {{", f"\t\tid = {fid}", f"\t\ticon = {icon}",
                         f"\t\tx = {x}", f"\t\ty = {start[g['id']] + i - 1}",
                         f"\t\tcost = {f['days'] // 7}"]
                if i == 1:
                    ps = parents_of(g)
                    if ps:
                        ors = " ".join(f"focus = {focus_id(p, len(next(x for x in groups if x['id'] == p)['focuses']))}" for p in ps)
                        block.append(f"\t\tprerequisite = {{ {ors} }}")
                    if g["exclusive"]:
                        others = [o for o in siblings[(g["exclusive"], str(g["after"]))] if o != g["id"]]
                        if others:
                            block.append("\t\tmutually_exclusive = { " + " ".join(f"focus = {focus_id(o, 1)}" for o in others) + " }")
                    cond = g["condition"]
                    if cond in ROUTE_CONDITIONS:
                        block.append(f"\t\tavailable = {{ has_completed_focus = {route_last[ROUTE_CONDITIONS[cond]]} }}")
                    elif cond:
                        if cond not in CONDITIONS:
                            unknown.add(cond)
                        else:
                            kind, trig = CONDITIONS[cond]
                            block.append(f"\t\t{kind} = {{ {trig} }}")
                else:
                    block.append(f"\t\tprerequisite = {{ focus = {focus_id(g['id'], i - 1)} }}")
                block.append("\t\tsearch_filters = { FOCUS_FILTER_POLITICAL }" if b["branch"] in ("politics", "diplomacy", "independence", "start")
                             else "\t\tsearch_filters = { FOCUS_FILTER_INDUSTRY }" if b["branch"] in ("industry", "terrain", "late")
                             else "\t\tsearch_filters = { FOCUS_FILTER_RESEARCH }")
                block.append("\t\tai_will_do = { factor = 1 }")
                block.append("\t\tcompletion_reward = {")
                block.append(f"\t\t\tcustom_effect_tooltip = {fid}_tt")
                block += [f"\t\t\t{r}" for r in rewards(f["effect"])]
                block += ["\t\t}", "\t}"]
                lines += block

                name = f["name"].replace('"', "'")
                loc.append(f' {fid}:0 "{name}"')
                loc.append(f' {fid}_desc:0 "{b["title"]} · {g["title"]}"')
                loc.append(f' {fid}_tt:0 "설계 효과: {f["effect"]}"')
        x_offset += int(cols * 2) + 4

    lines.append("}")
    if unknown:
        raise SystemExit(f"CONDITIONS 에 없는 조건 문구: {sorted(unknown)}")

    out = MOD / "common" / "national_focus" / "generic.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    loc_path = MOD / "localisation" / "english" / "gibon_jungjeom_l_english.yml"
    loc_path.parent.mkdir(parents=True, exist_ok=True)
    loc_path.write_text("\n".join(loc) + "\n", encoding="utf-8")
    korean_path = MOD / "localisation" / "korean" / "gibon_jungjeom_l_korean.yml"
    korean_path.parent.mkdir(parents=True, exist_ok=True)
    korean_loc = ["\ufeffl_korean:", *loc[1:]]
    korean_path.write_text("\n".join(korean_loc) + "\n", encoding="utf-8")
    focuses = sum(len(g["focuses"]) for b in branches for g in b["groups"])
    print(f"{out.relative_to(MOD.parent.parent)}  포커스 {focuses}개")
    print(f"{loc_path.relative_to(MOD.parent.parent)}  키 {len(loc) - 1}개")


if __name__ == "__main__":
    build()
