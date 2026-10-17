# tests/test_fwg_engine.py
"""
Unit tests for the support of the FWG Engine distributions.
Since Global v5, Europe v3 and the CORDEX regional distributions (v1.x), all
the Future Weather Generator tools share the same engine. Its command line
uses the '-g' action and new options (scenarios, timeframes, decomposition
methods, uncertainty variants, etc.), writes the weather files to a 'weather'
subfolder and no longer supports the Urban Heat Island (UHI) effect.
These tests use synthetic JAR files and mocks, so no Java installation is needed.
"""

import os
import zipfile
import logging
import subprocess
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from pyfwg.api import morph_epw_cordex, _run_direct_morphing
from pyfwg.iterator import MorphingIterator
from pyfwg.utils import (
    get_fwg_distribution_info,
    detect_fwg_version,
    detect_fwg_tool,
    get_fwg_cli_style,
    uhi_morph,
    check_lcz_availability,
    load_runs_from_excel,
    get_fwg_parameters_info
)
from pyfwg.workflow import MorphingWorkflowGlobal, MorphingWorkflowEurope, MorphingWorkflowCordex

GLOBAL_V5_JAR = "FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar"
EUROPE_V3_JAR = "FutureWeatherGenerator-CORDEX-CMIP5-Europe-EUR-11-v3.2.0.jar"
NAM_JAR = "FutureWeatherGenerator-CORDEX-CMIP5-North-America-NAM-44-v1.2.0.jar"
MNA_JAR = "FutureWeatherGenerator-CORDEX-CMIP5-Middle-East-and-North-Africa-MNA-22-v1.2.0.jar"


@pytest.fixture
def temp_epw(tmp_path):
    """Fixture that creates a dummy EPW file for tests."""
    epw = tmp_path / "sevilla_2010.epw"
    epw.write_text("dummy epw content")
    return str(epw)


def configure(workflow_class, epw_path, out_dir, **kwargs):
    """Helper that maps one EPW file and configures a workflow with a simple pattern."""
    wf = workflow_class()
    wf.map_categories([epw_path], keyword_mapping={"city": {"Seville": "sevilla"}})
    scenario = wf.scenario_placeholder_name
    wf.configure_and_preview(
        final_output_dir=out_dir,
        output_filename_pattern=f"{{city}}_{{{scenario}}}_{{year}}",
        **kwargs
    )
    return wf


# --- Detection utilities ---

def test_get_fwg_distribution_info(make_engine_jar):
    """
    The distribution manifest, the climate-model catalog and the engine version
    are read directly from the JAR (no Java needed).
    """
    jar = make_engine_jar(GLOBAL_V5_JAR, models={
        "CanESM5": {}, "MIROC6": {}, "GISS-E2-2-G": {"ensembleEligible": False}
    })
    info = get_fwg_distribution_info(jar)

    assert info["version"] == "5.2.0"
    assert info["engine_version"] == "1.1.0"
    assert info["tool"] == "global"
    assert info["scenarios"] == ["ssp126", "ssp245", "ssp370", "ssp585"]
    assert info["timeframes"] == ["2050", "2080"]
    assert info["models"] == ["CanESM5", "MIROC6", "GISS-E2-2-G"]
    # Models that are not ensemble-eligible are excluded from the default ensemble
    assert info["ensemble_models"] == ["CanESM5", "MIROC6"]


def test_get_fwg_distribution_info_regional(make_engine_jar):
    """A CORDEX regional JAR is identified by its framework and grid domain."""
    jar = make_engine_jar("regional.jar", version="1.2.0", framework="CORDEX", domain="NAM-44",
                          scenarios=["rcp45", "rcp85"], models={"CCCma-CanESM2-SMHI-RCA4": {}})
    info = get_fwg_distribution_info(jar)

    assert info["tool"] == "cordex"
    assert info["domain"] == "NAM-44"
    assert info["scenarios"] == ["rcp45", "rcp85"]


def test_get_fwg_distribution_info_unavailable(tmp_path):
    """
    JARs prior to the FWG Engine (without a distribution manifest), files that
    are not JARs and missing files return None.
    """
    legacy_jar = tmp_path / "FutureWeatherGenerator_v4.0.2.jar"
    with zipfile.ZipFile(legacy_jar, "w") as jar:
        jar.writestr("futureweathergenerator/Morph.class", "binary")
    not_a_jar = tmp_path / "not_a_jar.jar"
    not_a_jar.write_text("plain text")

    assert get_fwg_distribution_info(str(legacy_jar)) is None
    assert get_fwg_distribution_info(str(not_a_jar)) is None
    assert get_fwg_distribution_info(str(tmp_path / "missing.jar")) is None


