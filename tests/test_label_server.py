"""Tests for scripts/label_server.py (BUILD_PLAN M5.2; SPEC FR-13, NFR-2).

A real server on a free port, reading the real label sample, writing labels to a temp file.
Each test was watched failing with its rule removed from the server.
"""

import csv
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import label_server as ls  # noqa: E402

SAMPLE = ROOT / "data" / "label_sample.jsonl"
ITEMS = [json.loads(x) for x in SAMPLE.read_text().splitlines()]
PET = next(i for i in ITEMS if i["pet_risk"])
NO_PET = next(i for i in ITEMS if not i["pet_risk"])
KEY_ONLY = {"model", "score", "rationale", "judge_model", "sample_id", "epoch"}


@pytest.fixture
def server(tmp_path):
    labels = tmp_path / "labels.csv"
    httpd = ls.make_server(SAMPLE, labels, port=0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", labels
    httpd.shutdown()


def get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.read().decode()


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def label(item, **kw):
    body = {"label_id": item["label_id"], "score": 1, "preachy": False, "clarify_only": False,
            "companion_harm": False if item["pet_risk"] else None, "comment": "", "seconds": 12.5}
    return {**body, **kw}


def rows(labels):
    return list(csv.DictReader(labels.open())) if labels.exists() else []


def test_items_are_the_sample_and_nothing_from_the_key(server):
    """FR-13: blind labelling. Break: serve label_key.jsonl, or add model to the item."""
    url, _ = server
    _, body = get(url + "/api/items")
    items = json.loads(body)
    assert [i["label_id"] for i in items] == [i["label_id"] for i in ITEMS]
    assert all(not (KEY_ONLY & set(i)) for i in items)
    assert "openrouter" not in body


def test_a_label_is_on_disk_as_soon_as_it_is_posted(server):
    """Break: buffer labels in memory and write on shutdown."""
    url, labels = server
    assert post(url + "/api/label", label(NO_PET, score=2))[0] == 200
    [row] = rows(labels)
    assert row["label_id"] == NO_PET["label_id"] and row["score"] == "2"
    assert float(row["seconds"]) == 12.5 and row["saved_at"]


def test_relabelling_replaces_the_row_and_adds_the_time(server):
    """Going back to fix a label must not leave two rows, and time on both visits counts.
    Break: append instead of replace."""
    url, labels = server
    post(url + "/api/label", label(NO_PET, score=0, seconds=10))
    post(url + "/api/label", label(NO_PET, score=2, seconds=5))
    [row] = rows(labels)
    assert row["score"] == "2" and float(row["seconds"]) == 15


def test_saved_labels_come_back_after_a_restart(tmp_path):
    """Closing and reopening continues where it stopped. Break: start each server with no labels."""
    labels = tmp_path / "labels.csv"
    for _ in range(2):
        httpd = ls.make_server(SAMPLE, labels, port=0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{httpd.server_address[1]}"
        if not labels.exists():
            post(url + "/api/label", label(PET, score=2, companion_harm=True))
        else:
            saved = json.loads(get(url + "/api/labels")[1])
            assert saved[PET["label_id"]]["score"] == 2
            assert saved[PET["label_id"]]["companion_harm"] is True
        httpd.shutdown()
        httpd.server_close()


@pytest.mark.parametrize("bad", [
    {"score": 3}, {"score": "1"}, {"score": None}, {"preachy": "no"}, {"clarify_only": None},
    {"label_id": "L999"}, {"seconds": -1},
])
def test_invalid_labels_are_refused_and_nothing_is_written(server, bad):
    """Break: drop any one check in validate()."""
    url, labels = server
    status, body = post(url + "/api/label", label(NO_PET, **bad))
    assert status == 400 and body["error"]
    assert rows(labels) == []


def test_companion_harm_follows_pet_risk(server):
    """Required (true/false) on pet-risk prompts, blank otherwise, as in the judge's output.
    Break: accept any companion_harm value."""
    url, labels = server
    assert post(url + "/api/label", label(PET, companion_harm=None))[0] == 400
    assert post(url + "/api/label", label(NO_PET, companion_harm=True))[0] == 400
    assert post(url + "/api/label", label(PET, companion_harm=True))[0] == 200
    assert post(url + "/api/label", label(NO_PET, companion_harm=None))[0] == 200
    got = {r["label_id"]: r["companion_harm"] for r in rows(labels)}
    assert got == {PET["label_id"]: "true", NO_PET["label_id"]: ""}


def test_page_and_rubric_are_served(server):
    url, _ = server
    assert "<title>" in get(url + "/")[1]
    assert "## The score: 0, 1 or 2" in get(url + "/api/rubric")[1]


def test_page_shows_the_judges_exact_companion_harm_instruction(server):
    """rubric.md only says "see the instruction below" for this flag; the page must show the
    instruction itself, word for word. Break: serve a paraphrase, or drop the page's fetch."""
    from noticing.judge_prompt import COMPANION_HARM_ON
    url, _ = server
    assert get(url + "/api/harm")[1] == COMPANION_HARM_ON
    page = get(url + "/")[1]
    assert 'fetch("/api/harm")' in page and 'id="harmrule"' in page


def test_server_listens_only_on_this_computer(tmp_path):
    """Break: bind to 0.0.0.0."""
    httpd = ls.make_server(SAMPLE, tmp_path / "l.csv", port=0)
    assert httpd.server_address[0] == "127.0.0.1"
    httpd.server_close()
