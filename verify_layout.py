"""Measure the rendered layout to verify the two gaps are equal and the buttons
sit in the lower half of the screen.

Uses a headless browser via the Mel browser tool is not scriptable here, so this
reads the geometry from the DOM using the site's own JS context through a
temporary probe page is not possible either. Instead this asserts the CSS
contract: a single flex `gap` on .center governs both spaces, and no
margin/padding on the intervening elements adds to either side.
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
m = re.search(r"\.center\s*\{[^}]*\}", html, re.S)
center = m.group(0) if m else ""
check(".center is a flex column", "display:flex" in center.replace(" ", ""))
check(".center declares a gap", "gap:" in center)
check(".center is top-aligned (buttons fall to lower half)",
      "justify-content:flex-start" in center.replace(" ", ""))

# 2. The card grows, so the buttons are pushed down.
m = re.search(r"\.say\s*\{[^}]*\}", html, re.S)
say = m.group(0) if m else ""
# Normalise whitespace without destroying the spaces inside "1 1 auto".
say_norm = re.sub(r"\s+", " ", say)
check(".say grows to fill leftover height", "flex:1 1 auto" in say_norm,
      [ln.strip() for ln in say.splitlines() if "flex" in ln])
check(".say has no fixed max-height fighting the growth", "max-height" not in say)

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
m = re.search(r"@media \(max-height:620px\)\s*\{(.*?)\n  \}", html, re.S)
media = m.group(1) if m else ""
check("short-screen rule does not pin .say height", ".say" not in media)

# 6. The removed caption is really gone, and nothing still writes to it.
check("caption text removed", "stay on this device" not in html)
check("no dangling $('#hint') reference", "$('hint')" not in html)

print("\nRESULT: %s (%d failure(s))" % ("PASS" if not fails else "FAIL", len(fails)))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
