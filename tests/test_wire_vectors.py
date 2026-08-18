"""Wire-format + behavioral-vector tests."""
import hashlib

import pytest

from smartfabric import vectors
from smartfabric.models import CIRHeader, CIRMessage, CIRPolicy, InfluenceClass
from smartfabric.wire import (
    canonical_json,
    decode,
    deframe,
    encode,
    frame,
    frame_message,
    read_varint,
    write_varint,
)


# --- canonical JSON -------------------------------------------------------- #

def test_canonical_json_sorts_keys_and_omits_whitespace():
    out = canonical_json({"b": 1, "a": 2})
    assert out == b'{"a":2,"b":1}'


def test_canonical_json_utf8():
    out = canonical_json({"k": "héllo"})
    assert out.decode("utf-8") == '{"k":"héllo"}'
    assert "é".encode("utf-8") in out


def test_canonical_json_rejects_nan():
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


def _msg():
    return CIRMessage(
        header=CIRHeader(
            id="01TESTID000000000000000001",
            verb="invoke",
            from_addr="iaiso://a@dc1/cap",
            to_addr="iaiso://b@dc1/cap",
            verb_version="0.1",
        ),
        policy=CIRPolicy(influence_class=InfluenceClass.INFORMATIONAL),
    )


def test_encode_omits_absent_optionals():
    out = encode(_msg()).decode("utf-8")
    # no idempotency/trace/deadline present
    assert "idempotency" not in out
    assert "trace" not in out
    # required fields present
    assert '"verb":"invoke"' in out
    assert '"influence_class":"informational"' in out


def test_encode_is_deterministic():
    assert encode(_msg()) == encode(_msg())


def test_round_trip_is_stable():
    msg = _msg()
    once = encode(msg)
    twice = encode(decode(once))
    assert once == twice


def test_decode_reconstructs_fields():
    msg = decode(encode(_msg()))
    assert msg.header.verb == "invoke"
    assert msg.header.from_addr == "iaiso://a@dc1/cap"
    assert msg.policy.influence_class is InfluenceClass.INFORMATIONAL


# --- framing --------------------------------------------------------------- #

@pytest.mark.parametrize("n", [0, 1, 127, 128, 300, 16384, 2_000_000])
def test_varint_round_trip(n):
    buf = write_varint(n)
    val, off = read_varint(buf)
    assert val == n
    assert off == len(buf)


def test_frame_deframe():
    payload = b"hello fabric"
    framed = frame(payload)
    got, off = deframe(framed)
    assert got == payload
    assert off == len(framed)


def test_multiple_frames_in_a_stream():
    a = frame(b"one")
    b = frame(b"two")
    stream = a + b
    p1, off = deframe(stream, 0)
    p2, off2 = deframe(stream, off)
    assert p1 == b"one" and p2 == b"two"
    assert off2 == len(stream)


def test_frame_message_matches_manual():
    msg = _msg()
    manual = frame(encode(msg))
    assert frame_message(msg) == manual


# --- behavioral vectors ---------------------------------------------------- #

def test_all_vectors_pass():
    results = vectors.run_all()
    failures = [f"{r.family}/{r.name}: {r.detail}" for r in results if not r.ok]
    assert not failures, failures


def test_vectors_cover_all_families():
    results = vectors.run_all()
    families = {r.family for r in results}
    assert families == {"pressure", "fleet", "envelope"}


def test_envelope_vector_sha_matches_recompute():
    # independent recompute of the sha for one envelope vector
    from smartfabric.vectors import _load
    case = _load("envelope.vectors.json")["cases"][0]
    msg = decode(case["message"])
    sha = "sha256:" + hashlib.sha256(encode(msg)).hexdigest()
    assert sha == case["expect"]["canonical_sha256"]
