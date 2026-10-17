
# tests/test_workflow.py
"""
Unit tests for the MorphingWorkflow classes (Global and Europe).
These classes manage the full state machine of a morphing run:
1. Mapping (analyzing filenames)
2. Configuration & Preview (validating settings and planning output names)
3. Execution (running the Java tool)
"""

import os
import logging
import pytest
import shutil
import numpy as np
from unittest.mock import MagicMock, patch
from pyfwg.workflow import MorphingWorkflowGlobal, MorphingWorkflowEurope

@pytest.fixture
def temp_epw(tmp_path):
    """Fixture that creates a dummy EPW file for tests."""
    epw = tmp_path / "madrid_2010.epw"
    epw.write_text("dummy epw content")
    return str(epw)

def configure_global(epw_path, out_dir, pattern="{city}_{ssp}_{year}", **kwargs):
    """Helper that maps one EPW file and configures a Global workflow with a JAR name without version."""
    wf = MorphingWorkflowGlobal()
    wf.map_categories([epw_path], keyword_mapping={"city": {"Madrid": "madrid"}})
    wf.configure_and_preview(final_output_dir=out_dir, output_filename_pattern=pattern,
                             fwg_jar_path="FWG.jar", **kwargs)
    return wf

def test_workflow_mapping_pattern(temp_epw):
    """
    Test Step 1: Mapping categories using a regex pattern.
    Should extract named groups (like 'city') from the filename.
    """
    wf = MorphingWorkflowGlobal()
    pattern = r"(?P<city>.*?)_(?P<year>\d+)"
    wf.map_categories([temp_epw], input_filename_pattern=pattern)
    
    assert temp_epw in wf.epw_categories
    assert wf.epw_categories[temp_epw]["city"] == "madrid"
    assert wf.epw_categories[temp_epw]["year"] == "2010"

def test_workflow_mapping_keywords(temp_epw):
    """
    Test Step 1: Mapping categories using a simple keyword search.
    Useful for unstructured filenames where specific words indicate categories.
    """
    wf = MorphingWorkflowGlobal()
    mapping = {
        "location": {"Madrid": ["madrid"]},
        "type": {"Historic": ["2010"]}
    }
    wf.map_categories([temp_epw], keyword_mapping=mapping)
    
    assert temp_epw in wf.epw_categories
    assert wf.epw_categories[temp_epw]["location"] == "Madrid"
    assert wf.epw_categories[temp_epw]["type"] == "Historic"

def test_workflow_incomplete_mapping(temp_epw):
    """
    Test behavior when not all categories are found in a filename.
    The file should be moved to 'incomplete_epw_categories'.
    """
    wf = MorphingWorkflowGlobal()
    mapping = {
        "location": {"Madrid": ["madrid"]},
        "missing_cat": {"Value": ["notfound"]} # This category won't match
    }
    wf.map_categories([temp_epw], keyword_mapping=mapping)
    
    assert temp_epw in wf.incomplete_epw_categories
    # The 'missing_cat' should be absent because it wasn't found
    assert "missing_cat" not in wf.incomplete_epw_categories[temp_epw]

def test_configure_and_preview_global(temp_epw, tmp_path):
    """
    Test Step 2: Planning the output files for the Global tool.
    Should generate a 'rename_plan' describing the final paths.
    """
    wf = MorphingWorkflowGlobal()
    wf.map_categories([temp_epw], keyword_mapping={"city": {"Madrid": "madrid"}})
    
    out_dir = str(tmp_path / "out")
    wf.configure_and_preview(
        final_output_dir=out_dir,
        output_filename_pattern="{city}_{ssp}_{year}",
        fwg_jar_path="FWG_v4.jar",
        fwg_gcms=["CanESM5"],
        fwg_version=4
    )
    
    assert wf.is_config_valid, "Valid configuration should be marked as such"
    assert temp_epw in wf.rename_plan
    # Verify one entry in the generated plan
    # For one input file, one scenario (ssp126), and one year (2050)
    plan_entry = wf.rename_plan[temp_epw]["ssp126_2050.epw"]
    assert "Madrid_ssp126_2050.epw" in plan_entry

