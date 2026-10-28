"""Every template parses; every template passes the copy lint; the markdown mirror and llms.txt behave."""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from desk.config import lint_public_copy, strip_template
from desk.mirror import build_llms_txt, html_to_markdown, md_path, md_target, wants_markdown

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "desk" / "templates"


def test_templates_parse():
    env = Environment(loader=FileSystemLoader(str(TPL)))
    files = sorted(TPL.rglob("*.html"))
    assert len(files) >= 15
    for p in files:
        env.parse(p.read_text(encoding="utf-8"), filename=str(p))


def test_no_dict_method_shadowing():
    """Jinja resolves `d.keys` to dict.keys, not d["keys"]; data keys that collide must use subscripts."""
    bad = re.compile(r"\b\w+\.(keys|values|items|update|pop|copy|clear)\b(?!\()")
    hits = []
    for p in sorted(TPL.rglob("*.html")):
        text = re.sub(r"<script.*?</script>", " ", p.read_text(encoding="utf-8"), flags=re.S)
        for m in re.finditer(r"{[{%].*?[}%]}", text, flags=re.S):
            if bad.search(m.group(0)):
                hits.append(f"{p.name}: {m.group(0)}")
    assert hits == []


def test_templates_pass_copy_lint(config):
    texts = [strip_template(p.read_text(encoding="utf-8")) for p in TPL.rglob("*.html")]
    assert lint_public_copy(config, texts) == []


def test_reply_templates_do_not_promise(config):
    for name, text in config.reply_templates.items():
        low = text.lower()
        assert "will be paid" not in low and "guarantee" not in low, name
        assert "{ticket_url}" in text or name in ("invalid", "notice"), name


def test_md_paths():
    assert md_target("/index.md") == "/" and md_target("/bounty/XE-0001.md") == "/bounty/XE-0001"
    assert md_target("/v1/export/triage.md") is None and md_target("/scope") is None
    assert md_path("/") == "/index.md" and md_path("/scope") == "/scope.md"
    assert wants_markdown("text/markdown") and not wants_markdown("text/html,text/markdown")


def test_html_to_markdown_drops_chrome_and_keeps_table():
    html = """<html><head><title>T</title></head><body><header><nav><a href="/x">nav</a></nav></header>
    <main><h1>Open tickets</h1><form><input></form><table><tr><th>#</th><th>Finding</th></tr>
    <tr><td><a href="/bounty/XE-0001">XE-0001</a></td><td>A crash</td></tr></table><script>x()</script></main>
    <footer>f</footer></body></html>"""
    md = html_to_markdown(html, "https://bounty.xe.network/")
    assert "# Open tickets" in md and "A crash" in md and "https://bounty.xe.network/bounty/XE-0001" in md
    assert "nav" not in md and "x()" not in md and "<input" not in md


def test_llms_txt_shape(config):
    txt = build_llms_txt(config, "https://bounty.xe.network", "testnet-0005")
    assert txt.startswith("# XE Desk") and "> " in txt
    assert "https://bounty.xe.network/index.md" in txt and "/v1/events/stream" in txt
    assert lint_public_copy(config, [txt]) == []