def test_detect_fwg_version_from_manifest(make_engine_jar):
    """The version is read from the JAR when its filename does not include it."""
    jar = make_engine_jar("FWG_renamed.jar", version="5.2.0")
    assert detect_fwg_version(jar) == "5"


def test_detect_fwg_tool():
    """The distribution family is identified from the JAR filename."""
    assert detect_fwg_tool(GLOBAL_V5_JAR) == "global"
    assert detect_fwg_tool("FutureWeatherGenerator_v4.0.2.jar") == "global"
    assert detect_fwg_tool(EUROPE_V3_JAR) == "europe"
    assert detect_fwg_tool("FutureWeatherGenerator_Europe_v2.0.2.jar") == "europe"
    assert detect_fwg_tool(NAM_JAR) == "cordex"
    assert detect_fwg_tool("FutureWeatherGenerator_Portugal_v0.1.4.jar") == "portugal"
    # Unknown names are not classified
    assert detect_fwg_tool("FWG_v4.jar") is None


@pytest.mark.parametrize("version, tool, expected", [
    ("3", "global", "positional"),
    ("4", "global", "key_value"),
    ("5", "global", "engine"),
    ("5.2.0", "global", "engine"),
    ("1", "europe", "positional"),
    ("2", "europe", "key_value"),
    ("3", "europe", "engine"),
    ("1", "cordex", "engine"),
])
def test_get_fwg_cli_style(version, tool, expected):
    """Each version of each tool uses one command-line style."""
    assert get_fwg_cli_style(version, tool) == expected


def test_get_fwg_cli_style_invalid():
    """Invalid versions or tools raise a ValueError."""
    with pytest.raises(ValueError):
        get_fwg_cli_style("latest", "global")
    with pytest.raises(ValueError):
        get_fwg_cli_style("1", "portugal")


# --- UHI utilities ---

def test_uhi_morph_not_available_in_engine():
    """
    The FWG Engine does not support the UHI effect. uhi_morph raises an error
    without running the tool, or only logs it if raise_on_error is False.
    """
    with patch("subprocess.run") as mock_run:
        with pytest.raises(ValueError, match="UHI morphing is not available"):
            uhi_morph(fwg_epw_path="test.epw", fwg_jar_path=GLOBAL_V5_JAR, fwg_output_dir="out",
                      fwg_original_lcz=14, fwg_target_lcz=1)
        # With raise_on_error=False, the error is only logged
        uhi_morph(fwg_epw_path="test.epw", fwg_jar_path=NAM_JAR, fwg_output_dir="out",
                  fwg_original_lcz=14, fwg_target_lcz=1, raise_on_error=False)
        mock_run.assert_not_called()


def test_check_lcz_availability_engine(temp_epw):
    """The LCZ check fails gracefully (returns False) for FWG Engine JARs."""
    with patch("subprocess.run") as mock_run:
        result = check_lcz_availability(epw_path=temp_epw, original_lcz=14, target_lcz=1,
                                        fwg_jar_path=EUROPE_V3_JAR)
        assert result is False
        mock_run.assert_not_called()


# --- Global v5 workflow ---

