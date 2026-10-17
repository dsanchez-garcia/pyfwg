# tests/test_tutorials.py
"""
Tests for the tutorial notebooks, which are distributed in the wheel (pyfwg/tutorials)
and rendered in the documentation (docs/source/tutorials).
"""

import os
import re
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TUTORIALS_DIR = os.path.join(ROOT, "pyfwg", "tutorials")
DOCS_TUTORIALS_DIR = os.path.join(ROOT, "docs", "source", "tutorials")
NOTEBOOKS = sorted(f for f in os.listdir(TUTORIALS_DIR) if f.endswith(".ipynb"))

# Absolute paths that reveal the user name or the personal folders of the computer where the
# notebooks were run. In the JSON of the notebooks, each backslash of a path is escaped.
PERSONAL_PATH = re.compile(r"[A-Za-z]:\\+Users\\+|/home/[^/\s\"']+/|/Users/[^/\s\"']+/|OneDrive", re.IGNORECASE)


def read_notebook(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_notebook_has_no_personal_paths(name):
    """
    The JAR paths must be built from FWG_JAR_DIR, and the saved outputs must not show the
    user name or personal folders (they use the <FWG_JAR_DIR>, <TEMP> and <HOME> placeholders).
    """
    for directory in (TUTORIALS_DIR, DOCS_TUTORIALS_DIR):
        path = os.path.join(directory, name)
        if os.path.exists(path):
            assert PERSONAL_PATH.findall(read_notebook(path)) == [], path


@pytest.mark.skipif(not os.path.isdir(DOCS_TUTORIALS_DIR), reason="the documentation sources are not available")
@pytest.mark.parametrize("name", NOTEBOOKS)
def test_docs_copy_matches_package_notebook(name):
    """The documentation renders a copy of each tutorial notebook, which must be kept identical."""
    assert read_notebook(os.path.join(DOCS_TUTORIALS_DIR, name)) == read_notebook(os.path.join(TUTORIALS_DIR, name))


@pytest.mark.parametrize("name", NOTEBOOKS)
def test_notebook_is_valid(name):
    """The notebooks must follow the nbformat schema, e.g., after editing them by hand."""
    nbformat = pytest.importorskip("nbformat")
    nbformat.validate(nbformat.read(os.path.join(TUTORIALS_DIR, name), as_version=nbformat.NO_CONVERT))
