
# tests/test_init.py
"""
Tests for the pyfwg package initialization.
This module ensures that the public API is correctly exposed when the package is imported.
It verifies that the key classes, functions, and constants are accessible at the top level.
"""

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
    assert hasattr(pyfwg, "MorphingIterator"), "The parametric study iterator should be reachable via pyfwg.MorphingIterator"
    
    # --- High-Level API Functions ---
    # Convenience functions for running the whole process in one line.
    assert hasattr(pyfwg, "morph_epw_global")
    assert hasattr(pyfwg, "morph_epw_europe")
    
    # --- Utility Functions ---
    # Functions for specific tasks like checking LCZ availability or copying tutorials.
    assert hasattr(pyfwg, "uhi_morph")
    assert hasattr(pyfwg, "check_lcz_availability")
    assert hasattr(pyfwg, "copy_tutorials")
    assert hasattr(pyfwg, "get_available_lczs")
    assert hasattr(pyfwg, "export_template_to_excel")
    assert hasattr(pyfwg, "load_runs_from_excel")
    assert hasattr(pyfwg, "detect_fwg_version")
    assert hasattr(pyfwg, "sanitize_epw_minutes")
    assert hasattr(pyfwg, "get_fwg_parameters_info")
    
    # --- Constants ---
    # Predefined lists of models and scenarios used across the package.
    assert hasattr(pyfwg, "DEFAULT_GLOBAL_GCMS")
    assert hasattr(pyfwg, "DEFAULT_EUROPE_RCMS")
    assert hasattr(pyfwg, "GLOBAL_SCENARIOS")
    assert hasattr(pyfwg, "EUROPE_SCENARIOS")
    assert hasattr(pyfwg, "ALL_POSSIBLE_YEARS")
    
    # --- Version ---
    # Metadata about the current installation.
    assert hasattr(pyfwg, "__version__")
    assert isinstance(pyfwg.__version__, str)