def test_engine_command_global(temp_epw, tmp_path):
    """
    Global v5 uses the FWG Engine command line: the '-g' action, the organized
    output layout and the new options. The UHI, solar hour and legacy diffuse
    options are not passed.
    """
    wf = configure(
        MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"),
        fwg_jar_path=GLOBAL_V5_JAR,
        fwg_gcms=["CanESM5", "MIROC6"],
        fwg_scenarios=["SSP2-4.5"],
        fwg_timeframes=["2050s"],
        fwg_interpolation_method_id=5,
        fwg_decomposition_method="erbs_1982",
        fwg_uncertainty_variant="warm-dry",
        fwg_output_profile="minimal",
        fwg_model_unzipped_folder=str(tmp_path / "cache"),
        fwg_extra_args={"threads": 2, "save_present_day": False}
    )
    assert wf.is_config_valid
    assert wf.cli_style == "engine"

    cmd = wf._build_command_engine(temp_epw, "temp.epw", "out")
    assert cmd[:4] == ["java", "-jar", GLOBAL_V5_JAR, "-g"]
    assert "-output_layout=ORGANIZED" in cmd
    assert "-models=CanESM5,MIROC6" in cmd
    assert "-scenarios=ssp245" in cmd  # Normalized to the scenario ID
    assert "-timeframes=2050" in cmd
    assert "-grid_interpolation_method=SGBI" in cmd
    assert "-decomposition_method=ERBS_1982" in cmd
    assert "-uncertainty_variant=WARM_DRY" in cmd
    assert "-output_profile=MINIMAL" in cmd
    assert f"-model_unzipped_folder={tmp_path / 'cache'}" in cmd
    assert "-threads=2" in cmd
    assert "-save_present_day=false" in cmd
    assert not any(arg.startswith(("-uhi", "-solar_correction", "-diffuse_method")) for arg in cmd)

    # Only the selected scenario and period are planned
    assert list(wf.rename_plan[temp_epw]) == ["ssp245_2050.epw"]


def test_engine_default_command(temp_epw, tmp_path):
    """Options left as None are omitted, so the defaults of the tool apply."""
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"), fwg_jar_path=GLOBAL_V5_JAR)
    assert wf.is_config_valid

    cmd = wf._build_command_engine(temp_epw, "temp.epw", "out")
    # Without fwg_gcms, the tool uses all its ensemble-eligible models
    assert not any(arg.startswith("-models=") for arg in cmd)
    assert not any(arg.startswith(("-scenarios=", "-timeframes=", "-decomposition_method=")) for arg in cmd)
    assert "-ensemble=true" in cmd
    assert "-grid_interpolation_method=IDW" in cmd
    assert "-epw_dictionary_limits=true" in cmd
    # All scenarios and periods are planned
    assert len(wf.rename_plan[temp_epw]) == 8


def test_engine_uhi_disabled(temp_epw, tmp_path, caplog):
    """
    UHI is disabled for FWG Engine runs. By default (fwg_add_uhi=None) no
    warning is logged; an explicit request is warned about and ignored.
    """
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"), fwg_jar_path=GLOBAL_V5_JAR)
    assert wf.inputs["fwg_params"]["add_uhi"] is False

    with caplog.at_level(logging.WARNING):
        wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"),
                       fwg_jar_path=GLOBAL_V5_JAR, fwg_add_uhi=True)
    assert wf.is_config_valid
    assert wf.inputs["fwg_params"]["add_uhi"] is False
    assert "do not support the Urban Heat Island" in caplog.text


def test_legacy_uhi_default(temp_epw, tmp_path):
    """With older versions, fwg_add_uhi=None keeps applying the UHI effect, as before."""
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"),
                   fwg_jar_path="FWG_v4.jar", fwg_version=4)
    assert wf.inputs["fwg_params"]["add_uhi"] is True
    assert "-uhi=true:14:1" in wf._build_command_new_cli(temp_epw, "temp.epw", "out")


def test_engine_single_model_disables_ensemble(temp_epw, tmp_path):
    """The engine needs two models for an ensemble, so a single model disables it."""
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"),
                   fwg_jar_path=GLOBAL_V5_JAR, fwg_gcms=["CanESM5"])
    assert wf.is_config_valid
    assert "-ensemble=false" in wf._build_command_engine(temp_epw, "temp.epw", "out")


def test_legacy_diffuse_model_mapped(temp_epw, tmp_path):
    """A non-default legacy diffuse model is translated into the decomposition method."""
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"),
                   fwg_jar_path=GLOBAL_V5_JAR, fwg_diffuse_irradiation_model=2)
    assert wf.is_config_valid
    assert "-decomposition_method=PAULESCU_BLAGA_2019" in wf._build_command_engine(temp_epw, "temp.epw", "out")


