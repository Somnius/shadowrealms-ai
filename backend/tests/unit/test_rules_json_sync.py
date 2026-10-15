"""docs/rules/*.json is the source of truth; frontend/src/rules/*.json must be the same file."""

import os

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


@pytest.mark.parametrize("name", ["v5.json", "classic.json"])
def test_frontend_rules_copy_matches_docs(name):
    docs = os.path.join(REPO, "docs", "rules", name)
    front = os.path.join(REPO, "frontend", "src", "rules", name)
    if not (os.path.exists(docs) and os.path.exists(front)):
        pytest.skip("needs the whole repo (not available inside the backend container)")
    with open(docs, "rb") as a, open(front, "rb") as b:
        assert a.read() == b.read(), f"frontend/src/rules/{name} differs from docs/rules/{name}: cp docs/rules/{name} frontend/src/rules/{name}"
