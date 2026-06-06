import hashlib
import json
import sqlite3

import pytest

from modron import ledger
from modron.engine import evaluate
from modron.grammar import normal_form, parse


@pytest.fixture()
def tmp_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("MODRON_LEDGER", str(tmp_path / "rolls.db"))
    return tmp_path / "rolls.db"


def _roll_into(session_id, expr="2d6+1"):
    stream, meta = ledger.next_stream(session_id)
    node = parse(expr)
    result = evaluate(node, stream)
    rec = ledger.record_roll(meta, expr_asked=expr, expr_resolved=normal_form(node),
                             total=result.total,
                             groups=[g.to_dict() for g in result.groups],
                             view="2e", purpose="test")
    return rec, result


def test_session_commitment_binds_seed(tmp_ledger):
    """§12 Q1 (Ryan, 2026-06-05): seed WITHHELD at close; reveal on demand."""
    ses = ledger.open_session("night-one", view="2e", seed_phrase="the cage")
    assert ses["seed_commitment"]
    closed = ledger.close_session(ses["session_id"])          # default: withheld
    assert "seed_revealed_hex" not in closed
    assert "WITHHELD" in closed["seed"]
    revealed = ledger.close_session(ses["session_id"], reveal=True)   # on demand
    seed = bytes.fromhex(revealed["seed_revealed_hex"])
    assert hashlib.sha256(seed).hexdigest() == ses["seed_commitment"]


def test_roll_verify_pass(tmp_ledger):
    ses = ledger.open_session("verify-night")
    rec, _ = _roll_into(ses["session_id"])
    v = ledger.verify_roll(rec["roll_id"])
    assert v["verdict"] == "PASS"
    assert v["faces_match"] and v["total_match"] and v["sha_match"]


def test_ephemeral_roll_verifies(tmp_ledger):
    rec, _ = _roll_into(None)
    assert rec["roll_id"].startswith("rol:eph:")
    assert ledger.verify_roll(rec["roll_id"])["verdict"] == "PASS"


def test_counter_increments_and_closed_session_refuses(tmp_ledger):
    ses = ledger.open_session("counting")
    r1, _ = _roll_into(ses["session_id"])
    r2, _ = _roll_into(ses["session_id"])
    assert (r1["counter"], r2["counter"]) == (1, 2)
    ledger.close_session(ses["session_id"])
    with pytest.raises(ledger.LedgerError, match="closed"):
        ledger.next_stream(ses["session_id"])


def test_duplicate_sha_refused(tmp_ledger):
    ses = ledger.open_session("dup-night")
    stream, meta = ledger.next_stream(ses["session_id"])
    node = parse("1d6")
    result = evaluate(node, stream)
    groups = [g.to_dict() for g in result.groups]
    ledger.record_roll(meta, expr_asked="1d6", expr_resolved="1d6",
                       total=result.total, groups=groups)
    with pytest.raises(ledger.LedgerError, match="duplicate"):
        ledger.record_roll(meta, expr_asked="1d6", expr_resolved="1d6",
                           total=result.total, groups=groups)


def test_tamper_detected(tmp_ledger):
    ses = ledger.open_session("tamper-night")
    rec, result = _roll_into(ses["session_id"])
    with sqlite3.connect(str(tmp_ledger)) as conn:  # cook the books
        conn.execute("UPDATE rolls SET total = total + 5 WHERE roll_id=?",
                     (rec["roll_id"],))
    v = ledger.verify_roll(rec["roll_id"])
    assert v["verdict"] == "FAIL" and v["total_match"] is False
    sweep = ledger.verify_session(ses["session_id"])
    assert sweep["verdict"] == "FAIL" and len(sweep["failures"]) == 1


def test_fiat_is_honest(tmp_ledger):
    with pytest.raises(ledger.LedgerError, match="reason"):
        ledger.record_fiat(17, reason="  ")
    rec = ledger.record_fiat(17, reason="the story needs the bridge to hold",
                             expr="2d6")
    row = ledger.get_roll(rec["roll_id"])
    assert row["method"] == "fiat"
    assert ledger.verify_roll(rec["roll_id"])["verdict"] == "FIAT"
    assert "FIAT" in json.loads(row["notes_json"])[0]


def test_history_filters(tmp_ledger):
    ses = ledger.open_session("hist-night")
    _roll_into(ses["session_id"])
    _roll_into(None)
    ledger.record_fiat(3, reason="why not", session_id=ses["session_id"])
    assert len(ledger.history()) == 3
    assert len(ledger.history(session_id=ses["session_id"])) == 2
    assert len(ledger.history(purpose="fiat")) == 1


def test_replay_reproduces(tmp_ledger):
    ses = ledger.open_session("replay-night")
    rec, result = _roll_into(ses["session_id"], "4d6kh3+2")
    rep = ledger.replay(rec["roll_id"])
    assert rep["identical_to_ledger"] is True
    assert rep["total"] == result.total


def test_verify_session_sweeps_past_500(tmp_ledger):
    """audit F-1-design-docs-02: verify_session must sweep EVERY roll, not
    history()'s capped 500 — and cross-check the session counter."""
    ses = ledger.open_session("long-night", view="2e", seed_phrase="marathon")
    sid = ses["session_id"]
    for _ in range(503):
        _roll_into(sid, "1d6")
    report = ledger.verify_session(sid)
    assert report["rolls_checked"] == 503
    assert report["verdict"] == "PASS"
    assert "count_mismatch" not in report


def test_verify_session_count_mismatch_fails(tmp_ledger):
    """A counter that disagrees with the rolled rows is a FAIL, not a shrug."""
    ses = ledger.open_session("tampered", view="2e", seed_phrase="hmm")
    sid = ses["session_id"]
    _roll_into(sid)
    with ledger._connect() as conn:
        conn.execute("UPDATE sessions SET counter=5 WHERE session_id=?", (sid,))
    report = ledger.verify_session(sid)
    assert report["verdict"] == "FAIL"
    assert "count_mismatch" in report
