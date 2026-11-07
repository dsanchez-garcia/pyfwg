# tests/test_packaging.py
"""
Tests for the packaging metadata of pyfwg (setup.py).
"""

import os
import re
import ast
import pytest

SETUP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "setup.py")
TESTS_WORKFLOW = os.path.join(os.path.dirname(SETUP_PY), ".github", "workflows", "tests.yml")


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


def python_classifiers():
    """Returns the Python versions listed in the classifiers of setup.py (e.g., '3.9')."""
    versions = []
    for classifier in setup_argument("classifiers"):
        match = re.fullmatch(r"Programming Language :: Python :: (\d+\.\d+)", classifier)
        if match:
            versions.append(match.group(1))
    return versions


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


@pytest.mark.skipif(not os.path.exists(TESTS_WORKFLOW), reason="the GitHub Actions workflow is not available")
def test_python_classifiers_match_tested_versions():
    """
    The classifiers must list the Python versions that the GitHub Actions workflow tests,
    starting with the minimum version of python_requires. They listed Python 3.8, which
    pyfwg does not support, and stopped at Python 3.11.
    """
    with open(TESTS_WORKFLOW, encoding="utf-8") as f:
        matrix = re.search(r"python-version: \[(.*)\]", f.read()).group(1)
    tested_versions = re.findall(r"\d+\.\d+", matrix)
    assert python_classifiers() == tested_versions
    assert setup_argument("python_requires") == f">={tested_versions[0]}"
