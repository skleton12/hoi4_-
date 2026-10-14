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
# HOI4 supports these 10 localization languages. Reuse the English source text
# under each locale so the focus tree remains readable with any game language.
LOCALISATION_LANGUAGES = (
    "english", "french", "german", "polish", "braz_por",
    "russian", "spanish", "japanese", "simp_chinese", "korean",
)

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
    "옛 왕가 존재": ("available", "always = yes"),
    "국교 국가": ("available", "always = yes"),
    "숨은 조건": ("available", "always = yes"),
    "종주국 보유": ("available", "is_subject = yes"),
    "괴뢰국 보유": ("available", "num_subjects > 0"),
    # 자치도 단계 이름은 1.19.3 게임 파일(common/autonomous_states/)에서 확인 필요. 틀리면 그 칸만 열리지 않는다.
    "판무관부": ("available", "has_autonomy_state = autonomy_reichskommissariat"),
    "협력정부": ("available", "has_autonomy_state = autonomy_collaboration_government"),
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
PARTY = {"공산주의": "communism", "공산": "communism", "민주주의": "democratic", "민주": "democratic",
         "파시즘": "fascism", "비동맹": "neutrality"}
# 분야별 연구 보너스 → add_tech_bonus 범주 (바닐라 기술 범주 중 확실한 것만)
TECH = {"보병 장비": "infantry_weapons", "포병": "artillery", "대전차": "artillery", "기갑": "armor",
        "레이더": "radar_tech", "전자 공학": "electronics", "전자": "electronics", "로켓": "rocketry",
        "핵": "nuclear", "제트 엔진": "jet_engine", "합성": "synth_resources", "합성 정유소": "synth_resources",
        "합성 고무": "synth_resources", "산업": "industry", "전투기": "light_fighter", "근접 지원기": "cas_bomber"}


def num(text, pattern):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def fnum(text, pattern):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


# 퍼센트형 효과는 국가 정신 수백 개 대신 동적 수정자 셋(산업·군사·국정 개혁)에 변수로 쌓는다.
# (효과 문구 패턴, 수정자 이름, 값 배율, 정신)
MODIFIERS = [
    (r"징집 인력 \+(\d+)%", "conscription", 0.01, "mil"),
    (r"일일 정치력 ([+-][\d.]+)", "political_power_gain", 1, "state"),
    (r"정치력 획득 \+(\d+)%", "political_power_factor", 0.01, "state"),
    (r"(?<!획득 )정치력 \+(\d+)%", "political_power_factor", 0.01, "state"),
    (r"공장 생산량 \+(\d+)%", "industrial_capacity_factory", 0.01, "ind"),
    (r"소비재 공장 ([+-]\d+)%", "consumer_goods_factor", 0.01, "ind"),
    (r"(?<![가-힣] )연구 속도 \+(\d+)%", "research_speed_factor", 0.01, "ind"),
    (r"생산 효율 상한 \+(\d+)%", "production_factory_max_efficiency_factor", 0.01, "ind"),
    (r"생산 효율 증가 \+(\d+)%", "production_factory_efficiency_gain_factor", 0.01, "ind"),
    (r"라인 전환 효율 \+(\d+)%", "line_change_production_efficiency_factor", 0.01, "ind"),
    (r"민간공장 건설 속도 \+(\d+)%", "production_speed_industrial_complex_factor", 0.01, "ind"),
    (r"(?<!강철·텅스텐 )자원 추출 \+(\d+)%", "local_resources_factor", 0.01, "ind"),
    (r"(?<!해안 )요새 건설 속도 \+(\d+)%", "production_speed_bunker_factor", 0.01, "mil"),
    (r"해안 요새 건설 속도 \+(\d+)%", "production_speed_coastal_bunker_factor", 0.01, "mil"),
    (r"보급 소모 (-\d+)%", "supply_consumption_factor", 0.01, "mil"),
    (r"방어전 \+(\d+)%", "army_defence_factor", 0.01, "mil"),
    (r"사단 조직력 \+(\d+)%", "army_org_factor", 0.01, "mil"),
    (r"참호 효과 \+(\d+)%", "max_dig_in_factor", 0.01, "mil"),
    (r"연료 저장량 \+(\d+)%", "max_fuel_factor", 0.01, "mil"),
    (r"항복 한계 \+(\d+)%", "surrender_limit", 0.01, "mil"),
    (r"정당화 기간 (-\d+)%", "justify_war_goal_time", 0.01, "state"),
    (r"전쟁 목표 긴장도 (-\d+)%", "generate_wargoal_tension", 0.01, "state"),
    (r"이념 침투 방어 \+(\d+)%", "drift_defence_factor", 0.01, "state"),
    (r"고문 영입 비용 (-\d+)%", "political_advisor_cost_factor", 0.01, "state"),
    (r"점령지 저항 (-\d+)%", "resistance_target", 0.01, "state"),
    (r"준수 증가 \+(\d+)%", "compliance_growth", 0.01, "state"),
]
SPIRITS = {
    "ind": ("GJ_reform_industry", "산업 개혁", "GFX_idea_generic_political_pressure"),
    "mil": ("GJ_reform_military", "군사 개혁", "GFX_idea_generic_political_pressure"),
    "state": ("GJ_reform_state", "국정 개혁", "GFX_idea_generic_political_pressure"),
}
FACTION = "GJ_regional_faction"
RESOURCES = {"강철": "steel", "석유": "oil", "고무": "rubber", "알루미늄": "aluminium", "텅스텐": "tungsten", "크롬": "chromium"}


