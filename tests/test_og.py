"""Social cards draw, at the right size, from the one copy of the mark, with copy that passes the lint."""

import io

from PIL import Image

from desk import brand, og
from desk.config import lint_public_copy


def test_mark_flattens_to_three_shapes():
    polys = og._flatten(brand.MARK_PATH)
    assert len(polys) == 3
    xs = [x for poly in polys for x, _ in poly]
    ys = [y for poly in polys for _, y in poly]
    assert 0 <= min(xs) and max(xs) <= brand.MARK_VIEWBOX[0] + 0.01
    assert 0 <= min(ys) and max(ys) <= brand.MARK_VIEWBOX[1] + 0.01


def test_card_is_1200_by_630_png():
    png = og.draw_card(
        programme="Bounty programme",
        host="bounty.xe.network",
        kicker="XE-0116",
        title="Representative can final-vote two hashes at one position when the commit-lock write fails",
        chips=[("Critical", og._tier_style("critical")), ("Patched", {"outline": brand.STROKE_STRONG})],
    )
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG" and img.size == (og.W, og.H)
    assert img.getpixel((600, 2)) == brand.BRAND  # accent bar


def test_wrap_ellipsises_long_titles():
    f = og._font("Geist-Bold", 60)
    lines = og._wrap("word " * 80, f, 1040, 2)
    assert len(lines) == 2 and lines[-1].endswith("…")
    assert og._wrap("short", f, 1040, 2) == ["short"]


def test_page_specs_pass_copy_lint(config):
    texts = []
    for site in ("bounty", "support"):

        class C:
            pass

        c = C()
        c.config = config
        for slug in og.PAGES:
            spec = og.page_spec(c, site, slug)
            texts += [spec["title"], spec["line"]]
    assert lint_public_copy(config, texts) == []
