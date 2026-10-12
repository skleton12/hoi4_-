"""구성 데이터를 트리 그림으로 그린다.

    python3 design/generic_tree/render.py

data/*.json 하나당 img/<파일이름>.png 한 장, 그리고 전체 지도 img/00_overview.png 를 만든다.
아직 비어 있는 소갈래는 '미정' 칸으로 자리만 그려서 틀의 크기를 볼 수 있게 한다.
Pillow 와 한글 글꼴만 있으면 된다.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
DATA = HERE / "data"
OUT = HERE / "img"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]

BG = "#1b1d22"
TEXT = "#f2f2f2"
MUTED = "#8b919c"
LINE = "#6c727d"
EXCL = "#e0524a"
COND = "#e3b34a"
PENDING_FILL = "#262930"

BRANCH_COLORS = {
    "start": "#5b6b7a",
    "industry": "#9a6a2f",
    "military": "#5f7a3a",
    "politics": "#7a3f5f",
    "diplomacy": "#2f6a8a",
    "terrain": "#3f7a72",
    "independence": "#8a4a2f",
    "culture": "#5a4f8a",
    "late": "#6a6a6a",
}

NODE_W, NODE_H = 184, 74
COL = NODE_W + 34
ROW = NODE_H + 22
HEADER = 58
MARGIN = 48
TOP = 120
SPLIT_WIDTH = 6000  # 이보다 넓은 갈래 그림은 최상위 소갈래별로도 나눠 저장한다


def font(size):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit("한글 글꼴을 찾지 못했다. FONT_CANDIDATES 에 경로를 추가할 것.")


F_TITLE, F_SUB, F_HEAD, F_NAME, F_SMALL = font(34), font(18), font(16), font(15), font(12)


def wrap(text, f, width, max_lines):
    lines, cur = [], ""
    for ch in text:
        if f.getlength(cur + ch) > width:
            lines.append(cur)
            cur = ch.lstrip()
        else:
            cur += ch
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:-1] + "…"
    return lines


def bold(draw, xy, text, f, fill):
    x, y = xy
    draw.text((x, y), text, font=f, fill=fill)
    draw.text((x + 1, y), text, font=f, fill=fill)


def load():
    branches = []
    for path in sorted(DATA.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_file"] = path.stem
        branches.append(data)
    return branches


# ---------------------------------------------------------------- 배치

def parents_of(g):
    """after 는 id 하나이거나, '이 중 하나 완료' 를 뜻하는 id 목록이다."""
    a = g["after"]
    return [] if not a else ([a] if isinstance(a, str) else list(a))


def size(g):
    return len(g["focuses"]) or g["target"]


def layout(groups):
    """소갈래마다 (가운데 열, 머리 y) 를 정한다. 자식 소갈래는 부모 아래에 나란히 놓는다.

    after 가 목록인 소갈래(합류)는 그 부모들의 공통 부모 밑에 두되,
    부모들이 모두 끝난 높이 아래 줄에 따로 놓는다.
    """
    by_id = {g["id"]: g for g in groups}
    children = {g["id"]: [] for g in groups}
    joins = {g["id"]: [] for g in groups}
    roots = []
    for g in groups:
        ps = parents_of(g)
        if not ps:
            roots.append(g)
        elif len(ps) == 1:
            children[ps[0]].append(g)
        else:
            joins[by_id[ps[0]]["after"]].append(g)

    span = {}

    def measure(g):
        normal = sum(measure(k) for k in children[g["id"]])
        joined = sum(measure(k) for k in joins[g["id"]])
        span[g["id"]] = max(1, normal, joined)
        return span[g["id"]]

    for r in roots:
        measure(r)

    pos = {}

    def end_y(g):
        return pos[g["id"]][1] + HEADER + size(g) * ROW + 10

    def place(g, left, y):
        pos[g["id"]] = (left + (span[g["id"]] - 1) / 2, y)
        child_y = y + HEADER + size(g) * ROW + 10
        x = left + (span[g["id"]] - sum(span[k["id"]] for k in children[g["id"]])) / 2
        for k in children[g["id"]]:
            place(k, x, child_y)
            x += span[k["id"]]
        x = left
        for k in joins[g["id"]]:
            place(k, x, max(end_y(by_id[p]) for p in parents_of(k)) + 14)
            x += span[k["id"]]

    left = 0
    for r in roots:
        place(r, left, TOP + 70)
        left += span[r["id"]]
    return pos, left


def node_box(col, y):
    x = MARGIN + col * COL
    return x, y, x + NODE_W, y + NODE_H


def draw_node(d, box, focus, color, index, total):
    x0, y0, x1, y1 = box
    if focus is None:
        d.rounded_rectangle(box, 8, fill=PENDING_FILL, outline=LINE, width=1)
        d.text((x0 + 12, y0 + 27), f"미정  {index}/{total}", font=F_NAME, fill=MUTED)
        return
    d.rounded_rectangle(box, 8, fill=color, outline="#000000", width=1)
    lines = wrap(focus["name"], F_NAME, NODE_W - 20, 2)
    y = y0 + 8
    for line in lines:
        bold(d, (x0 + 10, y), line, F_NAME, TEXT)
        y += 19
    for line in wrap(focus["effect"], F_SMALL, NODE_W - 20, 4 - len(lines)):
        d.text((x0 + 10, y + 2), line, font=F_SMALL, fill="#dcdcdc")
        y += 15
    days = f"{focus['days']}일"
    d.text((x1 - 8 - F_SMALL.getlength(days), y1 - 17), days, font=F_SMALL, fill="#c8c8c8")


def render_branch(branch):
    groups = branch["groups"]
    color = BRANCH_COLORS.get(branch["branch"], "#555555")
    pos, cols = layout(groups)
    by_id = {g["id"]: g for g in groups}

    bottom = max(y + HEADER + (len(g["focuses"]) or g["target"]) * ROW for g in groups for _, y in [pos[g["id"]]])
    width = max(MARGIN * 2 + cols * COL, 900)
    height = bottom + 90
    img = Image.new("RGB", (int(width), int(height)), BG)
    d = ImageDraw.Draw(img)

    done = sum(len(g["focuses"]) for g in groups)
    total = sum(g["target"] for g in groups)
    bold(d, (MARGIN, 30), branch["title"], F_TITLE, TEXT)
    d.text((MARGIN + F_TITLE.getlength(branch["title"]) + 20, 44),
           f"{total}칸 · 작성 {done}/{total}", font=F_SUB, fill=MUTED)

    # 뿌리 띠: 갈래 이름에서 최상위 소갈래로 선을 내린다
    root_y = TOP + 70
    bar_y = TOP + 40
    roots = [g for g in groups if not g["after"]]
    if len(roots) > 1:
        xs = [MARGIN + pos[g["id"]][0] * COL + NODE_W / 2 for g in roots]
        d.line((xs[0], bar_y, xs[-1], bar_y), fill=LINE, width=2)
        for x in xs:
            d.line((x, bar_y, x, root_y), fill=LINE, width=2)

    # 소갈래
    for g in groups:
        col, y = pos[g["id"]]
        cx = MARGIN + col * COL + NODE_W / 2
        x0 = MARGIN + col * COL
        bold(d, (x0, y + 4), g["title"], F_HEAD, TEXT)
        meta = []
        if g["condition"]:
            meta.append((f"조건: {g['condition']}", COND))
        if g["exclusive"]:
            meta.append(("↔ 상호배타", EXCL))
        mx = x0
        for text, fill in meta:
            d.text((mx, y + 27), text, font=F_SMALL, fill=fill)
            mx += F_SMALL.getlength(text) + 10

        n = len(g["focuses"]) or g["target"]
        first_y = y + HEADER
        for i in range(n):
            ny = first_y + i * ROW
            if i:
                d.line((cx, ny - (ROW - NODE_H), cx, ny), fill=LINE, width=2)
            focus = g["focuses"][i] if g["focuses"] else None
            draw_node(d, node_box(col, ny), focus, color, i + 1, n)

        ps = parents_of(g)
        for pid in ps:
            parent = by_id[pid]
            pcol, py = pos[pid]
            pbottom = py + HEADER + (size(parent) - 1) * ROW + NODE_H
            pcx = MARGIN + pcol * COL + NODE_W / 2
            mid = pbottom + 6 if len(ps) == 1 else y - 8
            d.line((pcx, pbottom, pcx, mid), fill=LINE, width=2)
            d.line((pcx, mid, cx, mid), fill=LINE, width=2)
            d.line((cx, mid, cx, y), fill=LINE, width=2)
        if len(ps) > 1:
            d.text((cx + 6, y - 26), "둘 중 하나", font=F_SMALL, fill=MUTED)

    # 상호배타: 같은 태그를 가진 형제 소갈래의 머리를 빨간 선으로 묶는다
    tags = {}
    for g in groups:
        if g["exclusive"]:
            tags.setdefault((g["exclusive"], str(g["after"])), []).append(g)
    for members in tags.values():
        if len(members) < 2:
            continue
        xs = [MARGIN + pos[g["id"]][0] * COL for g in members]
        y = pos[members[0]["id"]][1] - 2
        d.line((min(xs), y, max(xs) + NODE_W, y), fill=EXCL, width=3)

    # 범례
    ly = height - 40
    items = [("■ 작성된 칸", color), ("■ 미정 칸", PENDING_FILL), ("━ 상호배타 묶음", EXCL), ("조건: 보이는 조건", COND)]
    lx = MARGIN
    for text, fill in items:
        d.text((lx, ly), text, font=F_SMALL, fill=fill if fill != PENDING_FILL else MUTED)
        lx += F_SMALL.getlength(text) + 28

    path = OUT / f"{branch['_file']}.png"
    img.save(path)
    if width > SPLIT_WIDTH:
        split_branch(branch, groups, pos, img)
    return path


def split_branch(branch, groups, pos, img):
    """너무 넓은 갈래는 최상위 소갈래(예: 이념)마다 잘라 따로 저장한다.

    좁은 최상위 소갈래들(숨은 길 등)은 하나로 묶는다. 파일 이름은 <갈래>_<번호>.png.
    """
    by_id = {g["id"]: g for g in groups}

    def root_of(g):
        while parents_of(g):
            g = by_id[parents_of(g)[0]]
        return g["id"]

    cols = {}
    for g in groups:
        cols.setdefault(root_of(g), []).append(pos[g["id"]][0])
    parts = []
    for g in groups:
        if parents_of(g) or g["id"] not in cols:
            continue
        lo, hi = min(cols[g["id"]]), max(cols[g["id"]])
        title = g["title"]
        if parts and hi - lo < 3 and parts[-1][3]:
            parts[-1] = (parts[-1][0], hi, parts[-1][2] + " · " + title, True)
        else:
            parts.append((lo, hi, title, hi - lo < 3))
    h = img.height
    for i, (lo, hi, title, _) in enumerate(parts, 1):
        x0 = max(0, int(MARGIN + lo * COL - 20))
        x1 = min(img.width, int(MARGIN + hi * COL + NODE_W + 20))
        part = Image.new("RGB", (max(x1 - x0, 900), h), BG)
        part.paste(img.crop((x0, 0, x1, h)), (0, 0))
        d = ImageDraw.Draw(part)
        d.rectangle((0, 0, part.width, 100), fill=BG)
        bold(d, (MARGIN, 30), f"{branch['title']} — {title}", F_TITLE, TEXT)
        part.save(OUT / f"{branch['_file']}_{i}.png")


# ---------------------------------------------------------------- 전체 지도

def summary_rows(groups):
    """전체 지도에 띄울 소갈래만 고른다.

    뿌리·1단계·상호배타·자식이 있는 소갈래만 한 줄씩 보이고, 나머지 잎 소갈래는
    가장 가까운 보이는 조상의 칸 수에 합친다. (그룹, 깊이, 작성 칸, 목표 칸) 목록.
    """
    by_id = {g["id"]: g for g in groups}
    parents = {p for g in groups for p in parents_of(g)}
    depth = {}
    for g in groups:
        ps = parents_of(g)
        depth[g["id"]] = depth[ps[0]] + 1 if ps else 0

    def shown(g):
        return depth[g["id"]] <= 1 or g["exclusive"] or g["id"] in parents

    owner = {}
    for g in groups:
        o = g
        while not shown(o):
            o = by_id[parents_of(o)[0]]
        owner[g["id"]] = o["id"]

    rows = []
    for g in groups:
        if not shown(g):
            continue
        members = [x for x in groups if owner[x["id"]] == g["id"]]
        rows.append((g, depth[g["id"]], sum(len(x["focuses"]) for x in members), sum(x["target"] for x in members)))
    return rows


def render_overview(branches):
    card_w, pad = 420, 28
    cols = 3
    line_h = 22
    cards = []
    for b in branches:
        h = 96 + line_h * len(summary_rows(b["groups"])) + 20
        cards.append((b, h))
    rows = [cards[i:i + cols] for i in range(0, len(cards), cols)]
    row_h = [max(h for _, h in r) for r in rows]

    width = MARGIN * 2 + cols * card_w + (cols - 1) * pad
    height = 150 + sum(row_h) + pad * (len(rows) - 1) + 70
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    total = sum(g["target"] for b in branches for g in b["groups"])
    done = sum(len(g["focuses"]) for b in branches for g in b["groups"])
    bold(d, (MARGIN, 30), "기본 중점 확장 — 전체 지도", F_TITLE, TEXT)
    d.text((MARGIN, 82), f"총 {total}칸 · 작성 {done}/{total} · 갈래 {len(branches)}개", font=F_SUB, fill=MUTED)

    y = 150
    for r, rh in zip(rows, row_h):
        x = MARGIN
        for b, _ in r:
            color = BRANCH_COLORS.get(b["branch"], "#555555")
            d.rounded_rectangle((x, y, x + card_w, y + rh), 12, fill="#23262d", outline=color, width=3)
            d.rounded_rectangle((x, y, x + card_w, y + 52), 12, fill=color)
            d.rectangle((x, y + 40, x + card_w, y + 52), fill=color)
            bt = sum(g["target"] for g in b["groups"])
            bd = sum(len(g["focuses"]) for g in b["groups"])
            bold(d, (x + 16, y + 12), b["title"], F_SUB, TEXT)
            label = f"{bt}칸"
            bold(d, (x + card_w - 16 - F_SUB.getlength(label), y + 12), label, F_SUB, TEXT)

            # 작성 진행 막대
            d.rectangle((x + 16, y + 64, x + card_w - 16, y + 72), fill=PENDING_FILL)
            if bd:
                d.rectangle((x + 16, y + 64, x + 16 + (card_w - 32) * bd / bt, y + 72), fill=color)

            gy = y + 86
            for g, level, done_n, target_n in summary_rows(b["groups"]):
                gx = x + 18 + level * 18
                prefix = "└ " if level else "· "
                d.text((gx, gy), prefix + g["title"], font=F_SMALL, fill=TEXT)
                tx = gx + F_SMALL.getlength(prefix + g["title"]) + 8
                if g["exclusive"]:
                    d.text((tx, gy), "↔", font=F_SMALL, fill=EXCL)
                    tx += 16
                if g["condition"]:
                    d.text((tx, gy), g["condition"], font=F_SMALL, fill=COND)
                count = f"{done_n}/{target_n}"
                d.text((x + card_w - 18 - F_SMALL.getlength(count), gy), count, font=F_SMALL, fill=MUTED)
                gy += line_h
            x += card_w + pad
        y += rh + pad

    d.text((MARGIN, height - 44), "↔ 상호배타 (하나만 고름)    노란 글씨: 보이는 조건    n/m: 작성 칸 / 목표 칸",
           font=F_SMALL, fill=MUTED)
    path = OUT / "00_overview.png"
    img.save(path)
    return path


def main():
    OUT.mkdir(exist_ok=True)
    branches = load()
    print(render_overview(branches).relative_to(HERE))
    for b in branches:
        print(render_branch(b).relative_to(HERE))


if __name__ == "__main__":
    main()