def state_count(effect, word):
    m = re.search(word + r" \+\d+ \((\d+)개 주\)", effect)
    return int(m.group(1)) if m else 1


def rewards(effect):
    """효과 요약에서 확실한 것만 실제 효과로 바꾼다."""
    out = []
    if (n := num(effect, r"(?<!일일 )(?<!획득 )정치력 \+(\d+)(?![\d%])")):
        out.append(f"add_political_power = {n}")
    if (n := num(effect, r"민간공장 \+(\d+)(?![\d%])")):
        out.append(f"add_offsite_building = {{ type = industrial_complex level = {n} }}")
    if (n := num(effect, r"군수공장 \+(\d+)(?![\d%])")):
        out.append(f"add_offsite_building = {{ type = arms_factory level = {n} }}")
    if (n := num(effect, r"해군 조선소 \+(\d+)")):
        out.append(f"add_offsite_building = {{ type = dockyard level = {n} }}")
    if (n := num(effect, r"(?<!괴뢰국 )안정도 \+(\d+)%")):
        out.append(f"add_stability = {n / 100:.2f}")
    if (n := num(effect, r"괴뢰국 안정도 \+(\d+)%")):
        out.append(f"every_subject_country = {{ add_stability = {n / 100:.2f} }}")
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
    if (n := num(effect, r"보병 장비 (\d+)(?: 획득)?(?![\d%])")):
        out.append(f"add_equipment_to_stockpile = {{ type = infantry_equipment amount = {n} }}")
    if (n := num(effect, r"수송선 \+(\d+)(?![\d%])")):
        out.append(f"add_equipment_to_stockpile = {{ type = convoy amount = {n} }}")
    if num(effect, r"인프라 \+(\d+)"):
        if "(수도)" in effect:
            out.append("capital_scope = { add_building_construction = { type = infrastructure level = 1 instant_build = yes } }")
        else:
            for _ in range(state_count(effect, "인프라")):
                out.append("random_owned_controlled_state = { limit = { infrastructure < 5 } "
                           "add_building_construction = { type = infrastructure level = 1 instant_build = yes } }")
    if (n := num(effect, r"건물 슬롯 \+(\d+)")):
        for _ in range(state_count(effect, "건물 슬롯")):
            out.append(f"random_owned_controlled_state = {{ add_extra_state_shared_building_slots = {n} }}")
    for word, res in RESOURCES.items():
        if (n := num(effect, word + r" \+(\d+)(?![\d%])")):
            out.append(f"random_owned_controlled_state = {{ add_resource = {{ type = {res} amount = {n} }} }}")
    for bloc, leader in (("연합국", "ENG"), ("추축국", "GER"), ("코민테른", "SOV")):
        if re.search(bloc + r" 가입(?! 가능)", effect):
            out.append(f"if = {{ limit = {{ {leader} = {{ is_faction_leader = yes }} }} {leader} = {{ add_to_faction = ROOT }} }}")
    for who, tag in (("연합국", "ENG"), ("소련", "SOV")):
        if f"{who} 보장 획득" in effect:
            out.append(f"if = {{ limit = {{ country_exists = {tag} }} {tag} = {{ give_guarantee = ROOT }} }}")
    if "자체 진영 생성" in effect:
        out.append(f"if = {{ limit = {{ is_in_faction = no }} create_faction = {FACTION} }}")
    if "정보 기관 설립" in effect:
        out.append("create_intelligence_agency = yes")
    for m in re.finditer(r"(?<!이웃국 )(?<![가-힣·])(공산주의|공산|민주주의|민주|파시즘|비동맹) 지지율 ([+-]\d+)%", effect):
        out.append(f"add_popularity = {{ ideology = {PARTY[m.group(1)]} popularity = {int(m.group(2)) / 100:.2f} }}")
    if (m := re.search(r"공산·파시즘 지지율 ([+-]\d+)%", effect)):
        for ideo in ("communism", "fascism"):
            out.append(f"add_popularity = {{ ideology = {ideo} popularity = {int(m.group(1)) / 100:.2f} }}")
    if (m := re.search(r"(?<!괴뢰국 )자치도 ([+-]\d+)", effect)):
        out.append(f"if = {{ limit = {{ is_subject = yes }} add_autonomy_score = {{ value = {int(m.group(1))} }} }}")
    if (m := re.search(r"괴뢰국 자치도 ([+-]\d+)", effect)):
        # 종주국이 모든 괴뢰국의 자치도를 올리거나 내린다
        out.append(f"every_subject_country = {{ add_autonomy_score = {{ value = {int(m.group(1))} }} }}")
    for word, tech in (("산악병", "tech_mountaineers"), ("해병", "tech_marines"), ("공수부대", "tech_paratroopers")):
        if f"{word} 기술 획득" in effect:
            out.append(f"set_technology = {{ {tech} = 1 }}")
    for m in re.finditer(r"(?<![가-힣])([가-힣]+(?: [가-힣]+)?) 연구(?: 속도)? \+(\d+)%", effect):
        if m.group(1) in TECH:
            out.append(f"add_tech_bonus = {{ name = {{FID}} bonus = {int(m.group(2)) / 100:.2f} uses = 1 "
                       f"category = {TECH[m.group(1)]} }}")
    m = re.search(r"정부를 (공산주의|민주주의|파시즘|비동맹)(?:으)?로 교체", effect)
    if m:
        elections = "yes" if m.group(1) == "민주주의" else "no"
        out.append(f"set_politics = {{ ruling_party = {IDEOLOGY[m.group(1)]} elections_allowed = {elections} }}")

    adds, spirits = [], []
    for pattern, modifier, scale, spirit in MODIFIERS:
        v = fnum(effect, pattern)
        if v:
            adds.append(f"add_to_variable = {{ var = GJ_{modifier} value = {v * scale:g} }}")
            if spirit not in spirits:
                spirits.append(spirit)
    for spirit in spirits:
        name = SPIRITS[spirit][0]
        out.append(f"if = {{ limit = {{ NOT = {{ has_dynamic_modifier = {{ modifier = {name} }} }} }} "
                   f"add_dynamic_modifier = {{ modifier = {name} }} }}")
    return out + adds


