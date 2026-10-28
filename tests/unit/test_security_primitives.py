"""Unit tests for security primitives: redaction, safe paths, hashing."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from hcs_discovery.core.errors import ValidationError
from hcs_discovery.core.hashing import sha256_text, stable_json_hash
from hcs_discovery.core.paths import safe_filename, safe_join
from hcs_discovery.core.redaction import redact_text, redact_value, register_secret


def test_redacts_github_and_openai_tokens():
    # Deliberately below real token lengths so secret scanners do not flag the fixture.
    text = "token ghp_" + "a" * 20 + " and sk-" + "b" * 16
    cleaned = redact_text(text)
    assert "ghp_" not in cleaned
    assert "sk-" not in cleaned
    assert "[REDACTED]" in cleaned


def test_redacts_assignment_values_and_bearer_headers():
    cleaned = redact_text('{"api_key": "supersecretvalue"} Authorization: Bearer abcdefghijklmnop')
    assert "supersecretvalue" not in cleaned
    assert "abcdefghijklmnop" not in cleaned


def test_redacts_registered_runtime_secret():
    register_secret("runtime-secret-value")
    assert "runtime-secret-value" not in redact_text("value=runtime-secret-value")


def test_redacts_nested_structures():
    payload = {"a": ["ghp_" + "x" * 30], "b": {"password": "hunter2hunter2"}}
    cleaned = redact_value(payload)
    assert "ghp_" not in str(cleaned)
    assert "hunter2hunter2" not in str(cleaned)


def test_safe_filename_strips_paths_and_reserved_names():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("CON.txt").startswith("_")
    assert safe_filename('bad<>:"|?*name.csv') == "bad_______name.csv"
    assert safe_filename("") == "file"
    assert safe_filename("a" * 400).__len__() <= 120


def test_safe_join_rejects_escape(tmp_path: Path):
    base = tmp_path / "base"
    base.mkdir()
    with pytest.raises(ValidationError):
        safe_join(base, "..", "outside.txt")
    with pytest.raises(ValidationError):
        safe_join(base, str(tmp_path / "absolute.txt"))
    assert safe_join(base, "inside", "file.txt").is_relative_to(base.resolve())


def test_stable_hash_is_key_order_independent():
    assert stable_json_hash({"a": 1, "b": [1, 2]}) == stable_json_hash({"b": [1, 2], "a": 1})
    assert stable_json_hash({"a": 1}) != stable_json_hash({"a": 2})
    assert sha256_text("abc") == sha256_text("abc")


@hypothesis_settings(max_examples=100, deadline=None)
@given(st.text(min_size=0, max_size=200))
def test_safe_filename_never_escapes(name: str):
    result = safe_filename(name)
    assert "/" not in result and "\\" not in result
    assert result not in {".", ".."}
    assert len(result) <= 120
