"""Unit tests for the canonical body hasher."""

from app.hashing import canonicalize, hash_body


def test_hash_is_stable_regardless_of_key_order():
    a = hash_body({"amount": 100, "currency": "USD"})
    b = hash_body({"currency": "USD", "amount": 100})
    assert a == b


def test_hash_differs_for_different_bodies():
    a = hash_body({"amount": 100, "currency": "USD"})
    b = hash_body({"amount": 101, "currency": "USD"})
    assert a != b


def test_canonicalize_sorts_nested_dicts_but_preserves_list_order():
    c = canonicalize({"b": {"y": 2, "x": 1}, "a": [3, 2, 1]})
    assert list(c.keys()) == ["a", "b"]
    assert list(c["b"].keys()) == ["x", "y"]
    assert c["a"] == [3, 2, 1]


def test_hash_handles_none_and_empty_safely():
    assert hash_body(None) == hash_body({})