@pytest.mark.parametrize("invalid_kwargs", [
    {"fwg_scenarios": ["ssp999"]},
    {"fwg_timeframes": [2100]},
    {"fwg_scenarios": []},
    {"fwg_decomposition_method": "UNKNOWN_MODEL"},
    {"fwg_illuminance_method": "PEREZ_2000"},
    {"fwg_infrared_method": "BRUNT"},
    {"fwg_uncertainty_sigma": -1},
    {"fwg_interpolation_method_id": 9},
    {"fwg_gcms": ["NotAModel"]},
    # A non-central uncertainty case cannot be combined with seasonal SD shifts
    {"fwg_uncertainty_variant": "PLUS_ONE_SIGMA", "fwg_winter_sd_shift": 1.0},
    # Options set by pyfwg cannot be overridden
    {"fwg_extra_args": {"models": "CanESM5"}},
    {"fwg_extra_args": {"bad option": 1}},
])
def test_engine_invalid_options(temp_epw, tmp_path, invalid_kwargs):
    """Invalid FWG Engine options block the execution."""
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"),
                   fwg_jar_path=GLOBAL_V5_JAR, **invalid_kwargs)
    assert not wf.is_config_valid


def test_engine_only_options_rejected_for_v4(temp_epw, tmp_path):
    """The FWG Engine options cannot be used with Global v4."""
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"),
                   fwg_jar_path="FWG_v4.jar", fwg_version=4, fwg_scenarios=["ssp245"])
    assert not wf.is_config_valid


def test_jar_of_another_distribution(temp_epw, tmp_path):
    """Using the JAR of another distribution (e.g., a CORDEX region) is blocked."""
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"), fwg_jar_path=NAM_JAR)
    assert not wf.is_config_valid


def test_engine_uses_jar_metadata(temp_epw, tmp_path, make_engine_jar):
    """
    The models, scenarios and periods of the JAR are used for validation, and the
    coverage of each model is checked.
    """
    jar = make_engine_jar("FWG_Global.jar", models={
        "CanESM5": {}, "MIROC6": {}, "EC-Earth3": {"scenarios": ["ssp126", "ssp245"]}
    })
    # EC_Earth3 is the same model as 'EC-Earth3' ('_' and '-' are equivalent)
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"), fwg_jar_path=jar,
                   fwg_gcms=["CanESM5", "EC_Earth3"], fwg_scenarios=["ssp245"])
    assert wf.is_config_valid
    assert wf.distribution_info["version"] == "5.2.0"

    # EC-Earth3 does not provide SSP5-8.5
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"), fwg_jar_path=jar,
                   fwg_gcms=["CanESM5", "EC_Earth3"], fwg_scenarios=["ssp585"])
    assert not wf.is_config_valid

    # Models that are not installed in the JAR are rejected
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"), fwg_jar_path=jar,
                   fwg_gcms=["CanESM5", "UKESM1_0_LL"])
    assert not wf.is_config_valid


def test_engine_europe_v3(temp_epw, tmp_path):
    """Europe v3 runs on the FWG Engine and accepts the existing GCM-RCM pair names."""
    wf = configure(MorphingWorkflowEurope, temp_epw, str(tmp_path / "out"), fwg_jar_path=EUROPE_V3_JAR,
                   fwg_rcm_pairs=["ICHEC_EC_EARTH_SMHI_RCA4", "MOHC-HadGEM2-ES-SMHI-RCA4"])
    assert wf.is_config_valid
    assert wf.cli_style == "engine"
    cmd = wf._build_command_engine(temp_epw, "temp.epw", "out")
    assert "-models=ICHEC_EC_EARTH_SMHI_RCA4,MOHC-HadGEM2-ES-SMHI-RCA4" in cmd


# --- Generated files ---

def write_engine_outputs(temp_dir, scenarios=("ssp245",), years=(2050,), model="Ensemble"):
    """Simulates the files written by the FWG Engine with the organized layout."""
    weather_dir = os.path.join(temp_dir, "weather")
    os.makedirs(weather_dir, exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "reports"), exist_ok=True)
    for scenario in scenarios:
        for year in years:
            base = os.path.join(weather_dir, f"ESP_Andalucia_Sevilla_{model}_{scenario}_{year}")
            for ext in (".epw", ".stat"):
                with open(base + ext, "w") as f:
                    f.write("generated")
    # Corrected baseline written by SolarQC, which is not a future scenario
    with open(os.path.join(weather_dir, "ESP_Andalucia_Sevilla_SolarQC_corrected.epw"), "w") as f:
        f.write("baseline")


