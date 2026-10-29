"""Contracts for every published CORDEX-CMIP5 domain, without Java or climate data.

The scenario sets and representative products below were checked against the
FWG distribution documentation and the available v1.2.0 JAR catalogs.
"""

import pytest

from pyfwg import MorphingWorkflowCordex, MorphingWorkflowEurope, MorphingWorkflowGlobal
from pyfwg.api import morph_epw_cordex
from pyfwg.utils import detect_fwg_tool, get_fwg_distribution_info


REGIONS = [
    ("EUR-11", "Europe", ["rcp26", "rcp45", "rcp85"], "ICHEC-EC-EARTH-SMHI-RCA4"),
    ("MNA-22", "Middle-East-and-North-Africa", ["rcp85"], "ICHEC-EC-EARTH-SMHI-RCA4"),
    ("AFR-22", "Africa", ["rcp26", "rcp85"], "MOHC-HadGEM2-ES-CLMcom-KIT-CCLM5-0-15"),
    ("NAM-44", "North-America", ["rcp45", "rcp85"], "CCCma-CanESM2-SMHI-RCA4"),
    ("CAM-44", "Central-America", ["rcp26", "rcp45", "rcp85"], "ICHEC-EC-EARTH-SMHI-RCA4"),
    ("SAM-44", "South-America", ["rcp26", "rcp45", "rcp85"], "MIROC-MIROC5-SMHI-RCA4"),
    ("WAS-22", "West-South-Asia", ["rcp26", "rcp85"], "MPI-M-MPI-ESM-LR-CLMcom-ETH-COSMO-crCLIM-v1-1"),
    ("SEA-22", "Southeast-Asia", ["rcp45", "rcp85"], "CNRM-CERFACS-CNRM-CM5-SMHI-RCA4"),
    ("AUS-22", "Australasia", ["rcp26", "rcp85"], "NCC-NorESM1-M-CLMcom-HZG-CCLM5-0-15"),
]


def configure(tmp_path, jar, workflow_class=MorphingWorkflowCordex, **kwargs):
    epw = tmp_path / "station.epw"
    epw.write_text("Configuration test only; not a weather baseline.")
    wf = workflow_class()
    wf.map_categories([str(epw)], keyword_mapping={"city": {"Station": "station"}})
    wf.configure_and_preview(
        fwg_jar_path=str(jar), final_output_dir=str(tmp_path / "out"),
        temp_base_dir=str(tmp_path / "temp"),
        output_filename_pattern=f"{{city}}_{{{wf.scenario_placeholder_name}}}_{{year}}",
        **kwargs,
    )
    return wf, str(epw)


@pytest.mark.parametrize("domain,region,scenarios,model", REGIONS, ids=[r[0] for r in REGIONS])
@pytest.mark.parametrize("manifest", [False, True], ids=["filename", "manifest"])
def test_every_cordex_region(tmp_path, make_engine_jar, domain, region, scenarios, model, manifest):
    version = "3.2.0" if domain == "EUR-11" else "1.2.0"
    # The renamed JAR exercises manifest discovery independently of filename hints.
    jar = (make_engine_jar("renamed.jar", version=version, framework="CORDEX", domain=domain,
                           scenarios=scenarios, models={model: {}}) if manifest else
           tmp_path / f"FutureWeatherGenerator-CORDEX-CMIP5-{region}-{domain}-v{version}.jar")
    assert detect_fwg_tool(jar) == ("europe" if domain == "EUR-11" else "cordex")
    wf, epw = configure(tmp_path, jar, fwg_rcm_pairs=[model.replace("-", "_")])
    assert wf.is_config_valid
    assert wf.cordex_domain == domain
    assert wf.tool_scenarios == scenarios
    assert set(wf.rename_plan[epw]) == {f"{scenario}_{year}.epw" for scenario in scenarios for year in (2050, 2080)}
    command = wf._build_command_engine(epw, epw, str(tmp_path / "temp"))
    assert command[3] == "-g"
    assert f"-models={model}" in command
    assert "-ensemble=false" in command
    assert "-output_layout=ORGANIZED" in command

    # Regional RCP filenames must collect the same EPW/STAT pairs as Global SSPs.
    weather = tmp_path / "temp" / "weather"
    weather.mkdir(parents=True)
    (tmp_path / "out").mkdir()
    for scenario in scenarios:
        for year in (2050, 2080):
            for suffix in (".epw", ".stat"):
                (weather / f"Station_{model}_{scenario}_{year}{suffix}").write_text("generated")
    control = weather / "Station_SolarQC_corrected.epw"
    control.write_text("control")
    wf._process_generated_files(epw, str(tmp_path / "temp"))
    assert {p.name for p in (tmp_path / "out").iterdir()} == {
        f"Station_{scenario}_{year}{suffix}"
        for scenario in scenarios for year in (2050, 2080) for suffix in (".epw", ".stat")}
    assert control.exists()

    invalid, _ = configure(tmp_path, jar, fwg_rcm_pairs=["CanESM5"], fwg_scenarios=["ssp585"])
    assert not invalid.is_config_valid
    bilinear, _ = configure(tmp_path, jar, fwg_interpolation_method_id="BI")
    assert not bilinear.is_config_valid


@pytest.mark.parametrize("topology", ["CURVILINEAR_ROTATED", "CURVILINEAR_PROJECTED",
                                    "CURVILINEAR_AUXILIARY", "RECTILINEAR_PROJECTED"])
