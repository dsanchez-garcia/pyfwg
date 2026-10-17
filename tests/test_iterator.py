
# tests/test_iterator.py
"""
Unit tests for MorphingIterator in pyfwg.iterator.
The Iterator automates multiple morphing runs from a structured input (Pandas DataFrame).
It handles merging defaults and ensuring that no output file overwrites another.
"""

import os
import logging
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from pyfwg.iterator import MorphingIterator
from pyfwg.workflow import MorphingWorkflowGlobal, MorphingWorkflowEurope
from pyfwg.utils import load_runs_from_excel

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

def test_set_default_values_warning(mock_workflow_class, caplog):
    """
    Test that the iterator warns the user if they provide an invalid default argument.
    Example: providing RCP/RCM arguments for a Global (SSP/GCM) tool.
    """
    iterator = MorphingIterator(mock_workflow_class)
    # Global workflow doesn't use rcm_pairs; it uses gcms.
    with caplog.at_level(logging.WARNING, logger="pyfwg"):
        iterator.set_default_values(fwg_rcm_pairs=["Pair1"])
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "fwg_rcm_pairs" in warnings[0].getMessage()
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

# --- Overwrite validation, defaults and documented examples ---

CITY_MAPPING = {"city": {"Seville": "sevilla", "London": "london"}}

@pytest.fixture
def seville_epw(tmp_path):
    """Fixture that creates a dummy EPW file for Seville."""
    epw = tmp_path / "sevilla_2010.epw"
    epw.write_text("dummy epw content")
    return str(epw)

def make_iterator(**defaults):
    """Helper that creates an iterator for Global v4 runs without UHI."""
    iterator = MorphingIterator(MorphingWorkflowGlobal)
    iterator.set_default_values(fwg_jar_path="FWG_v4.jar", fwg_version=4, fwg_add_uhi=False, **defaults)
    return iterator

def test_overwrite_check_uses_the_output_folder_of_each_run(seville_epw, tmp_path):
    """Runs that write the same filenames to different folders do not collide."""
    iterator = make_iterator(output_filename_pattern="{city}_{ssp}_{year}")
    runs_df = pd.DataFrame({
        "epw_paths": [seville_epw] * 2,
        "final_output_dir": [str(tmp_path / "out_a"), str(tmp_path / "out_b")],
    })
    iterator.generate_morphing_workflows(runs_df, keyword_mapping=CITY_MAPPING)
    assert len(iterator.prepared_workflows) == 2

def test_overwrite_check_compares_absolute_paths(seville_epw, tmp_path, monkeypatch):
    """The same folder given as a relative and as an absolute path is detected as a collision."""
    monkeypatch.chdir(tmp_path)
    iterator = make_iterator(output_filename_pattern="{city}_{ssp}_{year}")
    runs_df = pd.DataFrame({"epw_paths": [seville_epw] * 2, "final_output_dir": ["out", str(tmp_path / "out")]})
    with pytest.raises(ValueError, match="Definitive file overwrite"):
        iterator.generate_morphing_workflows(runs_df, keyword_mapping=CITY_MAPPING)
    # No workflows are left ready to run
    assert iterator.prepared_workflows == []

def test_overwrite_check_uses_the_pattern_of_each_run(seville_epw, tmp_path, caplog):
    """
    Each run can have its own output pattern. Runs whose patterns produce the
    same files are detected, even if the pattern of the first run is unique.
    """
    iterator = make_iterator(final_output_dir=str(tmp_path / "out"))
    runs_df = pd.DataFrame({
        "epw_paths": [seville_epw] * 3,
        "fwg_gcms": [["CanESM5"], ["MIROC6"], ["MRI_ESM2_0"]],
        "output_filename_pattern": ["{city}_{ssp}_{year}_{fwg_gcms}", "{city}_{ssp}_{year}", "{city}_{ssp}_{year}"],
    })
    with pytest.raises(ValueError, match="Definitive file overwrite") as error:
        iterator.generate_morphing_workflows(runs_df, keyword_mapping=CITY_MAPPING)
    message = str(error.value)
    # All the scenarios and years of the colliding runs are listed
    assert message.count("run 2 (sevilla_2010.epw), run 3 (sevilla_2010.epw)") == 8
    assert "run 1 " not in message

    # Without raising, the collision is only warned about and all workflows are prepared
    with caplog.at_level(logging.WARNING, logger="pyfwg"):
        iterator.generate_morphing_workflows(runs_df, keyword_mapping=CITY_MAPPING, raise_on_overwrite=False)
    assert len(iterator.prepared_workflows) == 3
    assert "Definitive file overwrite" in caplog.text

