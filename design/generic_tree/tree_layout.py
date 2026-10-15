"""Pillow와 글꼴 없이 사용할 수 있는 중점 트리 배치 계산."""

NODE_H = 74
ROW = NODE_H + 22
HEADER = 58
TOP = 120


def parents_of(group):
    after = group["after"]
    return [] if not after else ([after] if isinstance(after, str) else list(after))


def size(group):
    return len(group["focuses"]) or group["target"]


def layout(groups):
    """소갈래마다 (가운데 열, 머리 y)를 계산한다."""
    by_id = {g["id"]: g for g in groups}
    children = {g["id"]: [] for g in groups}
    joins = {g["id"]: [] for g in groups}
    roots = []
    for group in groups:
        ps = parents_of(group)
        if not ps:
            roots.append(group)
        elif len(ps) == 1:
            children[ps[0]].append(group)
        else:
            joins[by_id[ps[0]]["after"]].append(group)

    span = {}

    def measure(group):
        normal = sum(measure(child) for child in children[group["id"]])
        joined = sum(measure(child) for child in joins[group["id"]])
        span[group["id"]] = max(1, normal, joined)
        return span[group["id"]]

    for root in roots:
        measure(root)

    pos = {}

    def end_y(group):
        return pos[group["id"]][1] + HEADER + size(group) * ROW + 10

    def place(group, left, y):
        pos[group["id"]] = (left + (span[group["id"]] - 1) / 2, y)
        child_y = y + HEADER + size(group) * ROW + 10
        x = left + (span[group["id"]] - sum(span[c["id"]] for c in children[group["id"]])) / 2
        for child in children[group["id"]]:
            place(child, x, child_y)
            x += span[child["id"]]
        x = left
        for child in joins[group["id"]]:
            ps = parents_of(child)
            y_join = max(end_y(by_id[parent]) for parent in ps) + 14
            lo = min(pos[parent][0] - (span[parent] - 1) / 2 for parent in ps)
            hi = max(pos[parent][0] + (span[parent] - 1) / 2 for parent in ps)
            if span[child["id"]] <= hi - lo + 1:
                place(child, (lo + hi) / 2 - (span[child["id"]] - 1) / 2, y_join)
            else:
                place(child, x, y_join)
                x += span[child["id"]]

    left = 0
    for root in roots:
        place(root, left, TOP + 70)
        left += span[root["id"]]
    return pos, left