@pytest.mark.parametrize("method", [1, "bi", "SGBI", "STBI", "SCI", "NP", "IDW", "AVG4P"])
def test_interpolation_uses_selected_model_topology(tmp_path, make_engine_jar, topology, method):
    jar = make_engine_jar("regional.jar", framework="CORDEX", domain="NAM-44", scenarios=["rcp85"],
                          models={"Regional-Product": {"topology": topology}})
    assert get_fwg_distribution_info(jar)["model_details"]["Regional-Product"]["grid_topology"] == topology
    wf, _ = configure(tmp_path, jar, fwg_interpolation_method_id=method)
    assert wf.is_config_valid == (method not in (1, "bi"))


def test_bilinear_checks_only_selected_models(tmp_path, make_engine_jar):
    jar = make_engine_jar("mixed.jar", models={
        "Rectilinear": {"topology": "RECTILINEAR_GEOGRAPHIC"},
        "Curvilinear": {"topology": "CURVILINEAR_AUXILIARY", "ensembleEligible": False},
    })
    default, _ = configure(tmp_path, jar, MorphingWorkflowGlobal, fwg_interpolation_method_id=1)
    assert default.is_config_valid  # Non-default products must not block the default selection.
    assert default.inputs["fwg_params"]["create_ensemble"] is False
    selected, _ = configure(tmp_path, jar, MorphingWorkflowGlobal,
                            fwg_gcms=["Curvilinear"], fwg_interpolation_method_id=1)
    assert not selected.is_config_valid


@pytest.mark.parametrize("workflow_class", [MorphingWorkflowCordex, MorphingWorkflowEurope])
def test_europe_engine_uses_grid_metadata(tmp_path, make_engine_jar, workflow_class):
    jar = make_engine_jar("europe.jar", version="3.2.0", framework="CORDEX", domain="EUR-11",
                          scenarios=["rcp85"], models={"Regional-Product": {}})
    wf, _ = configure(tmp_path, jar, workflow_class, fwg_interpolation_method_id=1)
    assert not wf.is_config_valid


def test_duplicate_aliases_are_one_ensemble_member(tmp_path, make_engine_jar):
    jar = make_engine_jar("regional.jar", framework="CORDEX", domain="NAM-44",
                          scenarios=["rcp85"], models={"CCCma-CanESM2-SMHI-RCA4": {}})
    wf, epw = configure(tmp_path, jar, fwg_rcm_pairs=["CCCma-CanESM2-SMHI-RCA4", "CCCma_CanESM2_SMHI_RCA4"])
    assert wf.is_config_valid
    command = wf._build_command_engine(epw, epw, str(tmp_path / "temp"))
    assert "-ensemble=false" in command
    assert "-models=CCCma-CanESM2-SMHI-RCA4" in command


@pytest.mark.parametrize("models", [[], "", ","])
def test_empty_model_selection_is_invalid(tmp_path, make_engine_jar, models):
    jar = make_engine_jar("regional.jar", framework="CORDEX", domain="NAM-44", scenarios=["rcp85"])
    wf, _ = configure(tmp_path, jar, fwg_rcm_pairs=models)
    assert not wf.is_config_valid


def test_catalog_without_default_models_requires_selection(tmp_path, make_engine_jar):
    jar = make_engine_jar("regional.jar", framework="CORDEX", domain="NAM-44", scenarios=["rcp85"],
                          models={"Regional-Product": {"ensembleEligible": False}})
    default, _ = configure(tmp_path, jar)
    assert not default.is_config_valid
    selected, _ = configure(tmp_path, jar, fwg_rcm_pairs=["Regional-Product"])
    assert selected.is_config_valid


def test_simple_api_blocks_incompatible_regional_interpolation(tmp_path, make_engine_jar, monkeypatch):
    jar = make_engine_jar("regional.jar", framework="CORDEX", domain="NAM-44", scenarios=["rcp85"])
    epw = tmp_path / "station.epw"
    epw.write_text("Not needed: validation must stop before Java.")
    def unexpected_execution(*args, **kwargs):
        pytest.fail("Java must not run with an invalid configuration")
    monkeypatch.setattr("subprocess.run", unexpected_execution)
    with pytest.raises(ValueError, match="parameter validation failed"):
        morph_epw_cordex(epw_paths=str(epw), fwg_jar_path=jar, output_dir=str(tmp_path / "out"),
                         temp_base_dir=str(tmp_path / "temp"), fwg_interpolation_method_id="BI")


def test_iterator_keeps_each_regions_catalog(tmp_path, make_engine_jar):
    import pandas as pd
    from pyfwg import MorphingIterator

    runs = []
    for domain, _, scenarios, model in REGIONS:
        jar = make_engine_jar(f"{domain}.jar", version="3.2.0" if domain == "EUR-11" else "1.2.0",
                              framework="CORDEX", domain=domain, scenarios=scenarios, models={model: {}})
        epw = tmp_path / f"{domain}_station.epw"
        epw.write_text("Configuration only.")
        runs.append({"epw_paths": str(epw), "fwg_jar_path": jar, "fwg_rcm_pairs": [model],
                     "fwg_scenarios": [scenarios[0]], "fwg_timeframes": [2050]})
    iterator = MorphingIterator(MorphingWorkflowCordex)
    iterator.set_default_values(final_output_dir=str(tmp_path / "out"), temp_base_dir=str(tmp_path / "temp"),
                                output_filename_pattern="{region}_{rcp}_{year}")
    iterator.generate_morphing_workflows(pd.DataFrame(runs),
                                        keyword_mapping={"region": {r[0]: r[0] for r in REGIONS}})
    assert len(iterator.prepared_workflows) == len(REGIONS)
    for wf, (domain, _, scenarios, model) in zip(iterator.prepared_workflows, REGIONS):
        assert wf.is_config_valid
        assert wf.cordex_domain == domain
        assert wf.tool_scenarios == scenarios
        assert wf.inputs["fwg_requested_models"] == [model]