def test_configure_and_preview_europe(temp_epw, tmp_path):
    """
    Test Step 2: Planning the output files for the Europe tool.
    Similar to global, but uses RCP scenarios and RCM pairs.
    """
    wf = MorphingWorkflowEurope()
    wf.map_categories([temp_epw], keyword_mapping={"city": {"Madrid": "madrid"}})
    
    out_dir = str(tmp_path / "out")
    wf.configure_and_preview(
        final_output_dir=out_dir,
        output_filename_pattern="{city}_{rcp}_{year}",
        fwg_jar_path="FWG_Europe_v2.jar",
        fwg_rcm_pairs=["ICHEC_EC_EARTH_SMHI_RCA4"],
        fwg_version=2
    )
    
    assert wf.is_config_valid
    assert temp_epw in wf.rename_plan
    plan_entry = wf.rename_plan[temp_epw]["rcp26_2050.epw"]
    assert "Madrid_rcp26_2050.epw" in plan_entry

def test_execute_morphing_success(temp_epw, tmp_path):
    """
    Test Step 3: Running the full workflow.
    Mocks the actual Java call to verify the surrounding orchestration logic.
    """
    wf = MorphingWorkflowGlobal()
    wf.map_categories([temp_epw], keyword_mapping={"city": {"Madrid": "madrid"}})
    
    out_dir = str(tmp_path / "out")
    wf.configure_and_preview(
        final_output_dir=out_dir,
        output_filename_pattern="{city}_{ssp}_{year}",
        fwg_jar_path="FWG_v4.jar",
        fwg_version=4,
        fwg_add_uhi=False # Disable UHI check for this unit test
    )
    
    # Patch the methods that interact with external tools or files
    with patch.object(wf, "_execute_single_morph", return_value=True) as mock_exec:
        with patch.object(wf, "_process_generated_files") as mock_proc:
            wf.execute_morphing()
            # Verify internal orchestration
            mock_exec.assert_called_once()
            mock_proc.assert_called_once()

def test_validate_params_invalid():
    """
    Test that invalid parameter values are caught during validation.
    """
    wf = MorphingWorkflowGlobal()
    params = {
        "winter_sd_shift": 5.0, # Range is -2.0 to 2.0
        "fwg_version": "4"
    }
    # Should return False due to out-of-range value
    assert wf._validate_fwg_params(params) is False

def test_build_command_v4():
    """
    Test construction of the complex Global v4 key-value command.
    """
    wf = MorphingWorkflowGlobal()
    # Populate the input dictionary with mock values
    wf.inputs = {
        'fwg_jar_path': 'FWG_v4.jar',
        'fwg_params': {
            'fwg_version': '4',
            'create_ensemble': True,
            'winter_sd_shift': 0.0,
            'summer_sd_shift': 0.0,
            'month_transition_hours': 72,
            'use_multithreading': True,
            'interpolation_method_id': 'IDW',
            'solar_hour_adjustment': 'By_Month',
            'diffuse_irradiation_model': 'Engerer_2015',
            'add_uhi': True,
            'epw_original_lcz': 14,
            'target_uhi_lcz': 1,
            'output_type': 'EPW',
            'gcms': ['CanESM5']
        }
    }
    wf.java_class_path_prefix = "futureweathergenerator"
    # Construct the command list
    cmd = wf._build_command_new_cli("orig.epw", "temp.epw", "out")
    
    # Assert specific flags and values are correctly placed in the command list
    assert "-models=CanESM5" in cmd
    assert "-uhi=true:14:1" in cmd
    assert "-output_type=EPW" in cmd

def test_build_command_v3():
    """
    Test construction of the legacy Global v3 positional command.
    """
    wf = MorphingWorkflowGlobal()
    wf.inputs = {
        'fwg_jar_path': 'FWG_v3.jar',
        'fwg_params': {'fwg_version': '3'},
        'fwg_params_formatted': {
            'models': 'CanESM5',
            'ensemble': '1',
            'sd_shift': '0.0:0.0',
            'month_transition_hours': '72',
            'do_multithred_computation': 'true',
            'interpolation_method_id': '0',
            'do_limit_variables': 'true',
            'solar_hour_adjustment_option': '1',
            'diffuse_irradiation_model_option': '1',
            'uhi_combined': '1:14:1'
        }
    }
    wf.java_class_path_prefix = "futureweathergenerator"
    # Construct the legacy command
    cmd = wf._build_command_v3("orig.epw", "temp.epw", "out", wf.inputs['fwg_params_formatted'])
    
    assert "futureweathergenerator.Morph" in cmd # The main class for v3
    assert "CanESM5" in cmd
    assert "1:14:1" in cmd # The encoded UHI string

