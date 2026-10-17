
# tests/test_init.py
"""
Tests for the pyfwg package initialization.
This module ensures that the public API is correctly exposed when the package is imported.
It verifies that the key classes, functions, and constants are accessible at the top level.
"""

import io
import os
import sys
import logging
import subprocess
import pytest
from unittest.mock import patch

import pyfwg

def test_public_api_availability():
    """
    Test that all intended components are available in the public pyfwg namespace.
    This check prevents regression errors where internal refactoring might accidentally
    break the way users interact with the library.
    """
    
    # --- Classes ---
    # These are the main entry points for users to define their workflows.
    assert hasattr(pyfwg, "MorphingWorkflowGlobal"), "Workflow for Global models should be reachable via pyfwg.MorphingWorkflowGlobal"
    assert hasattr(pyfwg, "MorphingWorkflowEurope"), "Workflow for European models should be reachable via pyfwg.MorphingWorkflowEurope"
    assert hasattr(pyfwg, "MorphingWorkflowCordex"), "Workflow for CORDEX regional models should be reachable via pyfwg.MorphingWorkflowCordex"
    assert hasattr(pyfwg, "MorphingIterator"), "The parametric study iterator should be reachable via pyfwg.MorphingIterator"
    
    # --- High-Level API Functions ---
    # Convenience functions for running the whole process in one line.
    assert hasattr(pyfwg, "morph_epw_global")
    assert hasattr(pyfwg, "morph_epw_europe")
    assert hasattr(pyfwg, "morph_epw_cordex")
    
    # --- Utility Functions ---
    # Functions for specific tasks like checking LCZ availability or copying tutorials.
    assert hasattr(pyfwg, "uhi_morph")
    assert hasattr(pyfwg, "check_lcz_availability")
    assert hasattr(pyfwg, "copy_tutorials")
    assert hasattr(pyfwg, "get_available_lczs")
    assert hasattr(pyfwg, "export_template_to_excel")
    assert hasattr(pyfwg, "load_runs_from_excel")
    assert hasattr(pyfwg, "detect_fwg_version")
    assert hasattr(pyfwg, "detect_fwg_tool")
    assert hasattr(pyfwg, "get_fwg_cli_style")
    assert hasattr(pyfwg, "get_fwg_distribution_info")
    assert hasattr(pyfwg, "sanitize_epw_minutes")
    assert hasattr(pyfwg, "get_fwg_parameters_info")
    assert hasattr(pyfwg, "enable_console_logging")
    
    # --- Constants ---
    # Predefined lists of models and scenarios used across the package.
    assert hasattr(pyfwg, "DEFAULT_GLOBAL_GCMS")
    assert hasattr(pyfwg, "DEFAULT_EUROPE_RCMS")
    assert hasattr(pyfwg, "GLOBAL_SCENARIOS")
    assert hasattr(pyfwg, "EUROPE_SCENARIOS")
    assert hasattr(pyfwg, "ALL_POSSIBLE_YEARS")
    assert hasattr(pyfwg, "DEFAULT_CORDEX_RCMS")
    assert hasattr(pyfwg, "CORDEX_REGIONS")
    assert hasattr(pyfwg, "CORDEX_SCENARIOS")
    
    # --- Version ---
    # Metadata about the current installation.
    assert hasattr(pyfwg, "__version__")
    assert isinstance(pyfwg.__version__, str)

def test_import_does_not_configure_logging():
    """
    Importing pyfwg (in a fresh interpreter) leaves the handlers and the level of
    the root logger untouched and only adds a NullHandler to the 'pyfwg' logger.
    """
    code = "\n".join([
        "import logging, sys",
        "root = logging.getLogger()",
        "handler = logging.StreamHandler(sys.stdout)",
        "root.addHandler(handler)",
        "root.setLevel(logging.WARNING)",
        "import pyfwg",
        "assert root.handlers == [handler], root.handlers",
        "assert root.level == logging.WARNING, root.level",
        "assert [type(h).__name__ for h in logging.getLogger('pyfwg').handlers] == ['NullHandler']",
        "print('ok')",
    ])
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(pyfwg.__file__)))
    python_path = os.pathsep.join(filter(None, [package_root, os.environ.get("PYTHONPATH")]))
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300,
                            env=dict(os.environ, PYTHONPATH=python_path))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"

@pytest.fixture
def pyfwg_logger():
    """Restores the handlers, level and propagation of the 'pyfwg' logger after the test."""
    package_logger = logging.getLogger("pyfwg")
    handlers, level, propagate = list(package_logger.handlers), package_logger.level, package_logger.propagate
    yield package_logger
    package_logger.handlers[:] = handlers
    package_logger.setLevel(level)
    package_logger.propagate = propagate

def test_enable_console_logging(pyfwg_logger):
    """
    The helper prints the messages of pyfwg on the console without touching the
    root logger. Calling it again replaces the handler, so messages are not duplicated.
    """
    stream = io.StringIO()
    pyfwg.enable_console_logging(stream=stream, color=False)
    handler = pyfwg.enable_console_logging(level="INFO", stream=stream, color=False)

    assert [h for h in pyfwg_logger.handlers if not isinstance(h, logging.NullHandler)] == [handler]
    assert handler not in logging.getLogger().handlers
    logging.getLogger("pyfwg.workflow").info("Mapped file")
    logging.getLogger("pyfwg.workflow").debug("Hidden detail")
    assert stream.getvalue().count("INFO - Mapped file") == 1
    assert "Hidden detail" not in stream.getvalue()

def test_enable_console_logging_colors_are_optional(pyfwg_logger):
    """Without the optional colorlog package, plain messages are printed."""
    stream = io.StringIO()
    with patch.dict(sys.modules, {"colorlog": None}):
        handler = pyfwg.enable_console_logging(level=logging.WARNING, stream=stream)
    assert type(handler.formatter) is logging.Formatter
    logging.getLogger("pyfwg.utils").warning("Plain warning")
    logging.getLogger("pyfwg.utils").info("Hidden progress")
    assert "WARNING - Plain warning" in stream.getvalue()
    assert "Hidden progress" not in stream.getvalue()

def test_enable_console_logging_with_colors(pyfwg_logger):
    """With colorlog installed, the messages are colored by level."""
    colorlog = pytest.importorskip("colorlog")
    stream = io.StringIO()
    handler = pyfwg.enable_console_logging(stream=stream)
    assert isinstance(handler.formatter, colorlog.ColoredFormatter)
    logging.getLogger("pyfwg.api").error("Colored error")
    assert "Colored error" in stream.getvalue()
