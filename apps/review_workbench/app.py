from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data/evaluation/pilots/alphabet_2025_item1_business_map.json"
REVIEW_FILE = ROOT / "data/evaluation/reviews/alphabet_2025_item1_review.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: object) -> str:
    return html.escape(str(value))


def render_business(item: dict, evidence: dict[str, dict], review: dict) -> str:
    evidence_cards = "".join(render_evidence(evidence[eid]) for eid in item.get("evidence_ids", []) if eid in evidence)
    products = "".join(f"<span class='chip'>{esc(value)}</span>" for value in item.get("products_services", []))
    money = "".join(f"<li>{esc(value['description'])} <small>{esc(value['basis'])}</small></li>" for value in item.get("monetization", []))
    current = review.get(item["id"], {}).get("status", item.get("review_status", "candidate"))
    note = review.get(item["id"], {}).get("note", "")
    options = "".join(
        f"<option value='{status}' {'selected' if status == current else ''}>{status}</option>"
        for status in ("candidate", "accepted", "edited", "rejected", "ambiguous")
    )
    return f"""
    <article class="business-card" id="{esc(item['id'])}">
      <div class="card-head"><div><span class="kind">{esc(item['kind'])}</span><h3>{esc(item['name'])}</h3></div><span class="status {esc(current)}">{esc(current)}</span></div>
      <p class="description">{esc(item['description'])}</p>
      <div class="label">Representative products & services</div><div class="chips">{products or '<span class="muted">None recorded</span>'}</div>
      <div class="label">How it makes money</div><ul>{money or '<li class="muted">Not stated at this level</li>'}</ul>
      <details><summary>Evidence ({len(item.get('evidence_ids', []))})</summary>{evidence_cards}</details>
      <form method="post" action="/review">
        <input type="hidden" name="item_id" value="{esc(item['id'])}">
        <select name="status">{options}</select>
        <input name="note" value="{esc(note)}" placeholder="Review note">
        <button type="submit">Save review</button>
      </form>
    </article>"""


def render_evidence(item: dict) -> str:
    path = " › ".join(item.get("section_path", []))
    return f"""<div class="evidence"><div>{esc(item['support'])}</div><small>{esc(path)} · paragraph {esc(item['paragraph_ordinal'])} · {esc(item['text_hash'][:12])}</small><a href="{esc(item['source_url'])}" target="_blank">Open SEC filing ↗</a></div>"""


def render_page(data: dict, reviews: dict) -> str:
    evidence = {item["id"]: item for item in data["evidence"]}
    businesses = "".join(render_business(item, evidence, reviews.get("businesses", {})) for item in data["businesses"])
    relationships = "".join(
        f"<tr><td>{esc(item['source_id'])}</td><td><span class='relation'>{esc(item['kind'])}</span></td><td>{esc(item['target_id'])}</td><td>{esc(item['description'])}</td></tr>"
        for item in data["relationships"]
    )
    unknowns = "".join(f"<li><strong>{esc(item['question'])}</strong><br><span>{esc(item['reason_unanswered'])}</span></li>" for item in data["unknowns"])
    reviewed = sum(1 for item in reviews.get("businesses", {}).values() if item.get("status") != "candidate")
    total = len(data["businesses"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Uteki · Business Map Review</title>
<style>
:root{{--ink:#17201b;--muted:#66716b;--paper:#f4f1e9;--card:#fffdf8;--line:#d9d5ca;--green:#1f6b4f;--amber:#b46a24;--red:#a4433c}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}header{{padding:42px max(24px,calc((100vw - 1120px)/2));background:#183f32;color:#f7f4ea}}header small{{letter-spacing:.12em;text-transform:uppercase;color:#b8d7c9}}h1{{font:500 42px/1.1 Georgia,serif;margin:10px 0}}header p{{max-width:760px;color:#dbe9e2}}main{{max-width:1120px;margin:auto;padding:30px 24px 80px}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:-52px;margin-bottom:32px}}.metric{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;box-shadow:0 8px 22px #173c2e13}}.metric b{{display:block;font-size:26px}}h2{{font:500 28px Georgia,serif;margin-top:42px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}.business-card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px}}.card-head{{display:flex;justify-content:space-between;gap:12px}}h3{{margin:4px 0;font:500 23px Georgia,serif}}.kind,.relation{{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--green)}}.status{{font-size:12px;border:1px solid var(--line);border-radius:999px;padding:4px 9px;height:max-content}}.status.accepted{{color:var(--green);border-color:#8bb7a2}}.status.rejected{{color:var(--red)}}.status.ambiguous{{color:var(--amber)}}.description{{min-height:48px}}.label{{font-size:12px;color:var(--muted);margin-top:14px}}.chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}.chip{{background:#edf0e8;border-radius:6px;padding:3px 8px;font-size:12px}}.muted,small{{color:var(--muted)}}details{{border-top:1px solid var(--line);margin-top:16px;padding-top:12px}}summary{{cursor:pointer;color:var(--green)}}.evidence{{background:#f2efe7;margin:8px 0;padding:10px;border-radius:8px}}.evidence small{{display:block}}.evidence a{{font-size:12px;color:var(--green)}}form{{display:grid;grid-template-columns:130px 1fr auto;gap:8px;margin-top:15px}}input,select,button{{border:1px solid var(--line);border-radius:7px;padding:9px;background:white}}button{{background:var(--green);color:white;border-color:var(--green);cursor:pointer}}table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line)}}td,th{{text-align:left;padding:11px;border-bottom:1px solid var(--line)}}.unknowns{{background:#fff8e8;border-left:4px solid var(--amber);padding:14px 24px}}@media(max-width:760px){{.grid,.metrics{{grid-template-columns:1fr}}form{{grid-template-columns:1fr}}h1{{font-size:34px}}}}
</style></head><body>
<header><small>Uteki Beta · M0 Candidate</small><h1>Alphabet Company Business Map</h1><p>{esc(data['summary'])}</p></header>
<main><section class="metrics"><div class="metric"><small>Business nodes</small><b>{total}</b></div><div class="metric"><small>Relationships</small><b>{len(data['relationships'])}</b></div><div class="metric"><small>Reviewed</small><b>{reviewed}/{total}</b></div></section>
<h2>Businesses</h2><section class="grid">{businesses}</section>
<h2>Relationships</h2><table><thead><tr><th>From</th><th>Relation</th><th>To</th><th>Meaning</th></tr></thead><tbody>{relationships}</tbody></table>
<h2>Material unknowns</h2><ul class="unknowns">{unknowns}</ul>
</main></body></html>"""


def save_review(item_id: str, status: str, note: str) -> None:
    if status not in {"candidate", "accepted", "edited", "rejected", "ambiguous"}:
        raise ValueError("invalid review status")
    REVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    value = load_json(REVIEW_FILE) if REVIEW_FILE.exists() else {"businesses": {}}
    value.setdefault("businesses", {})[item_id] = {"status": status, "note": note}
    temporary = REVIEW_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REVIEW_FILE)


def make_handler(data_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/":
                self.send_error(404)
                return
            data = load_json(data_path)
            reviews = load_json(REVIEW_FILE) if REVIEW_FILE.exists() else {}
            body = render_page(data, reviews).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != "/review":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            fields = parse_qs(self.rfile.read(length).decode())
            item_id = fields.get("item_id", [""])[0]
            allowed_ids = {item["id"] for item in load_json(data_path)["businesses"]}
            if item_id not in allowed_ids:
                self.send_error(400, "unknown business id")
                return
            save_review(item_id, fields.get("status", [""])[0], fields.get("note", [""])[0])
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.data))
    print(f"Uteki Review Workbench: http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
