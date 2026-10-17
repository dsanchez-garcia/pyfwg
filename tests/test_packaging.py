# tests/test_packaging.py
"""
Tests for the packaging metadata of pyfwg (setup.py).
"""

import os
import re
import ast
import pytest

SETUP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "setup.py")


def install_requires():
    """Returns the names of the packages listed in the install_requires argument of setup.py."""
    with open(SETUP_PY, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "install_requires":
            requirements = ast.literal_eval(node.value)
            return [re.split(r"[<>=!~;\[ ]", requirement, maxsplit=1)[0].strip().lower() for requirement in requirements]
    raise AssertionError("install_requires was not found in setup.py")


@pytest.mark.skipif(not os.path.exists(SETUP_PY), reason="setup.py is not available")
def test_excel_dependency_is_installed():
    """
    export_template_to_excel and load_runs_from_excel need openpyxl, which pandas
    does not install, so it must be a dependency of pyfwg.
    """
    assert "openpyxl" in install_requires()
    assert "pandas" in install_requires()