# --- Parameter precedence and type normalization ---

def test_fwg_params_used_when_arguments_are_not_passed(temp_epw, tmp_path):
    """
    The values of fwg_params apply to the parameters that are not passed as
    explicit fwg_ arguments, instead of being replaced by their defaults.
    """
    wf = configure_global(temp_epw, str(tmp_path / "out"), fwg_version=4, fwg_params={
        "winter_sd_shift": 1.5,
        "month_transition_hours": 24,
        "create_ensemble": False,
        "interpolation_method_id": 2,
        "epw_original_lcz": 6,
        "output_type": "SPAIN_MET",
    })
    assert wf.is_config_valid
    params = wf.inputs["fwg_params"]
    assert params["winter_sd_shift"] == 1.5
    assert params["month_transition_hours"] == 24
    assert params["create_ensemble"] is False
    assert params["interpolation_method_id"] == 2

    cmd = wf._build_command_new_cli(temp_epw, "temp.epw", "out")
    assert "-temp_shift_winter=1.5" in cmd
    assert "-smooth_hours=24" in cmd
    assert "-ensemble=false" in cmd
    assert "-grid_interpolation_method=AVG4P" in cmd
    assert "-uhi=true:6:1" in cmd
    assert "-output_type=SPAIN_MET" in cmd

def test_explicit_arguments_override_fwg_params(temp_epw, tmp_path):
    """
    An explicit fwg_ argument overrides fwg_params, even when it is passed with
    its default value. Parameters set in neither place take the defaults.
    """
    wf = configure_global(temp_epw, str(tmp_path / "out"), fwg_version=4,
                          fwg_params={"month_transition_hours": 24, "winter_sd_shift": 1.5},
                          fwg_month_transition_hours=72)
    params = wf.inputs["fwg_params"]
    assert params["month_transition_hours"] == 72
    assert params["winter_sd_shift"] == 1.5
    assert params["summer_sd_shift"] == 0.0
    assert params["create_ensemble"] is True
    assert params["interpolation_method_id"] == 0
    assert params["epw_original_lcz"] == 14
    assert params["output_type"] == "EPW"

def test_float_values_reach_the_tool_as_integers(temp_epw, tmp_path):
    """
    Integer parameters given as floats or NumPy numbers (e.g., read from Excel or
    from a DataFrame with gaps) reach the command line and the filenames as integers.
    """
    kwargs = dict(
        fwg_epw_original_lcz=14.0,
        fwg_target_uhi_lcz=np.float64(2.0),
        fwg_month_transition_hours=np.int64(72),
        fwg_interpolation_method_id=0.0,
        fwg_solar_hour_adjustment=2.0,
        fwg_diffuse_irradiation_model=np.float64(0.0),
        fwg_winter_sd_shift="0.5",
    )
    out_dir = str(tmp_path / "out")

    # Global v4: key-value command line
    wf = configure_global(temp_epw, out_dir, pattern="{city}_{ssp}_{year}_LCZ{fwg_epw_original_lcz}",
                          fwg_version=4, **kwargs)
    assert wf.is_config_valid
    cmd = wf._build_command_new_cli(temp_epw, "temp.epw", "out")
    assert "-uhi=true:14:2" in cmd
    assert "-smooth_hours=72" in cmd
    assert "-temp_shift_winter=0.5" in cmd
    assert "-grid_interpolation_method=IDW" in cmd
    assert "-solar_correction=By_Day" in cmd
    assert "-diffuse_method=Ridley_Boland_Lauret_2010" in cmd
    assert wf.rename_plan[temp_epw]["ssp126_2050.epw"].endswith("Madrid_ssp126_2050_LCZ14.epw")

    # Global v3: positional command line
    wf = configure_global(temp_epw, out_dir, fwg_version=3.0, **kwargs)
    assert wf.is_config_valid
    assert wf.inputs["fwg_params"]["fwg_version"] == "3"
    formatted = wf.inputs["fwg_params_formatted"]
    assert formatted["uhi_combined"] == "1:14:2"
    assert formatted["month_transition_hours"] == "72"
    assert formatted["sd_shift"] == "0.5:0.0"
    assert formatted["interpolation_method_id"] == "0"
    assert formatted["solar_hour_adjustment_option"] == "2"
    assert formatted["diffuse_irradiation_model_option"] == "0"

    # FWG Engine
    wf = configure_global(temp_epw, out_dir, fwg_version=5, fwg_month_transition_hours=48.0, fwg_timeframes=2050.0)
    assert wf.is_config_valid
    cmd = wf._build_command_engine(temp_epw, "temp.epw", "out")
    assert "-smooth_hours=48" in cmd
    assert "-timeframes=2050" in cmd

