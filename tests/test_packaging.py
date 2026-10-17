# tests/test_packaging.py
"""
Tests for the packaging metadata of pyfwg (setup.py).
"""

import os
import re
import ast
import pytest

SETUP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "setup.py")


def setup_argument(name):
    """Returns the value of a keyword argument of the setup() call in setup.py."""
    with open(SETUP_PY, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} was not found in setup.py")


def install_requires():
    """Returns the names of the packages listed in the install_requires argument of setup.py."""
    requirements = setup_argument("install_requires")
    return [re.split(r"[<>=!~;\[ ]", requirement, maxsplit=1)[0].strip().lower() for requirement in requirements]


@pytest.mark.skipif(not os.path.exists(SETUP_PY), reason="setup.py is not available")
def test_excel_dependency_is_installed():
    """
    export_template_to_excel and load_runs_from_excel need openpyxl, which pandas
    does not install, so it must be a dependency of pyfwg.
    """
    assert "openpyxl" in install_requires()
    assert "pandas" in install_requires()


@pytest.mark.skipif(not os.path.exists(SETUP_PY), reason="setup.py is not available")
def test_docs_extra_includes_ipython():
    """
    nbsphinx highlights the code cells of the tutorial notebooks with the 'ipython3'
    Pygments lexer, which IPython provides. Without it, Read the Docs shows them as
    plain text.
    """
    assert "ipython" in setup_argument("extras_require")["docs"]