def test_overwrite_check_per_input_file(tmp_path):
    """The outputs of every input file of a run are checked, not a single name per run."""
    epws = []
    for name in ("sevilla_2010.epw", "london_2010.epw"):
        epw = tmp_path / name
        epw.write_text("dummy epw content")
        epws.append(str(epw))
    iterator = make_iterator(final_output_dir=str(tmp_path / "out"))

    runs_df = pd.DataFrame({"epw_paths": [epws], "output_filename_pattern": ["future_{ssp}_{year}"]})
    with pytest.raises(ValueError, match="Definitive file overwrite") as error:
        iterator.generate_morphing_workflows(runs_df, keyword_mapping=CITY_MAPPING)
    assert "run 1 (sevilla_2010.epw), run 1 (london_2010.epw)" in str(error.value)

    # With the city in the pattern, each input file has its own outputs
    runs_df["output_filename_pattern"] = ["{city}_{ssp}_{year}"]
    iterator.generate_morphing_workflows(runs_df, keyword_mapping=CITY_MAPPING)
    assert len(iterator.prepared_workflows) == 1

def test_iterator_keeps_fwg_params(seville_epw, tmp_path):
    """
    Parameters that a run does not set are not filled with the workflow defaults,
    so the values of fwg_params (from the run or from set_default_values) apply.
    """
    iterator = make_iterator(final_output_dir=str(tmp_path / "out"),
                             output_filename_pattern="{city}_{ssp}_{year}_{fwg_month_transition_hours}h",
                             fwg_params={"month_transition_hours": 24})
    runs_df = pd.DataFrame({
        "epw_paths": [seville_epw] * 3,
        "fwg_params": [None, {"month_transition_hours": 48}, None],
        # A column with gaps is read as floats (e.g., from Excel)
        "fwg_month_transition_hours": [None, None, 96.0],
    })
    iterator.generate_morphing_workflows(runs_df, keyword_mapping=CITY_MAPPING)

    workflows = iterator.prepared_workflows
    assert [wf.inputs["fwg_params"]["month_transition_hours"] for wf in workflows] == [24, 48, 96]
    assert workflows[2].rename_plan[seville_epw]["ssp126_2050.epw"].endswith("Seville_ssp126_2050_96h.epw")

def test_apply_defaults_with_list_values():
    """A custom list default fills only the missing cells of a column that contains lists."""
    iterator = MorphingIterator(MorphingWorkflowGlobal)
    iterator.set_default_values(fwg_gcms=["CanESM5", "MIROC6"])
    runs_df = pd.DataFrame({
        "epw_paths": ["a.epw", "b.epw", "c.epw"],
        "fwg_gcms": [["MIROC6", "MRI_ESM2_0"], None, float("nan")],
    })
    completed_df = iterator._apply_defaults(runs_df)
    assert completed_df["fwg_gcms"].tolist() == [
        ["MIROC6", "MRI_ESM2_0"], ["CanESM5", "MIROC6"], ["CanESM5", "MIROC6"]
    ]

def test_template_rows_can_be_added_with_loc():
    """The documented way of adding runs to the template DataFrame works, also with lists."""
    iterator = MorphingIterator(MorphingWorkflowGlobal)
    runs_df = iterator.get_template_dataframe()
    runs_df.loc[len(runs_df)] = {'epw_paths': 'file1.epw', 'fwg_gcms': ['CanESM5']}
    runs_df.loc[len(runs_df)] = {'epw_paths': 'file2.epw', 'fwg_gcms': ['MIROC6']}
    assert runs_df["epw_paths"].tolist() == ["file1.epw", "file2.epw"]
    assert runs_df["fwg_gcms"].tolist() == [["CanESM5"], ["MIROC6"]]

def test_excel_runs_with_gaps_reach_the_tool_with_the_right_types(seville_epw, tmp_path):
    """
    Columns read from Excel with empty cells (integers read as floats, flags
    typed as text) reach the command line and the filenames with the right types.
    """
    file_path = tmp_path / "runs.xlsx"
    pd.DataFrame({
        "epw_paths": [seville_epw, seville_epw],
        "fwg_epw_original_lcz": [None, 13],
        "fwg_add_uhi": ["False", None],
    }).to_excel(file_path, index=False)
    runs_df = load_runs_from_excel(str(file_path))
    # pandas reads the column with an empty cell as floats (13.0)
    assert runs_df["fwg_epw_original_lcz"].dtype.kind == "f"

    iterator = make_iterator(final_output_dir=str(tmp_path / "out"),
                             output_filename_pattern="{city}_{ssp}_{year}_LCZ{fwg_epw_original_lcz}")
    # The UHI default of the helper is removed, so that the Excel values apply
    iterator.custom_defaults.pop("fwg_add_uhi")
    iterator.generate_morphing_workflows(runs_df, keyword_mapping=CITY_MAPPING)

    first, second = iterator.prepared_workflows
    assert "-uhi=false" in first._build_command_new_cli(seville_epw, "temp.epw", "out")
    assert "-uhi=true:13:1" in second._build_command_new_cli(seville_epw, "temp.epw", "out")
    assert second.rename_plan[seville_epw]["ssp126_2050.epw"].endswith("Seville_ssp126_2050_LCZ13.epw")
