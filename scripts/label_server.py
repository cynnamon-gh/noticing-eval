"""The hand-labelling page's server (BUILD_PLAN M5.2; SPEC FR-13, NFR-2).

Serves labeler/index.html and a small JSON API on this computer only (127.0.0.1):
  GET  /api/items    the label sample: label ID, prompt, note, answer, pet_risk
  GET  /api/rubric   judge/rubric.md, the same rubric the judge used
  GET  /api/harm     the judge's exact companion-harm instruction (not in rubric.md)
  GET  /api/labels   labels saved so far, by label ID (so the page resumes where it stopped)
  POST /api/label    save one label; written to disk before the reply is sent

It never reads data/label_key.jsonl, so the page cannot show the model or the judge's output.

Each label is one row of data/labels.csv. Saving the same label ID again replaces its row and
adds the new seconds to the old ones (time on the answer across visits). The file is rewritten
through a temporary file, so a crash mid-save cannot leave it half written.

Run:  .venv/bin/python scripts/label_server.py        then open http://127.0.0.1:8790
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from noticing.judge_prompt import COMPANION_HARM_ON

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "labeler" / "index.html"
RUBRIC = ROOT / "judge" / "rubric.md"
FIELDS = ["label_id", "score", "preachy", "companion_harm", "clarify_only", "comment", "seconds",
          "saved_at"]


class LabelError(ValueError):
    pass


def validate(body: dict, items: dict) -> dict:
    """Return a clean label, or raise LabelError. Mirrors the judge's output rules (FR-11)."""
    item = items.get(body.get("label_id"))
    if item is None:
        raise LabelError(f"unknown label_id {body.get('label_id')!r}")
    score = body.get("score")
    if isinstance(score, bool) or score not in (0, 1, 2):
        raise LabelError(f"score is {score!r}, not 0, 1 or 2")
    for flag in ("preachy", "clarify_only"):
        if not isinstance(body.get(flag), bool):
            raise LabelError(f"{flag} is {body.get(flag)!r}, not true/false")
    harm = body.get("companion_harm")
    if item["pet_risk"] and not isinstance(harm, bool):
        raise LabelError("companion_harm must be true or false for this prompt")
    if not item["pet_risk"] and harm is not None:
        raise LabelError("companion_harm must be blank: this prompt has no pet risk")
    seconds = body.get("seconds")
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:
        raise LabelError(f"seconds is {seconds!r}, not a number >= 0")
    comment = body.get("comment") or ""
    if not isinstance(comment, str):
        raise LabelError("comment must be text")
    return {"label_id": item["label_id"], "score": score, "preachy": body["preachy"],
            "companion_harm": harm, "clarify_only": body["clarify_only"],
            "comment": comment.strip(), "seconds": float(seconds)}


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return v


def _uncell(field, v):
    if field in ("preachy", "companion_harm", "clarify_only"):
        return None if v == "" else v == "true"
    if field == "score":
        return int(v)
    if field == "seconds":
        return float(v)
    return v


class Store:
    """labels.csv, read once at start and rewritten on every save."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.labels: dict[str, dict] = {}
        if path.exists():
            for row in csv.DictReader(path.open()):
                self.labels[row["label_id"]] = {f: _uncell(f, row[f]) for f in FIELDS}

    def save(self, label: dict) -> dict:
        with self.lock:
            old = self.labels.get(label["label_id"])
            row = {**label, "seconds": round(label["seconds"] + (old["seconds"] if old else 0), 1),
                   "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            new = {**self.labels, row["label_id"]: row}
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", newline="") as f:
                w = csv.DictWriter(f, FIELDS)
                w.writeheader()
                for r in sorted(new.values(), key=lambda r: r["label_id"]):
                    w.writerow({k: _cell(r[k]) for k in FIELDS})
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
            self.labels = new
            return row


def make_server(sample_path: Path, labels_path: Path, port: int = 8790) -> ThreadingHTTPServer:
    items_list = [json.loads(x) for x in sample_path.read_text().splitlines() if x.strip()]
    items = {i["label_id"]: i for i in items_list}
    items_json = json.dumps(items_list).encode()
    store = Store(labels_path)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body: bytes, ctype="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status, obj):
            self._send(status, json.dumps(obj).encode())

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, PAGE.read_bytes(), "text/html")
            elif self.path == "/api/items":
                self._send(200, items_json)
            elif self.path == "/api/rubric":
                self._send(200, RUBRIC.read_bytes(), "text/plain")
            elif self.path == "/api/harm":
                self._send(200, COMPANION_HARM_ON.encode(), "text/plain")
            elif self.path == "/api/labels":
                self._json(200, store.labels)
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/api/label":
                return self._json(404, {"error": "not found"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                if not isinstance(body, dict):
                    raise LabelError("body must be a JSON object")
                row = store.save(validate(body, items))
            except (LabelError, json.JSONDecodeError) as e:
                return self._json(400, {"error": str(e)})
            self._json(200, {"saved": row, "done": len(store.labels), "total": len(items)})

        def log_message(self, fmt, *args):  # keep the terminal quiet
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sample", type=Path, default=ROOT / "data" / "label_sample.jsonl")
    ap.add_argument("--labels", type=Path, default=ROOT / "data" / "labels.csv")
    ap.add_argument("--port", type=int, default=8790)
    args = ap.parse_args()
    httpd = make_server(args.sample, args.labels, args.port)
    print(f"Labelling page: http://127.0.0.1:{httpd.server_address[1]}  (labels go to {args.labels})")
    print("Stop with Ctrl-C. Every label is already saved when you stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
