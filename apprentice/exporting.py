"""Export the current map as JSON, Markdown with assets, and standalone HTML."""

import base64
import html
import json
from pathlib import Path
import shutil
from uuid import uuid4

from apprentice.domain import Session


def export_session(session: Session, store, destination: Path) -> Path:
    # A unique snapshot folder preserves previous deliberate exports. Exports are
    # user-owned copies; later evidence exclusions cannot recall shared copies.
    folder = destination / ("work-map-" + session.id[:8] + "-" + uuid4().hex[:6])
    folder.mkdir(parents=True)
    assets = folder / "assets"
    assets.mkdir()
    title = html.escape(session.title)
    md = [f"# {session.title}", "", f"Mode: {session.mode} | Expert confirmed: {session.confirmed}", "", session.context, ""]
    sections = [f"<h1>{title}</h1><p>Mode: {session.mode} · Expert confirmed: {session.confirmed}</p><p>{html.escape(session.context)}</p>"]
    evidence = {e.id: e for e in session.evidence}
    for i, item in enumerate((k for k in session.knowledge if k.status != "rejected"), 1):
        md.extend([f"## {i}. {item.title}", f"Status: {item.status}", ""])
        block = [f"<section><h2>{i}. {html.escape(item.title)}</h2><p class='status'>{item.status}</p>"]
        for key in ("action", "decision", "reason", "rule", "exception", "guardrail", "escalation"):
            value = getattr(item, key)
            md.extend([f"**{key.title()}:** {value}", ""])
            block.append(f"<p><strong>{key.title()}:</strong> {html.escape(value)}</p>")
        for eid in item.evidence_ids:
            if eid not in evidence:
                continue
            e = evidence[eid]
            caption = f"Source {eid[:8]} · {e.timestamp:.1f}s · {e.kind}: {e.text}"
            md.extend([caption, ""])
            block.append(f"<p class='source'>{html.escape(caption)}</p>")
            if e.image:
                source = store.media(session.id, e.image)
                if source.is_file():
                    filename = f"{eid}.jpg"
                    shutil.copyfile(source, assets / filename)
                    md.extend([f"![Evidence](assets/{filename})", ""])
                    data = base64.b64encode(source.read_bytes()).decode()
                    block.append(f"<img alt='Source screenshot' src='data:image/jpeg;base64,{data}'>")
        block.append("</section>")
        sections.append("\n".join(block))
    (folder / "work-map.md").write_text("\n".join(md), encoding="utf-8")
    (folder / "work-map.json").write_text(session.model_dump_json(indent=2), encoding="utf-8")
    (folder / "work-map.html").write_text("<!doctype html><html lang='en'><meta charset='utf-8'>"
        f"<title>{title}</title><style>body{{font:16px/1.6 system-ui;max-width:900px;margin:48px auto;padding:0 24px;color:#182b32;background:#f5f7f7}}section{{background:white;padding:24px;margin:20px 0;border:1px solid #dce5e3;border-radius:16px}}img{{max-width:100%}}.source,.status{{color:#456961;font-size:13px}}p{{white-space:pre-wrap}}</style><body>" + "\n".join(sections) + "</body></html>", encoding="utf-8")
    return folder
