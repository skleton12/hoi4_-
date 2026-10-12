"""Bundle six installed HOI4 icons and their shine sprites under unique mod names.

Usage: python import_icons.py --game-dir ".../Hearts of Iron IV"
"""
import argparse
import re
import shutil
from pathlib import Path

NAMES = (
    "political_pressure", "construct_civ_factory", "army_doctrines",
    "major_alliance", "construct_infrastructure", "production",
)
MOD = Path(__file__).resolve().parents[2] / "mod/gibon_jungjeom"

def sprite(source, name):
    match = re.search(r'SpriteType\s*=\s*\{\s*name\s*=\s*"' + re.escape(name) + r'"', source)
    if not match:
        raise ValueError(f"Missing sprite: {name}")
    opening = source.index("{", match.start())
    depth = 0
    for i in range(opening, len(source)):
        depth += (source[i] == "{") - (source[i] == "}")
        if depth == 0:
            return source[match.start():i+1]
    raise ValueError(f"Unclosed sprite: {name}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-dir", type=Path, required=True)
    game = parser.parse_args().game_dir
    normal = (game / "interface/goals.gfx").read_text(encoding="utf-8-sig")
    shine = (game / "interface/goals_shine.gfx").read_text(encoding="utf-8-sig")
    target = MOD / "gfx/interface/gj_goals"
    target.mkdir(parents=True, exist_ok=True)
    blocks = []
    for name in NAMES:
        old = f"GFX_goal_generic_{name}"
        new = f"GFX_GJ_{name}"
        for source, suffix in ((normal, ""), (shine, "_shine")):
            block = sprite(source, old + suffix).replace(old + suffix, new + suffix)
            paths = set(re.findall(r'(?:texturefile|animationmaskfile|animationtexturefile)\s*=\s*"([^"]+)"', block))
            for relative in paths:
                asset = game / relative
                if not asset.is_file():
                    raise FileNotFoundError(asset)
                destination = target / asset.name
                shutil.copyfile(asset, destination)
                block = block.replace(relative, f"gfx/interface/gj_goals/{asset.name}")
            blocks.append(block)
    interface = MOD / "interface/gj_focus_icons.gfx"
    interface.parent.mkdir(parents=True, exist_ok=True)
    interface.write_bytes(("spriteTypes = {\n" + "\n".join(blocks) + "\n}\n").encode("utf-8"))
    print(f"Bundled {len(NAMES)} icons, {len(blocks)} sprite definitions")

if __name__ == "__main__":
    main()