def test_process_generated_files_engine(temp_epw, tmp_path):
    """The weather files are taken from the 'weather' subfolder and renamed."""
    out_dir = tmp_path / "out"
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(out_dir), fwg_jar_path=GLOBAL_V5_JAR,
                   fwg_scenarios=["ssp245"], fwg_timeframes=[2050])
    temp_dir = tmp_path / "temp"
    write_engine_outputs(str(temp_dir))
    os.makedirs(out_dir)

    wf._process_generated_files(temp_epw, str(temp_dir))

    assert sorted(os.listdir(out_dir)) == ["Seville_ssp245_2050.epw", "Seville_ssp245_2050.stat"]
    # Auxiliary files remain in the temporary folder
    assert os.path.exists(temp_dir / "weather" / "ESP_Andalucia_Sevilla_SolarQC_corrected.epw")


def test_execute_morphing_engine(temp_epw, tmp_path):
    """
    Full workflow with the Java call mocked: the LCZ check is skipped, the tool
    is called once and the generated files are renamed into the output folder.
    """
    out_dir = tmp_path / "out"
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(out_dir), fwg_jar_path=GLOBAL_V5_JAR,
                   temp_base_dir=str(tmp_path / "temp"), fwg_timeframes=[2080])

    def fake_run(command, **kwargs):
        output_folder = next(arg.split("=", 1)[1] for arg in command if arg.startswith("-output_folder="))
        write_engine_outputs(output_folder, scenarios=("ssp126", "ssp245", "ssp370", "ssp585"), years=(2080,))
        return subprocess.CompletedProcess(command, 0)

    with patch("pyfwg.workflow.check_lcz_availability") as mock_lcz:
        with patch("subprocess.run", side_effect=fake_run) as mock_run:
            wf.execute_morphing()
    mock_lcz.assert_not_called()
    mock_run.assert_called_once()
    assert len(os.listdir(out_dir)) == 8
    assert os.path.exists(out_dir / "Seville_ssp585_2080.epw")


def test_execute_single_morph_timeout(temp_epw, tmp_path):
    """A run that exceeds the time limit is reported as failed instead of stopping the workflow."""
    wf = configure(MorphingWorkflowGlobal, temp_epw, str(tmp_path / "out"), fwg_jar_path=GLOBAL_V5_JAR)
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="java", timeout=3600)):
        assert wf._execute_single_morph(temp_epw, str(temp_dir)) is False


# --- CORDEX regional workflow ---

def test_cordex_region_from_filename(temp_epw, tmp_path):
    """
    The region is detected from the JAR filename, and only its scenarios and
    GCM-RCM pairs are accepted.
    """
    wf = configure(MorphingWorkflowCordex, temp_epw, str(tmp_path / "out"), fwg_jar_path=NAM_JAR,
                   fwg_rcm_pairs=["CCCma-CanESM2-SMHI-RCA4", "ICHEC_EC_EARTH_DMI_HIRHAM5"])
    assert wf.is_config_valid
    assert wf.cordex_domain == "NAM-44"
    assert wf.tool_scenarios == ["rcp45", "rcp85"]
    assert sorted(wf.rename_plan[temp_epw]) == ["rcp45_2050.epw", "rcp45_2080.epw",
                                                "rcp85_2050.epw", "rcp85_2080.epw"]
    cmd = wf._build_command_engine(temp_epw, "temp.epw", "out")
    assert "-g" in cmd and not any(arg.startswith("-uhi") for arg in cmd)


@pytest.mark.parametrize("invalid_kwargs", [
    {"fwg_rcm_pairs": ["CCCma-CanESM2-SMHI-RCA4", "MOHC_HadGEM2_ES_SMHI_RCA4"]},  # Not in NAM-44
    {"fwg_scenarios": ["rcp26"]},  # Not available in NAM-44
])
def test_cordex_invalid_options(temp_epw, tmp_path, invalid_kwargs):
    """Scenarios and GCM-RCM pairs of other regions are rejected."""
    wf = configure(MorphingWorkflowCordex, temp_epw, str(tmp_path / "out"), fwg_jar_path=NAM_JAR, **invalid_kwargs)
    assert not wf.is_config_valid


def test_cordex_single_scenario_region(temp_epw, tmp_path):
    """The Middle East and North Africa distribution only provides RCP8.5."""
    wf = configure(MorphingWorkflowCordex, temp_epw, str(tmp_path / "out"), fwg_jar_path=MNA_JAR)
    assert wf.is_config_valid
    assert sorted(wf.rename_plan[temp_epw]) == ["rcp85_2050.epw", "rcp85_2080.epw"]


