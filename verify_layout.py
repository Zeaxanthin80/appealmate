"""Assert the call screen's layout contract directly, from index.html.

The rendered result is verified with screenshots; this file guards the
properties that are easy to break silently by editing CSS — a second gap
creeping in, a max-height reappearing, a logo glyph shrinking back inside its
tile. If this passes and the screenshot looks right, the layout is right.

Run:  python verify_layout.py
"""
import re
import sys

html = open("index.html", encoding="utf-8").read()
fails = []


def check(label, cond, detail=""):
    print("%-52s %s %s" % (label, "PASS" if cond else "FAIL", detail))
    if not cond:
        fails.append(label)


# 1. One gap governs the column.
center = re.search(r"\.center\s*\{[^}]*\}", html, re.S).group(0)
check(".center is a flex column", "display:flex" in center.replace(" ", ""))
check(".center declares a gap", "gap:" in center)
check(".center is top-aligned (buttons fall to lower half)",
      "justify-content:flex-start" in center.replace(" ", ""))

# 2. The card grows, so the buttons are pushed down.
say = re.search(r"\.say\s*\{[^}]*\}", html, re.S).group(0)
say_norm = re.sub(r"\s+", " ", say)
check(".say grows to fill leftover height", "flex:1 1 auto" in say_norm,
      [ln.strip() for ln in say.splitlines() if "flex" in ln])
check(".say has no fixed max-height fighting the growth", "max-height" not in say)

# 2b. The desktop presentation width, and that it stays fluid on a phone.
cap = re.search(r"max-width:(\d+)px", say)
check(".say caps at the 860px presentation width",
      cap is not None and cap.group(1) == "860",
      cap.group(0) if cap else "no max-width found")
check(".say stays fluid on narrow screens",
      re.search(r"width:100%", say_norm) is not None,
      "width:100% means the 860px cap cannot break the mobile layout")

# 2c. One column for the whole page: nav, stage and footer share the measure, so
#     their left and right edges line up with the conversation card.
col = re.search(r"--col:\s*(\d+)px", html)
check("a single --col measure is defined", col is not None,
      col.group(0) if col else "missing")
if col:
    check("--col matches the card width (860px)", col.group(1) == "860", col.group(1))
for band, pat in (("header", r"\bheader\s*\{[^}]*\}"),
                  ("footer", r"\bfooter\s*\{[^}]*\}"),
                  (".stage", r"\.stage\s*\{[^}]*\}")):
    rule = re.sub(r"\s+", "", re.search(pat, html, re.S).group(0))
    check("%s uses the shared column" % band, "max-width:var(--col)" in rule)
# Below the column width there is no slack to centre into, so real gutters are
# needed or the content sits flush against the screen edge.
check("gutter defined for narrow screens", "--gut:" in html)
check("gutter applied below the column width",
      re.search(r"@media \(max-width:900px\)\s*\{\s*:root\s*\{[^}]*--gut:\s*\d+px", html) is not None)

# 3. Nothing between the card and the button adds extra space.
check(".talkwrap has no margin", "margin" not in re.search(
    r"\.talkwrap\s*\{[^}]*\}", html, re.S).group(0))
check("#live adds no height when empty",
      "#live:empty" in html and "display:none" in re.search(
          r"#live:empty\s*\{[^}]*\}", html, re.S).group(0))

# 4. The button -> Start over gap is the column gap, nothing more.
under = re.search(r"\.undercall\s*\{[^}]*\}", html, re.S).group(0)
check(".undercall adds no margin (gap stays equal)",
      "margin" not in under, under.replace("\n", " ")[:70])

# 5. Short-screen rule must not reintroduce a fixed card height.
media = re.search(r"@media \(max-height:620px\)\s*\{(.*?)\n  \}", html, re.S)
check("short-screen rule does not pin .say height", ".say" not in (media.group(1) if media else ""))

# 6. The removed caption is really gone, and nothing still writes to it.
check("caption text removed", "stay on this device" not in html)
check("no dangling $('#hint') reference", "$('hint')" not in html)

# 7. The logo mark: the heart must fill its tile, with a thin stroke.
tile = re.search(r"\.mark\s*\{[^}]*\}", html, re.S).group(0)
mark_svg = re.search(r"\.mark svg\s*\{[^}]*\}", html, re.S).group(0)
tile_px = int(re.search(r"width:(\d+)px", tile).group(1))
glyph_px = int(re.search(r"width:(\d+)px", mark_svg).group(1))
ratio = glyph_px / tile_px
check("heart fills most of the tile (>=0.75)", ratio >= 0.75,
      "tile=%dpx glyph=%dpx ratio=%.2f" % (tile_px, glyph_px, ratio))

svg_tag = re.search(r"<svg viewBox=\"2 3\.2[^>]*>", html, re.S)
check("logo svg present", svg_tag is not None)
if svg_tag:
    stroke = float(re.search(r'stroke-width="([\d.]+)"', svg_tag.group(0)).group(1))
    check("heart stroke stays thin (<=1.5)", stroke <= 1.5, "stroke=%s" % stroke)

print("\nRESULT: %s (%d failure(s))" % ("PASS" if not fails else "FAIL", len(fails)))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
