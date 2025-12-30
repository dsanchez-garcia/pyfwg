
# tests/test_iterator.py
"""
Unit tests for MorphingIterator in pyfwg.iterator.
The Iterator automates multiple morphing runs from a structured input (Pandas DataFrame).
It handles merging defaults and ensuring that no output file overwrites another.
"""

import os
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from pyfwg.iterator import MorphingIterator
from pyfwg.workflow import MorphingWorkflowGlobal, MorphingWorkflowEurope

@pytest.fixture
def mock_workflow_class():
    """
    Fixture that creates a mocked Workflow class.
    Simulates the structure of a real Workflow class without its complexity.
    """
    mock_wf_cls = MagicMock(spec=MorphingWorkflowGlobal)
    mock_wf_cls.model_arg_name = "gcms"
    mock_wf_cls.scenario_placeholder_name = "ssp"
    mock_wf_cls.tool_scenarios = ["ssp126", "ssp245"]
    mock_wf_cls.valid_models = {"CanESM5", "MIROC6"}
    mock_wf_cls.__name__ = "MorphingWorkflowGlobal"
    
    # We must also mock the signature of the configure method for introspective methods like get_template_dataframe
    import inspect
    mock_wf_cls.configure_and_preview.__signature__ = inspect.signature(MorphingWorkflowGlobal.configure_and_preview)
    return mock_wf_cls

def test_iterator_init(mock_workflow_class):
    """Test that the iterator initializes correctly with a workflow class."""
    iterator = MorphingIterator(mock_workflow_class)
    assert iterator.workflow_class == mock_workflow_class
    assert iterator.custom_defaults == {}

def test_set_default_values(mock_workflow_class):
    """Test setting global defaults that will apply to all runs in the batch."""
    iterator = MorphingIterator(mock_workflow_class)
    # Set a JAR path and a model list that should be shared by all runs
    iterator.set_default_values(fwg_jar_path="FWG.jar", fwg_gcms=["CanESM5"])
    assert iterator.custom_defaults["fwg_jar_path"] == "FWG.jar"
    assert iterator.custom_defaults["fwg_gcms"] == ["CanESM5"]

def test_set_default_values_warning(mock_workflow_class):
    """
    Test that the iterator warns the user if they provide an invalid default argument.
    Example: providing RCP/RCM arguments for a Global (SSP/GCM) tool.
    """
    iterator = MorphingIterator(mock_workflow_class)
    # Global workflow doesn't use rcm_pairs; it uses gcms.
    with patch("logging.warning") as mock_warn:
        iterator.set_default_values(fwg_rcm_pairs=["Pair1"])
        mock_warn.assert_called_once()
        # The invalid argument should be discarded after warning
        assert "fwg_rcm_pairs" not in iterator.custom_defaults

def test_get_template_dataframe():
    """
    Test the dynamic generation of a template DataFrame.
    The columns should match the signature of the workflow's configuration method.
    """
    iterator = MorphingIterator(MorphingWorkflowGlobal)
    df = iterator.get_template_dataframe()
    # Check for core iterator columns
    assert "epw_paths" in df.columns
    # Check for workflow-specific columns extracted from signature
    assert "fwg_jar_path" in df.columns
    assert "fwg_gcms" in df.columns

def test_apply_defaults():
    """
    Test the merging of defaults into a sparse runs DataFrame.
    Priority: Row Value > custom_defaults > Hardcoded Defaults.
    """
    iterator = MorphingIterator(MorphingWorkflowGlobal)
    # Set a custom default
    iterator.set_default_values(fwg_jar_path="default.jar")
    
    # Create a DataFrame where one run has a missing JAR path
    runs_df = pd.DataFrame({"epw_paths": ["test.epw"]})
    completed_df = iterator._apply_defaults(runs_df)
    
    # The missing JAR path should be filled with the one from custom_defaults
    assert completed_df["fwg_jar_path"].iloc[0] == "default.jar"
    # Essential settings like delete_temp_files should be filled from the hardcoded defaults
    assert completed_df["delete_temp_files"].iloc[0] == True

def test_generate_morphing_workflows(tmp_path):
    """
    Test Step 4: Generating the full execution plan.
    This involves mapping file categories and preparing workflow instances.
    """
    iterator = MorphingIterator(MorphingWorkflowGlobal)
    
    # Create a dummy file with a pattern in its name
    epw = tmp_path / "london_uhi-type-2.epw"
    epw.write_text("content")
    
    # Define a single run in the DataFrame
    runs_df = pd.DataFrame({
        "epw_paths": [str(epw)],
        "fwg_gcms": [["CanESM5"]],
        "final_output_dir": str(tmp_path / "out"),
        "output_filename_pattern": "{city}_{ssp}_{year}"
    })
    
    # JAR path is required for version detection mock
    runs_df["fwg_jar_path"] = "FWG_v4.jar"
    
    with patch("pyfwg.workflow.detect_fwg_version", return_value="4"):
        iterator.generate_morphing_workflows(
            runs_df,
            input_filename_pattern=r"(?P<city>.*?)_uhi-type-(?P<uhi>\d+)"
        )
    
    # Verify that one workflow was prepared
    assert len(iterator.prepared_workflows) == 1
    # Verify that categories were extracted and added to the plan DataFrame
    assert "cat_city" in iterator.morphing_workflows_plan_df.columns
    assert iterator.morphing_workflows_plan_df["cat_city"].iloc[0] == ["london"]

def test_generate_morphing_workflows_overwrite_error(tmp_path):
    """
    Critical validation test: Prevent multiple runs from overwriting the same file.
    If two runs produce the same output filename, the iterator must raise an error.
    """
    iterator = MorphingIterator(MorphingWorkflowGlobal)
    epw = tmp_path / "test.epw"
    epw.write_text("content")
    
    # Create two runs that are different (different GCMs) but produce the same filename
    # because GCM is NOT in the output pattern.
    runs_df = pd.DataFrame({
        "epw_paths": [str(epw), str(epw)],
        "fwg_gcms": [["CanESM5"], ["MIROC6"]],
        "output_filename_pattern": "constant_file_{ssp}_{year}", # No {fwg_gcms} placeholder!
        "final_output_dir": str(tmp_path / "out")
    })
    
    runs_df["fwg_jar_path"] = "FWG_v4.jar"
    
    # The iterator should detect this collision during the planning phase
    with patch("pyfwg.workflow.detect_fwg_version", return_value="4"):
        with pytest.raises(ValueError, match="Definitive file overwrite"):
            iterator.generate_morphing_workflows(
                runs_df, 
                input_filename_pattern=r"(?P<city>.*)",
                raise_on_overwrite=True
            )

def test_run_morphing_workflows():
    """Test the final execution of the prepared batch of workflows."""
    iterator = MorphingIterator(MorphingWorkflowGlobal)
    # Manually insert a mock workflow into the prepared list
    mock_wf = MagicMock()
    mock_wf.is_config_valid = True
    iterator.prepared_workflows = [mock_wf]
    
    # Execute the batch
    iterator.run_morphing_workflows()
    # Verify that execute_morphing was called on the instance
    mock_wf.execute_morphing.assert_called_once()