def dynamic_modifier_file():
    text = "# build_mod.py 가 만든 파일이다. 포커스가 GJ_<수정자> 변수에 값을 더하면 여기서 반영된다.\n"
    for spirit, (name, _, icon) in SPIRITS.items():
        seen = []
        for _, modifier, _, owner in MODIFIERS:
            if owner == spirit and modifier not in seen:
                seen.append(modifier)
        body = "\n".join(f"\t{m} = GJ_{m}" for m in seen)
        text += f"{name} = {{\n\ticon = {icon}\n\tenable = {{ always = yes }}\n{body}\n}}\n"
    return text


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
                block += [f"\t\t\t{r}".replace("{FID}", fid) for r in rewards(f["effect"])]
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

    loc.append(f' {FACTION}:0 "지역 협약"')
    for name, title, _ in SPIRITS.values():
        loc.append(f' {name}:0 "{title}"')
        loc.append(f' {name}_desc:0 "기본 중점에서 쌓은 {title}의 누적 효과."')
    dyn = MOD / "common" / "dynamic_modifiers" / "gibon_jungjeom_modifiers.txt"
    dyn.parent.mkdir(parents=True, exist_ok=True)
    dyn.write_text(dynamic_modifier_file(), encoding="utf-8")

    out = MOD / "common" / "national_focus" / "generic.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    english_path = None
    for language in LOCALISATION_LANGUAGES:
        loc_path = MOD / "localisation" / language / f"gibon_jungjeom_l_{language}.yml"
        loc_path.parent.mkdir(parents=True, exist_ok=True)
        language_loc = [f"\ufeffl_{language}:", *loc[1:]]
        loc_path.write_text("\n".join(language_loc) + "\n", encoding="utf-8")
        if language == "english":
            english_path = loc_path
    focuses = sum(len(g["focuses"]) for b in branches for g in b["groups"])
    print(f"{out.relative_to(MOD.parent.parent)}  포커스 {focuses}개")
    print(f"{english_path.relative_to(MOD.parent.parent)} + {len(LOCALISATION_LANGUAGES) - 1}개 언어  키 {len(loc) - 1}개씩")


if __name__ == "__main__":
    build()
