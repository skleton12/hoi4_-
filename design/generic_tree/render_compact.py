"""GPT 담당 트리를 가로 묶음으로 렌더링한다. 데이터와 선행 관계는 유지한다.

    python design/generic_tree/render_compact.py

각 소갈래를 네 칸씩 접어 그리며, 공통 선행과 선택지를 나란히 배치한다.
기존 render.py와 Claude 담당 이미지는 수정하지 않는다.
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

import render as style

HERE = Path(__file__).parent
FILES = ("02_industry", "03_military", "06_terrain", "07_independence", "09_late")
OUT = HERE / "img"
COLS = 4
NW, NH = 164, 78
GX, GY = 16, 24
PAD, HEAD = 16, 72
CW = PAD * 2 + COLS * NW + (COLS - 1) * GX
GAP, MARGIN, TOP = 36, 48, 152
NAME = style.font(15)
SMALL = style.font(12)
LABEL = style.font(17)


def arrow(draw, start, end, color=style.LINE, width=2):
    draw.line((*start, *end), fill=color, width=width)
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if not length:
        return
    ux, uy = dx / length, dy / length
    x, y = end
    draw.polygon([(x, y), (x - 6 * ux + 3 * uy, y - 6 * uy - 3 * ux),
                  (x - 6 * ux - 3 * uy, y - 6 * uy + 3 * ux)], fill=color)


def count(g):
    return len(g["focuses"]) or g["target"]


def card_height(g):
    return HEAD + math.ceil(count(g) / COLS) * (NH + GY) + PAD


def forest_layout(groups):
    """독립된 육/해/공 뿌리는 별도 행, 부모와 자식은 같은 행으로 배치한다."""
    by_id = {g["id"]: g for g in groups}
    children = {g["id"]: [] for g in groups}
    roots = []
    for g in groups:
        if g["after"]:
            children[g["after"]].append(g)
        else:
            roots.append(g)
    positions = {}
    y = TOP
    max_x = MARGIN

    if all(not children[g["id"]] for g in roots):
        # 지형/후반은 독립 패널을 좌우로 놓는다.
        for i, g in enumerate(roots):
            positions[g["id"]] = (MARGIN + i * (CW + GAP), y)
        y += max(card_height(g) for g in roots) + GAP
        max_x = MARGIN + len(roots) * (CW + GAP) - GAP
    else:
        for root in roots:
            row = [root] + children[root["id"]]
            for i, g in enumerate(row):
                positions[g["id"]] = (MARGIN + i * (CW + GAP), y)
            bottom = y + max(card_height(g) for g in row)
            max_x = max(max_x, MARGIN + len(row) * (CW + GAP) - GAP)

            def place_descendants(parent):
                nonlocal bottom
                px, py = positions[parent["id"]]
                next_y = py + card_height(parent) + GAP
                for child in children[parent["id"]]:
                    positions[child["id"]] = (px, next_y)
                    next_y += card_height(child) + GAP
                    bottom = max(bottom, next_y - GAP)
                    place_descendants(child)

            for g in row[1:]:
                place_descendants(g)
            y = bottom + 68
    assert set(positions) == set(by_id), "누락된 소갈래"
    return positions, int(max_x + MARGIN), int(y + 36)


def paint_group(draw, group, pos, color, by_id):
    x, y = pos
    height = card_height(group)
    draw.rounded_rectangle((x, y, x + CW, y + height), 12,
                           fill="#23262d", outline=color, width=2)
    title = f"{group['title']} · {count(group)}칸"
    style.bold(draw, (x + PAD, y + 10), title, LABEL, style.TEXT)
    if group["after"]:
        label = f"선행: {by_id[group['after']]['title']} 완료"
    else:
        label = "독립 시작"
    if group["exclusive"]:
        label += "  |  ↔ 한 갈래 선택"
    draw.text((x + PAD, y + 35), label, font=SMALL,
              fill=style.EXCL if group["exclusive"] else style.MUTED)
    if group["condition"]:
        draw.text((x + PAD, y + 52), "조건: " + group["condition"],
                  font=SMALL, fill=style.COND)
    boxes = []
    for i in range(count(group)):
        row, slot = divmod(i, COLS)
        col = slot if row % 2 == 0 else COLS - 1 - slot
        nx, ny = x + PAD + col * (NW + GX), y + HEAD + row * (NH + GY)
        box = (nx, ny, nx + NW, ny + NH)
        boxes.append(box)
        focus = group["focuses"][i] if group["focuses"] else None
        draw.rounded_rectangle(box, 7, fill=color if focus else style.PENDING_FILL,
                               outline="#111318")
        if focus:
            # 이름/효과/기간의 영역을 분리해 긴 문구도 겹치지 않게 한다.
            lines = style.wrap(focus["name"], NAME, NW - 16, 2)
            for j, line in enumerate(lines):
                style.bold(draw, (nx + 8, ny + 6 + j * 17), line, NAME, style.TEXT)
            effect_y = ny + 8 + len(lines) * 17
            max_lines = 2 if len(lines) == 1 else 1
            for j, line in enumerate(style.wrap(focus["effect"], SMALL, NW - 16, max_lines)):
                draw.text((nx + 8, effect_y + j * 14), line, font=SMALL, fill="#eeeeee")
            draw.text((nx + 8, ny + NH - 17), f"{i + 1:02d}", font=SMALL, fill="#c8c8c8")
            days = f"{focus['days']}일"
            draw.text((nx + NW - 8 - SMALL.getlength(days), ny + NH - 17),
                      days, font=SMALL, fill="#c8c8c8")
        else:
            draw.text((nx + 8, ny + 25), f"미정 {i + 1}", font=NAME, fill=style.MUTED)

    for i in range(1, len(boxes)):
        old, new = boxes[i - 1], boxes[i]
        if (i - 1) // COLS == i // COLS:
            if new[0] > old[0]:
                start, end = (old[2], old[1] + NH / 2), (new[0], new[1] + NH / 2)
            else:
                start, end = (old[0], old[1] + NH / 2), (new[2], new[1] + NH / 2)
        else:
            start, end = ((old[0] + old[2]) / 2, old[3]), ((new[0] + new[2]) / 2, new[1])
        arrow(draw, start, end)


def render_file(stem):
    branch = json.loads((HERE / "data" / f"{stem}.json").read_text(encoding="utf-8"))
    positions, width, height = forest_layout(branch["groups"])
    img = Image.new("RGB", (width, height), style.BG)
    draw = ImageDraw.Draw(img)
    by_id = {g["id"]: g for g in branch["groups"]}
    color = style.BRANCH_COLORS[branch["branch"]]
    total = sum(g["target"] for g in branch["groups"])
    done = sum(len(g["focuses"]) for g in branch["groups"])
    style.bold(draw, (MARGIN, 24), f"{branch['title']} — 가로 구성", style.F_TITLE, style.TEXT)
    draw.text((MARGIN, 76), f"{done}/{total}칸 · 번호와 화살표 순서로 진행 · 다음 줄은 반대 방향",
              font=style.F_SUB, fill=style.MUTED)
    draw.text((MARGIN, 106), "공통 선행은 한 번만 표시 · 빨간 안내는 서로 배타적인 선택지 · 조건/선행 관계 유지",
              font=style.F_SUB, fill=style.MUTED)
    for group in branch["groups"]:
        paint_group(draw, group, positions[group["id"]], color, by_id)
    # 패널 사이 선은 선행 관계를 그대로 표시한다.
    for group in branch["groups"]:
        if not group["after"]:
            continue
        parent = by_id[group["after"]]
        px, py = positions[parent["id"]]
        x, y = positions[group["id"]]
        if py == y:
            # 공통 선행→여러 자식은 각 자식 상단을 지나는 위쪽 연결선.
            start = (px + CW / 2, py)
            end = (x + CW / 2, y)
            mid = y - 12
            draw.line((start[0], start[1], start[0], mid, end[0], mid), fill=style.LINE, width=2)
            arrow(draw, (end[0], mid), end)
        else:
            arrow(draw, (px + CW / 2, py + card_height(parent)), (x + CW / 2, y))
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{stem}.png"
    img.save(path)
    return path


def main():
    for stem in FILES:
        path = render_file(stem)
        with Image.open(path) as image:
            print(f"{path.relative_to(HERE)}  {image.width}x{image.height}")


if __name__ == "__main__":
    main()