def test_cordex_region_from_jar_metadata(temp_epw, tmp_path, make_engine_jar):
    """The region, scenarios and models are read from the JAR when available."""
    jar = make_engine_jar("regional.jar", version="1.2.0", framework="CORDEX", domain="SAM-44",
                          scenarios=["rcp26", "rcp85"], models={"MIROC-MIROC5-SMHI-RCA4": {}, "NCC-NorESM1-M-SMHI-RCA4": {}})
    wf = configure(MorphingWorkflowCordex, temp_epw, str(tmp_path / "out"), fwg_jar_path=jar,
                   fwg_rcm_pairs=["MIROC_MIROC5_SMHI_RCA4", "NCC_NorESM1_M_SMHI_RCA4"])
    assert wf.is_config_valid
    assert wf.cordex_domain == "SAM-44"
    assert wf.tool_scenarios == ["rcp26", "rcp85"]


def test_cordex_rejects_global_jar(temp_epw, tmp_path):
    """MorphingWorkflowCordex cannot be used with the Global tool."""
    wf = configure(MorphingWorkflowCordex, temp_epw, str(tmp_path / "out"), fwg_jar_path=GLOBAL_V5_JAR)
    assert not wf.is_config_valid


@pytest.mark.parametrize("jar", ["FutureWeatherGenerator_Europe_v2.0.2.jar", "FutureWeatherGenerator_Europe_v1.0.1.jar"])
def test_cordex_rejects_europe_jars_before_the_engine(temp_epw, tmp_path, caplog, jar):
    """
    Europe v1.x and v2.x do not run on the FWG Engine, so MorphingWorkflowCordex
    (which builds the FWG Engine command) rejects them. Europe v3+ is accepted.
    """
    with caplog.at_level(logging.ERROR, logger="pyfwg"):
        wf = configure(MorphingWorkflowCordex, temp_epw, str(tmp_path / "out"), fwg_jar_path=jar)
    assert not wf.is_config_valid
    assert "Use MorphingWorkflowEurope instead" in caplog.text

    wf = configure(MorphingWorkflowCordex, temp_epw, str(tmp_path / "out"), fwg_jar_path=EUROPE_V3_JAR)
    assert wf.is_config_valid


def test_cordex_uses_fwg_params(temp_epw, tmp_path):
    """The values of fwg_params apply to the parameters that are not passed explicitly."""
    wf = configure(MorphingWorkflowCordex, temp_epw, str(tmp_path / "out"), fwg_jar_path=NAM_JAR,
                   fwg_params={"month_transition_hours": 24, "create_ensemble": False, "diffuse_irradiation_model": 2})
    assert wf.is_config_valid
    cmd = wf._build_command_engine(temp_epw, "temp.epw", "out")
    assert "-smooth_hours=24" in cmd
    assert "-ensemble=false" in cmd
    # The legacy diffuse model is translated into the decomposition method
    assert "-decomposition_method=PAULESCU_BLAGA_2019" in cmd


# --- High-level API ---

@patch("pyfwg.api.MorphingWorkflowCordex")
@patch("pyfwg.api._robust_rmtree")
@patch("os.path.exists", return_value=True)
@patch("os.makedirs")
def test_morph_epw_cordex(mock_makedirs, mock_exists, mock_rmtree, mock_workflow_class, tmp_path):
    """Test the successful execution of morph_epw_cordex with the workflow mocked."""
    mock_workflow = mock_workflow_class.return_value
    mock_workflow.is_config_valid = True
    mock_workflow.epws_to_be_morphed = ["test.epw"]
    mock_workflow.inputs = {
        'temp_base_dir': str(tmp_path / 'temp'),
        'fwg_params': {'add_uhi': False},
        'fwg_jar_path': NAM_JAR,
        'delete_temp_files': True
    }
    mock_workflow._execute_single_morph.return_value = True

    with patch("os.listdir", return_value=["test_morphed.epw"]):
        with patch("shutil.move"):
            results = morph_epw_cordex(epw_paths="test.epw", fwg_jar_path=NAM_JAR, output_dir=str(tmp_path / "out"))

    assert len(results) == 1
    mock_workflow.configure_and_preview.assert_called_once()