@pytest.mark.parametrize("invalid_kwargs", [
    {"fwg_epw_original_lcz": 14.5},
    {"fwg_target_uhi_lcz": "two"},
    {"fwg_month_transition_hours": 72.5},
    {"fwg_winter_sd_shift": "high"},
    {"fwg_summer_sd_shift": float("nan")},
    {"fwg_interpolation_method_id": 1.5},
    {"fwg_interpolation_method_id": True},
])
def test_invalid_numbers_are_rejected(temp_epw, tmp_path, invalid_kwargs):
    """Values that are not valid numbers make the configuration invalid, without errors or truncation."""
    wf = configure_global(temp_epw, str(tmp_path / "out"), fwg_version=4, **invalid_kwargs)
    assert not wf.is_config_valid

def test_boolean_flags_are_interpreted_strictly(temp_epw, tmp_path, caplog):
    """
    Flags given as 1/0, NumPy booleans or 'True'/'False' strings (e.g., read from
    Excel) mean the same with every version of the tool.
    """
    out_dir = str(tmp_path / "out")

    # Global v4: key-value command line
    wf = configure_global(temp_epw, out_dir, fwg_version=4, fwg_add_uhi=1, fwg_create_ensemble="False",
                          fwg_use_multithreading=np.bool_(False), fwg_limit_variables=0.0)
    assert wf.is_config_valid
    cmd = wf._build_command_new_cli(temp_epw, "temp.epw", "out")
    assert "-uhi=true:14:1" in cmd
    assert "-ensemble=false" in cmd
    assert "-multithread=false" in cmd
    assert "-epw_dictionary_limits=false" in cmd

    # Global v3: positional command line
    wf = configure_global(temp_epw, out_dir, fwg_version=3, fwg_add_uhi="False", fwg_create_ensemble=0,
                          fwg_use_multithreading="TRUE", fwg_limit_variables=np.bool_(True))
    assert wf.is_config_valid
    formatted = wf.inputs["fwg_params_formatted"]
    assert formatted["uhi_combined"] == "0:14:1"
    assert formatted["ensemble"] == "0"
    assert formatted["do_multithred_computation"] == "true"
    assert formatted["do_limit_variables"] == "true"

    # FWG Engine: 'False' does not request the (unsupported) UHI effect
    with caplog.at_level(logging.WARNING, logger="pyfwg"):
        wf = configure_global(temp_epw, out_dir, fwg_version=5, fwg_gcms=["CanESM5", "MIROC6"],
                              fwg_create_ensemble="false", fwg_add_uhi="False")
    assert wf.is_config_valid
    assert "-ensemble=false" in wf._build_command_engine(temp_epw, "temp.epw", "out")
    assert "Urban Heat Island" not in caplog.text

@pytest.mark.parametrize("invalid_kwargs", [
    {"fwg_add_uhi": "maybe"},
    {"fwg_create_ensemble": 2},
    {"fwg_use_multithreading": "yes"},
    {"fwg_limit_variables": 0.5},
])
def test_invalid_flags_are_rejected(temp_epw, tmp_path, invalid_kwargs):
    """Values that are not booleans make the configuration invalid instead of being guessed."""
    wf = configure_global(temp_epw, str(tmp_path / "out"), fwg_version=4, **invalid_kwargs)
    assert not wf.is_config_valid
