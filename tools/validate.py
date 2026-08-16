#!/usr/bin/env python3
"""
대균열 모드 정적 검증기.

Paradox 스크립트를 실제로 파싱해서 게임을 켜지 않고 잡을 수 있는 건 전부 잡는다.
게임 실행 없이 확인 가능한 범위:

  - 파일 인코딩 (.txt = BOM 없는 UTF-8, .yml = BOM 포함 UTF-8)
  - 구문 오류 (줄 번호 포함)
  - 포커스 id 중복 / 선행조건 미해결 / 순환 / 좌표 충돌
  - 이벤트 namespace 선언, id 중복, 참조된 이벤트 존재 여부
  - 디시전 카테고리 정의 여부
  - add_ideas / idea_token / add_timed_idea 참조 해결
  - 국가 플래그: 검사만 하고 세우지 않는 플래그
  - 로컬라이제이션 키 누락 / 미사용
  - .mod 디스크립터 정합성

확인 불가능한 범위(게임 실행이 필요):
  - GFX 스프라이트 이름 유효성, 트레이트/모디파이어 이름 유효성, 밸런스

사용법:
    python3 tools/validate.py [모드폴더]
종료 코드는 오류 개수(최대 100).
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# 파서
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(
    r"""
      (?P<comment>\#[^\n]*)
    | (?P<ws>\s+)
    | (?P<string>"(?:[^"\\\n]|\\.)*")
    | (?P<op><=|>=|!=|==|[=<>{}])
    | (?P<bare>[^\s{}=<>\#"]+)
    """,
    re.VERBOSE,
)


class ParseError(Exception):
    def __init__(self, msg: str, line: int):
        super().__init__(msg)
        self.msg = msg
        self.line = line


class Entry:
    """key op value. key 가 None 이면 블록 안의 나열 항목(리스트 원소)."""

    __slots__ = ("key", "op", "value", "line")

    def __init__(self, key, op, value, line):
        self.key = key
        self.op = op
        self.value = value
        self.line = line

    @property
    def is_block(self) -> bool:
        return isinstance(self.value, list)

    def __repr__(self) -> str:
        return f"Entry({self.key!r}, {self.op!r}, line={self.line})"


def tokenize(text: str):
    tokens = []
    line = 1
    pos = 0
    n = len(text)
    while pos < n:
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise ParseError(f"해석할 수 없는 문자 {text[pos]!r}", line)
        kind = m.lastgroup
        val = m.group()
        if kind in ("ws", "comment"):
            line += val.count("\n")
        else:
            tokens.append((kind, val, line))
        pos = m.end()
    return tokens


def parse(tokens, top=True):
    """토큰 리스트를 Entry 트리로. 재귀 하강."""
    entries = []
    i = 0

    def parse_block(idx):
        """idx 는 '{' 다음 위치. (entries, 다음 idx) 반환."""
        out = []
        while idx < len(tokens):
            kind, val, ln = tokens[idx]
            if kind == "op" and val == "}":
                return out, idx + 1
            item, idx = parse_entry(idx)
            out.append(item)
        raise ParseError("닫히지 않은 '{'", tokens[-1][2] if tokens else 0)

    def parse_entry(idx):
        kind, val, ln = tokens[idx]
        if kind == "op" and val in ("{", "}"):
            if val == "{":
                # 이름 없는 중첩 블록 (예: 색상 리스트)
                block, idx = parse_block(idx + 1)
                return Entry(None, None, block, ln), idx
            raise ParseError("예상치 못한 '}'", ln)

        name = val[1:-1] if kind == "string" else val
        idx += 1

        if idx < len(tokens) and tokens[idx][0] == "op" and tokens[idx][1] not in ("{", "}"):
            op = tokens[idx][1]
            idx += 1
            if idx >= len(tokens):
                raise ParseError(f"'{name} {op}' 뒤에 값이 없다", ln)
            vkind, vval, vln = tokens[idx]
            if vkind == "op" and vval == "{":
                block, idx = parse_block(idx + 1)
                return Entry(name, op, block, ln), idx
            if vkind == "op":
                raise ParseError(f"'{name} {op}' 뒤에 값 대신 '{vval}' 이 왔다", vln)
            value = vval[1:-1] if vkind == "string" else vval
            return Entry(name, op, value, ln), idx + 1

        # 연산자가 없으면 나열 항목
        return Entry(None, None, name, ln), idx

    while i < len(tokens):
        kind, val, ln = tokens[i]
        if kind == "op" and val == "}":
            raise ParseError("짝 없는 '}'", ln)
        item, i = parse_entry(i)
        entries.append(item)
    return entries


def parse_file(path: Path):
    return parse(tokenize(path.read_text(encoding="utf-8")))


def walk(entries):
    for e in entries:
        yield e
        if e.is_block:
            yield from walk(e.value)


def children(entries, key):
    return [e for e in entries if e.key == key]


def scalar(entries, key, default=None):
    for e in entries:
        if e.key == key and not e.is_block:
            return e.value
    return default


# ---------------------------------------------------------------------------
# 리포트
# ---------------------------------------------------------------------------


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.notes = []

    def error(self, where, msg):
        self.errors.append((where, msg))

    def warn(self, where, msg):
        self.warnings.append((where, msg))

    def note(self, msg):
        self.notes.append(msg)

    def dump(self):
        for where, msg in self.errors:
            print(f"  ERROR  {where}: {msg}")
        for where, msg in self.warnings:
            print(f"  WARN   {where}: {msg}")
        for msg in self.notes:
            print(f"         {msg}")


# ---------------------------------------------------------------------------
# 검사
# ---------------------------------------------------------------------------


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def check_encoding(root: Path, rep: Report):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        name = rel(path, root)
        raw = path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        if path.suffix in (".txt", ".mod", ".gfx", ".gui"):
            if bom:
                rep.error(name, "BOM 이 붙어 있다. 스크립트 파일은 BOM 없는 UTF-8 이어야 한다")
                raw = raw[3:]
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                rep.error(name, f"UTF-8 이 아니다 (CP949/ANSI 추정): {exc}")
        elif path.suffix == ".yml":
            if not bom:
                rep.error(name, "로컬라이제이션 .yml 은 UTF-8 BOM 이 있어야 한다")
            try:
                raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                rep.error(name, f"UTF-8 이 아니다: {exc}")


def check_descriptors(mod_root: Path, outer_mod: Path, rep: Report):
    inner = mod_root / "descriptor.mod"
    if not inner.exists():
        rep.error("descriptor.mod", "모드 폴더 안에 descriptor.mod 가 없다")
    if not outer_mod.exists():
        rep.error(outer_mod.name, "폴더 옆 .mod 파일이 없다")
        return

    fields = {}
    for path, need_path in ((outer_mod, True), (inner, False)):
        if not path.exists():
            continue
        name = path.name
        try:
            entries = parse_file(path)
        except ParseError as exc:
            rep.error(name, f"{exc.line}행: {exc.msg}")
            continue
        for field in ("name", "supported_version"):
            if scalar(entries, field) is None:
                rep.error(name, f'{field}="..." 항목이 없다')
        fields[name] = {f: scalar(entries, f) for f in ("name", "version", "supported_version")}
        p = scalar(entries, "path")
        if p is None:
            if need_path:
                rep.error(name, 'path="mod/폴더명" 이 없다. 게임이 파일을 찾지 못한다')
        else:
            # path 가 있으면 어느 디스크립터든 같은 규칙을 적용한다.
            if "\\" in p:
                rep.error(name, f"path 에 역슬래시가 있다: {p}. 슬래시(/)여야 한다")
            if p.replace("\\", "/").split("/")[-1] != mod_root.name:
                rep.error(name, f"path 가 실제 폴더명과 다르다: {p} vs {mod_root.name}")
            if not p.isascii():
                rep.warn(name, f"path 에 비ASCII 문자가 있다: {p}")
            if not need_path:
                rep.warn(name, "폴더 안 descriptor.mod 에는 path= 가 없는 편이 안전하다")
        if scalar(entries, "archive") is not None and p is not None:
            rep.error(name, "archive= 와 path= 를 동시에 쓸 수 없다")

    # 두 디스크립터가 어긋나면 런처와 게임이 다른 값을 보게 된다.
    # 특히 supported_version 이 어긋나면 런처가 목록에는 띄우면서 플레이세트에서 조용히 뺀다.
    if len(fields) == 2:
        (n1, f1), (n2, f2) = fields.items()
        for field in ("name", "version", "supported_version"):
            if f1[field] != f2[field]:
                rep.error(
                    n1,
                    f"{field} 가 {n1}({f1[field]!r}) 과 {n2}({f2[field]!r}) 에서 다르다. "
                    "두 디스크립터는 같아야 한다",
                )
    sv = next((f["supported_version"] for f in fields.values() if f["supported_version"]), None)
    if sv:
        rep.note(f"supported_version = {sv} (게임 버전과 맞는지 launcher-settings.json 의 rawVersion 으로 확인)")


def load_scripts(mod_root: Path, rep: Report):
    """{상대경로: entries}. 파싱 실패는 오류로 기록하고 건너뛴다."""
    trees = {}
    for path in sorted(mod_root.rglob("*.txt")):
        name = rel(path, mod_root)
        try:
            trees[name] = parse_file(path)
        except ParseError as exc:
            rep.error(name, f"{exc.line}행: {exc.msg}")
        except UnicodeDecodeError as exc:
            rep.error(name, f"디코딩 실패: {exc}")
    return trees


def in_dir(trees, prefix):
    return {k: v for k, v in trees.items() if k.startswith(prefix)}


def check_focus_trees(trees, rep: Report):
    focuses = {}          # id -> (file, line)
    prereqs = defaultdict(set)
    exclusives = defaultdict(set)
    coords = defaultdict(list)
    tree_count = 0

    for name, entries in in_dir(trees, "common/national_focus/").items():
        for tree in children(entries, "focus_tree"):
            tree_count += 1
            tid = scalar(tree.value, "id")
            if not tid:
                rep.error(name, f"{tree.line}행: focus_tree 에 id 가 없다")
            country = [e for e in tree.value if e.key == "country" and e.is_block]
            if not country:
                rep.error(
                    name,
                    f"{tree.line}행: country 블록이 없다. 트리가 어떤 나라에도 배정되지 않아 "
                    "게임에서 영원히 보이지 않는다",
                )
            else:
                tags = [e.value for e in walk(country[0].value) if e.key == "tag"]
                if not tags:
                    rep.warn(name, f"{tree.line}행: country 블록에 tag 조건이 없다")
                else:
                    rep.note(f"{name}: focus_tree '{tid}' -> {', '.join(sorted(set(tags)))}")
            if scalar(tree.value, "default") == "yes":
                rep.warn(name, f"{tree.line}행: default = yes 다. 국가 전용 트리라면 no 여야 한다")

        for f in [e for e in walk(entries) if e.key == "focus" and e.is_block]:
            fid = scalar(f.value, "id")
            if not fid:
                rep.error(name, f"{f.line}행: focus 에 id 가 없다")
                continue
            if fid in focuses:
                rep.error(name, f"{f.line}행: focus id 중복 '{fid}' (앞서 {focuses[fid][0]})")
            focuses[fid] = (name, f.line)

            for p in children(f.value, "prerequisite"):
                if p.is_block:
                    prereqs[fid].update(e.value for e in p.value if e.key == "focus")
            for mx in children(f.value, "mutually_exclusive"):
                if mx.is_block:
                    exclusives[fid].update(e.value for e in mx.value if e.key == "focus")

            x, y = scalar(f.value, "x"), scalar(f.value, "y")
            if scalar(f.value, "relative_position_id") is None:
                if x is None or y is None:
                    rep.error(name, f"{f.line}행: '{fid}' 에 x/y 좌표가 없다")
                else:
                    coords[(x, y)].append(fid)
            if scalar(f.value, "cost") is None:
                rep.warn(name, f"{f.line}행: '{fid}' 에 cost 가 없다 (기본 10 = 70일)")
            if not children(f.value, "completion_reward"):
                rep.warn(name, f"{f.line}행: '{fid}' 에 completion_reward 가 없다")

    for fid, deps in list(prereqs.items()) + list(exclusives.items()):
        for dep in deps:
            if dep not in focuses:
                where = focuses.get(fid, ("?", 0))
                rep.error(where[0], f"{where[1]}행: '{fid}' 가 존재하지 않는 포커스 '{dep}' 를 참조한다")

    for (x, y), ids in coords.items():
        if len(ids) > 1:
            rep.warn("common/national_focus", f"좌표 ({x},{y}) 를 {len(ids)}개가 공유한다: {', '.join(ids)}")

    # 선행조건 순환
    state = {}

    def visit(node, stack):
        if state.get(node) == "done":
            return
        if state.get(node) == "open":
            rep.error("common/national_focus", f"선행조건 순환: {' -> '.join(stack + [node])}")
            return
        state[node] = "open"
        for dep in prereqs.get(node, ()):
            if dep in focuses:
                visit(dep, stack + [node])
        state[node] = "done"

    for fid in focuses:
        visit(fid, [])

    rep.note(f"포커스트리 {tree_count}개, 포커스 {len(focuses)}개")
    return focuses


def check_events(trees, rep: Report):
    namespaces = set()
    events = {}
    options = 0
    for name, entries in in_dir(trees, "events/").items():
        file_ns = {e.value for e in entries if e.key == "add_namespace"}
        if not file_ns:
            rep.error(name, "add_namespace 가 없다. 파일 전체가 거부된다")
        namespaces |= file_ns

        for ev in [e for e in entries if e.key and e.key.endswith("_event") and e.is_block]:
            eid = scalar(ev.value, "id")
            if not eid:
                rep.error(name, f"{ev.line}행: 이벤트에 id 가 없다")
                continue
            if eid in events:
                rep.error(name, f"{ev.line}행: 이벤트 id 중복 '{eid}'")
            events[eid] = (name, ev.line, ev.key)

            ns = eid.split(".")[0]
            if ns not in file_ns:
                rep.error(name, f"{ev.line}행: '{eid}' 의 namespace '{ns}' 가 이 파일에 선언되지 않았다")

            if scalar(ev.value, "title") is None:
                rep.error(name, f"{ev.line}행: '{eid}' 에 title 이 없다")
            opts = children(ev.value, "option")
            if not opts:
                rep.error(name, f"{ev.line}행: '{eid}' 에 option 이 없다. 클릭해도 닫히지 않는다")
            options += len(opts)
            for o in opts:
                if o.is_block and scalar(o.value, "name") is None:
                    rep.error(name, f"{o.line}행: '{eid}' 의 option 에 name 이 없다")

            triggered = scalar(ev.value, "is_triggered_only") == "yes"
            has_trigger = bool(children(ev.value, "trigger"))
            has_mtth = bool(children(ev.value, "mean_time_to_happen"))
            if not triggered and not has_trigger and not has_mtth:
                rep.warn(
                    name,
                    f"{ev.line}행: '{eid}' 가 is_triggered_only 도 trigger 도 아니다. "
                    "매일 모든 나라에 발동한다",
                )
    rep.note(f"이벤트 {len(events)}개 / 선택지 {options}개 / namespace {', '.join(sorted(namespaces))}")
    return events


def check_decisions(trees, rep: Report):
    defined = {}
    for name, entries in in_dir(trees, "common/decisions/categories/").items():
        for cat in [e for e in entries if e.key and e.is_block]:
            defined[cat.key] = name

    used = {}
    for name, entries in in_dir(trees, "common/decisions/").items():
        if "/categories/" in name:
            continue
        for cat in [e for e in entries if e.key and e.is_block]:
            used.setdefault(cat.key, (name, cat.line))
            for dec in [e for e in cat.value if e.key and e.is_block]:
                if not children(dec.value, "allowed"):
                    rep.warn(name, f"{dec.line}행: '{dec.key}' 에 allowed 가 없다. 모든 나라에 노출된다")
                if not (children(dec.value, "complete_effect") or children(dec.value, "remove_effect")):
                    rep.warn(name, f"{dec.line}행: '{dec.key}' 에 효과가 없다")

    for cat, (name, line) in used.items():
        if cat not in defined:
            rep.error(
                name,
                f"{line}행: 카테고리 '{cat}' 가 common/decisions/categories/ 에 정의되지 않았다. "
                "바닐라 카테고리가 아니면 디시전 탭에 아무것도 뜨지 않는다",
            )
    rep.note(f"디시전 카테고리 정의 {len(defined)}개 / 사용 {len(used)}개")
    return defined, used


def collect_names(trees, prefix, depth):
    """prefix 아래 파일에서 지정한 깊이의 블록 키를 모은다."""
    found = {}

    def rec(entries, level, file):
        for e in entries:
            if not (e.key and e.is_block):
                continue
            if level == depth:
                found.setdefault(e.key, (file, e.line))
            else:
                rec(e.value, level + 1, file)

    for name, entries in in_dir(trees, prefix).items():
        rec(entries, 0, name)
    return found


def check_ideas_and_characters(trees, rep: Report):
    ideas = {}
    for name, entries in in_dir(trees, "common/ideas/").items():
        for root in children(entries, "ideas"):
            if not root.is_block:
                continue
            for slot in [e for e in root.value if e.key and e.is_block]:
                for idea in [e for e in slot.value if e.key and e.is_block]:
                    if idea.key in ideas:
                        rep.error(name, f"{idea.line}행: 이념 id 중복 '{idea.key}'")
                    ideas[idea.key] = (name, idea.line, slot.key)

    chars = {}
    tokens = {}
    for name, entries in in_dir(trees, "common/characters/").items():
        for root in children(entries, "characters"):
            if not root.is_block:
                continue
            for ch in [e for e in root.value if e.key and e.is_block]:
                chars[ch.key] = (name, ch.line)
                if scalar(ch.value, "name") is None:
                    rep.error(name, f"{ch.line}행: 캐릭터 '{ch.key}' 에 name 이 없다")
                for adv in children(ch.value, "advisor"):
                    if not adv.is_block:
                        continue
                    tok = scalar(adv.value, "idea_token")
                    if tok is None:
                        rep.error(name, f"{adv.line}행: '{ch.key}' 의 advisor 에 idea_token 이 없다")
                    else:
                        if tok in tokens:
                            rep.error(name, f"{adv.line}행: idea_token 중복 '{tok}'")
                        tokens[tok] = ch.key
                    if scalar(adv.value, "slot") is None:
                        rep.error(name, f"{adv.line}행: '{ch.key}' 의 advisor 에 slot 이 없다")
                    if not children(adv.value, "allowed"):
                        rep.warn(name, f"{adv.line}행: '{ch.key}' 의 advisor 에 allowed 가 없다")
    return ideas, chars, tokens


MOD_PREFIXES = ("KOR_", "JAP_")


def check_scripted(trees, rep: Report):
    """common/scripted_effects, scripted_triggers 에 정의된 이름을 모은다."""
    defined = {}
    for prefix in ("common/scripted_effects/", "common/scripted_triggers/"):
        for name, entries in in_dir(trees, prefix).items():
            for e in entries:
                if not (e.key and e.is_block):
                    continue
                if e.key in defined:
                    rep.error(name, f"{e.line}행: 이름 중복 '{e.key}' (앞서 {defined[e.key][0]})")
                defined[e.key] = (name, e.line)
    if defined:
        rep.note(f"scripted effect/trigger {len(defined)}개: {', '.join(sorted(defined))}")
    return defined


def check_references(trees, focuses, events, ideas, chars, tokens, scripted, rep: Report):
    """스크립트 전체에서 효과 참조를 모아 정의와 대조한다."""
    set_flags = defaultdict(set)
    checked_flags = defaultdict(set)
    ev_refs = []
    idea_refs = []
    has_idea_refs = []
    added_ideas = set()
    focus_refs = []
    char_refs = []
    tree_refs = []
    effect_calls = []

    for name, entries in trees.items():
        for e in walk(entries):
            k, v = e.key, e.value
            if k is None:
                continue
            if k in ("country_event", "news_event", "state_event", "unit_leader_event"):
                eid = scalar(v, "id") if e.is_block else v
                if eid:
                    ev_refs.append((eid, name, e.line))
            elif k in ("add_ideas", "remove_ideas", "swap_ideas", "add_timed_idea"):
                adding = k in ("add_ideas", "add_timed_idea")
                if e.is_block:
                    for sub in walk(v):
                        if sub.key in ("add_idea", "remove_idea", "idea") and not sub.is_block:
                            idea_refs.append((sub.value, name, sub.line))
                            if sub.key == "add_idea" or (adding and sub.key == "idea"):
                                added_ideas.add(sub.value)
                        elif sub.key is None and isinstance(sub.value, str):
                            idea_refs.append((sub.value, name, sub.line))
                            if adding:
                                added_ideas.add(sub.value)
                else:
                    idea_refs.append((v, name, e.line))
                    if adding:
                        added_ideas.add(v)
            elif k == "has_idea":
                iid = scalar(v, "idea") if e.is_block else v
                if iid:
                    has_idea_refs.append((iid, name, e.line))
            elif k in ("complete_national_focus", "unlock_national_focus") and not e.is_block:
                focus_refs.append((v, name, e.line))
            elif k in ("recruit_character", "promote_character", "retire_character") and not e.is_block:
                char_refs.append((v, name, e.line))
            elif k == "load_focus_tree":
                tid = scalar(v, "tree") if e.is_block else v
                if tid:
                    tree_refs.append((tid, name, e.line))
            elif k in ("set_country_flag", "set_global_flag"):
                flag = scalar(v, "flag") if e.is_block else v
                if flag:
                    set_flags[k].add(flag)
            elif k in ("has_country_flag", "has_global_flag"):
                flag = scalar(v, "flag") if e.is_block else v
                if flag:
                    checked_flags[k].add(flag)
            elif not e.is_block and v == "yes" and k.startswith(MOD_PREFIXES):
                # 모드 접두사가 붙은 'X = yes' 는 scripted effect/trigger 호출이다.
                effect_calls.append((k, name, e.line))

    for eid, name, line in ev_refs:
        if eid not in events:
            rep.error(name, f"{line}행: 존재하지 않는 이벤트 '{eid}' 를 발동한다")
    for iid, name, line in idea_refs:
        if iid not in ideas:
            rep.error(name, f"{line}행: 정의되지 않은 이념 '{iid}' 를 추가한다")

    # has_idea 오타는 조건을 영원히 거짓으로 만든다. 효과가 안 걸린 채 조용히 지나간다.
    for iid, name, line in has_idea_refs:
        if iid.startswith(MOD_PREFIXES) and iid not in ideas and iid not in tokens:
            rep.error(
                name,
                f"{line}행: 정의되지 않은 이념 '{iid}' 를 has_idea 로 검사한다. "
                "조건이 영원히 거짓이라 안쪽 효과가 실행되지 않는다",
            )

    for iid, (fname, line, _slot) in ideas.items():
        if iid in tokens:
            continue  # 어드바이저 토큰은 add_ideas 로 붙이지 않는다
        if iid not in added_ideas:
            rep.warn(fname, f"{line}행: 이념 '{iid}' 를 정의했지만 어디서도 추가하지 않는다")
    for fid, name, line in focus_refs:
        if fid not in focuses:
            rep.error(name, f"{line}행: 존재하지 않는 포커스 '{fid}' 를 참조한다")
    for cid, name, line in char_refs:
        if cid not in chars:
            rep.error(name, f"{line}행: 정의되지 않은 캐릭터 '{cid}' 를 참조한다")

    for sid, name, line in effect_calls:
        if sid not in scripted:
            rep.error(
                name,
                f"{line}행: 정의되지 않은 scripted effect '{sid}' 를 호출한다. "
                "게임은 이 줄을 조용히 무시한다",
            )
    called = {s for s, _, _ in effect_calls}
    for sid, (fname, line) in scripted.items():
        if sid not in called:
            rep.warn(fname, f"{line}행: scripted effect '{sid}' 를 정의했지만 아무도 호출하지 않는다")

    tree_ids = set()
    for name, entries in in_dir(trees, "common/national_focus/").items():
        for t in children(entries, "focus_tree"):
            tid = scalar(t.value, "id")
            if tid:
                tree_ids.add(tid)
    for tid, name, line in tree_refs:
        if tid not in tree_ids:
            rep.error(name, f"{line}행: 존재하지 않는 포커스트리 '{tid}' 를 로드한다")

    for kind, checker in (("set_country_flag", "has_country_flag"), ("set_global_flag", "has_global_flag")):
        for flag in sorted(checked_flags[checker] - set_flags[kind]):
            rep.warn("flags", f"'{flag}' 를 {checker} 로 검사하지만 어디서도 {kind} 하지 않는다")
        for flag in sorted(set_flags[kind] - checked_flags[checker]):
            rep.note(f"플래그 '{flag}' 는 설정만 하고 검사하지 않는다 (의도적일 수 있음)")


LOC_LINE = re.compile(r'^\s*([\w.\-]+):\s*\d*\s*"(.*)"\s*$')


def check_localisation(mod_root: Path, focuses, events, trees, ideas, chars, cats, rep: Report):
    keys = {}
    for path in sorted((mod_root / "localisation").rglob("*.yml")):
        name = rel(path, mod_root)
        text = path.read_bytes().decode("utf-8-sig")
        lines = text.splitlines()
        if not lines or not re.match(r"^\s*l_\w+:\s*$", lines[0]):
            rep.error(name, f"첫 줄이 'l_english:' 형태가 아니다: {lines[0][:40] if lines else '(빈 파일)'}")
        if not re.search(r"_l_\w+\.yml$", path.name):
            rep.error(name, "파일명이 '..._l_english.yml' 형식이어야 한다")
        for i, line in enumerate(lines[1:], start=2):
            if not line.strip() or line.strip().startswith("#"):
                continue
            m = LOC_LINE.match(line)
            if not m:
                rep.error(name, f"{i}행: 해석 불가. 형식은 ' KEY:0 \"값\"' 이다 -> {line.strip()[:50]}")
                continue
            key, val = m.group(1), m.group(2)
            if key in keys:
                rep.error(name, f"{i}행: 로컬라이제이션 키 중복 '{key}' (앞서 {keys[key]})")
            keys[key] = f"{name}:{i}"
            if not val.strip():
                rep.warn(name, f"{i}행: '{key}' 의 값이 비어 있다")

    required = set()
    for fid in focuses:
        required |= {fid, fid + "_desc"}
    for eid, (_, _, kind) in events.items():
        required |= {eid + ".t", eid + ".d"}
    for name, entries in trees.items():
        for e in walk(entries):
            if e.key == "option" and e.is_block:
                opt = scalar(e.value, "name")
                if opt:
                    required.add(opt)
    for iid in ideas:
        required |= {iid, iid + "_desc"}
    for name, entries in in_dir(trees, "common/characters/").items():
        for e in walk(entries):
            if e.key == "name" and not e.is_block and e.value.startswith(("KOR_", "JAP_")):
                required.add(e.value)
    for cat in cats:
        required.add(cat)
    for name, entries in in_dir(trees, "common/decisions/").items():
        if "/categories/" in name:
            continue
        for cat in [e for e in entries if e.key and e.is_block]:
            for dec in [e for e in cat.value if e.key and e.is_block]:
                required |= {dec.key, dec.key + "_desc"}

    missing = sorted(required - set(keys))
    # localisation/replace/ 는 바닐라 키를 의도적으로 덮어쓰는 곳이라 '미사용' 이 정상이다.
    unused = sorted(
        k for k in set(keys) - required
        if not keys[k].startswith("localisation/replace/")
    )
    overrides = sorted(k for k in keys if keys[k].startswith("localisation/replace/"))
    if overrides:
        rep.note(f"바닐라 로컬라이제이션 덮어쓰기 {len(overrides)}개: {', '.join(overrides)}")
    for k in missing:
        rep.error("localisation", f"키 누락: {k}")
    for k in unused:
        rep.warn("localisation", f"쓰이지 않는 키: {k} ({keys[k]})")
    rep.note(f"로컬라이제이션 키 {len(keys)}개 / 필요 {len(required)}개")


def collect_gfx(trees, rep: Report):
    gfx = defaultdict(set)
    for name, entries in trees.items():
        for e in walk(entries):
            if e.key in ("icon", "picture", "small", "large", "sprite", "texturefile") and not e.is_block:
                gfx[e.key].add(e.value)
    total = sum(len(v) for v in gfx.values())
    rep.note(f"GFX 참조 {total}개 (게임 파일 없이는 유효성 확인 불가, error.log 로 확인할 것)")
    for kind in sorted(gfx):
        rep.note(f"  {kind}: {', '.join(sorted(gfx[kind]))}")

    templates = set()
    for name, entries in trees.items():
        for e in walk(entries):
            if e.key == "division_template" and not e.is_block:
                templates.add(e.value)
    if templates:
        rep.note(
            f"사단 템플릿 참조 {len(templates)}개 (바닐라 이름이라 확인 불가, error.log 로 대조할 것): "
            + ", ".join(f'"{t}"' for t in sorted(templates))
        )


# ---------------------------------------------------------------------------

def main(argv):
    mod_root = Path(argv[1]) if len(argv) > 1 else Path("mod/daegyunyeol")
    if not mod_root.is_dir():
        print(f"모드 폴더를 찾을 수 없다: {mod_root}")
        return 1
    outer_mod = mod_root.parent / f"{mod_root.name}.mod"

    rep = Report()
    print(f"검증 대상: {mod_root}\n")

    check_encoding(mod_root, rep)
    check_descriptors(mod_root, outer_mod, rep)
    trees = load_scripts(mod_root, rep)

    focuses = check_focus_trees(trees, rep)
    events = check_events(trees, rep)
    cats, _ = check_decisions(trees, rep)
    ideas, chars, tokens = check_ideas_and_characters(trees, rep)
    scripted = check_scripted(trees, rep)
    check_references(trees, focuses, events, ideas, chars, tokens, scripted, rep)
    check_localisation(mod_root, focuses, events, trees, ideas, chars, cats, rep)
    collect_gfx(trees, rep)

    rep.note(f"이념 {len(ideas)}개 / 캐릭터 {len(chars)}개 / 어드바이저 {len(tokens)}개")

    rep.dump()
    print()
    print(f"  파일 {len(trees)}개 파싱, 오류 {len(rep.errors)}개, 경고 {len(rep.warnings)}개")
    return min(len(rep.errors), 100)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