def test_run_direct_morphing_engine(temp_epw, tmp_path):
    """
    The simple API moves the scenario files of the 'weather' subfolder (FWG
    Engine). The copy of the input EPW file and the baseline processed by the
    engine are not moved.
    """
    temp_base = tmp_path / "temp"
    workflow = MagicMock()
    workflow.is_config_valid = True
    workflow.epws_to_be_morphed = [temp_epw]
    workflow.rename_plan = {temp_epw: {"ssp245_2050.epw": str(tmp_path / "out" / "ssp245_2050.epw")}}
    workflow.inputs = {
        'temp_base_dir': str(temp_base),
        'fwg_params': {'add_uhi': False, 'output_type': 'EPW'},
        'fwg_jar_path': GLOBAL_V5_JAR,
        'delete_temp_files': False,
        'fwg_cli_style': 'engine'
    }

    def fake_execute(epw_path, temp_dir):
        # The tool receives a copy of the EPW file in the temporary folder
        with open(os.path.join(temp_dir, os.path.basename(epw_path)), "w") as f:
            f.write("copy")
        write_engine_outputs(temp_dir)
        return True

    workflow._execute_single_morph.side_effect = fake_execute
    results = _run_direct_morphing(workflow, str(tmp_path / "out"))

    assert sorted(os.path.basename(path) for path in results) == [
        "ESP_Andalucia_Sevilla_Ensemble_ssp245_2050.epw",
        "ESP_Andalucia_Sevilla_Ensemble_ssp245_2050.stat",
    ]


# --- Iterator and utilities ---

def test_iterator_cordex_ignores_uhi_defaults(caplog):
    """Arguments that a workflow does not accept (e.g., UHI for CORDEX) are ignored with a warning."""
    iterator = MorphingIterator(MorphingWorkflowCordex)
    with caplog.at_level(logging.WARNING, logger="pyfwg"):
        iterator.set_default_values(fwg_jar_path=NAM_JAR, fwg_add_uhi=True, fwg_scenarios=["rcp85"])
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "fwg_add_uhi" in warnings[0].getMessage()
    assert "fwg_add_uhi" not in iterator.custom_defaults
    assert iterator.custom_defaults["fwg_scenarios"] == ["rcp85"]
    # The template only contains the arguments of the CORDEX workflow
    columns = iterator.get_template_dataframe().columns
    assert "fwg_rcm_pairs" in columns and "fwg_add_uhi" not in columns


def test_iterator_engine_runs(temp_epw, tmp_path):
    """The iterator prepares FWG Engine workflows with the new arguments."""
    iterator = MorphingIterator(MorphingWorkflowGlobal)
    iterator.set_default_values(fwg_jar_path=GLOBAL_V5_JAR, output_filename_pattern="{city}_{ssp}_{year}_{fwg_uncertainty_variant}",
                                final_output_dir=str(tmp_path / "out"))
    runs_df = pd.DataFrame({
        "epw_paths": [temp_epw, temp_epw],
        "fwg_uncertainty_variant": ["CENTRAL", "WARM_DRY"],
        "fwg_scenarios": [["ssp585"], ["ssp585"]],
    })
    iterator.generate_morphing_workflows(runs_df, keyword_mapping={"city": {"Seville": "sevilla"}})

    assert len(iterator.prepared_workflows) == 2
    assert all(wf.is_config_valid for wf in iterator.prepared_workflows)
    assert list(iterator.prepared_workflows[1].rename_plan[temp_epw]) == ["ssp585_2050.epw", "ssp585_2080.epw"]


def test_load_runs_from_excel_engine_columns(tmp_path):
    """The new list and dictionary columns are converted back into Python objects."""
    file_path = tmp_path / "runs.xlsx"
    pd.DataFrame({
        "epw_paths": ["test.epw"],
        "fwg_scenarios": ["['ssp245', 'ssp585']"],
        "fwg_extra_args": ["{'threads': 4}"],
    }).to_excel(file_path, index=False)

    loaded_df = load_runs_from_excel(str(file_path))
    assert loaded_df["fwg_scenarios"].iloc[0] == ["ssp245", "ssp585"]
    assert loaded_df["fwg_extra_args"].iloc[0] == {"threads": 4}


def test_get_fwg_parameters_info_engine():
    """The parameter documentation includes the FWG Engine options."""
    info = get_fwg_parameters_info()
    for key in ("fwg_scenarios", "fwg_timeframes", "fwg_decomposition_method", "fwg_uncertainty_variant"):
        assert info[key]["requires"] == "FWG Engine"
    assert info["fwg_interpolation_method_id"]["allowed_values"][6] == "STBI"
