"""Optional checks against actual downloaded CORDEX-CMIP5 distributions.

No JARs or EPWs are downloaded. Metadata checks do not need Java. CLI help
checks need Java but do not extract climate archives. Morphing is enabled
only when the user supplies a real baseline inside each regional domain.
"""

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from pyfwg import MorphingWorkflowCordex, get_fwg_distribution_info, morph_epw_cordex
from pyfwg.constants import CORDEX_REGIONS
from pyfwg.utils import _detect_cordex_domain


pytestmark = pytest.mark.integration
DOMAINS = ("EUR-11", "MNA-22", "AFR-22", "NAM-44", "CAM-44", "SAM-44", "WAS-22", "SEA-22", "AUS-22")


def pytest_generate_tests(metafunc):
    if "cordex_jar" not in metafunc.fixturenames:
        return
    jar_dir = metafunc.config.getoption("--fwg-jar-dir")
    by_domain = {domain: [] for domain in DOMAINS}
    if jar_dir:
        directory = Path(jar_dir).expanduser().resolve()
        if not directory.is_dir():
            raise pytest.UsageError(f"FWG JAR directory does not exist: {directory}")
        for jar in sorted(directory.glob("*.jar")):
            domain = _detect_cordex_domain(str(jar))
            if domain in by_domain:
                by_domain[domain].append(jar)
    cases = []
    for domain, jars in by_domain.items():
        if jars:
            # Keep every downloaded version; do not silently pick only one JAR per region.
            cases.extend(pytest.param((domain, jar), id=f"{domain}/{jar.stem}") for jar in jars)
        else:
            reason = (f"No {domain} JAR found in {jar_dir}" if jar_dir else
                      "Set FWG_JAR_DIR or --fwg-jar-dir to check downloaded distributions")
            cases.append(pytest.param((domain, None), id=domain, marks=pytest.mark.skip(reason=reason)))
    metafunc.parametrize("cordex_jar", cases)


@pytest.fixture
def java_executable(request):
    executable = shutil.which(request.config.getoption("--fwg-java"))
    if not executable:
        pytest.skip("Java unavailable; set --fwg-java or FWG_JAVA to a Java 17+ executable")
    return executable


def prepare(tmp_path, jar, epw, *, ensemble=True, cache_dir=None, ensemble_size=None):
    info = get_fwg_distribution_info(str(jar))
    assert info is not None, f"Cannot read FWG metadata from {jar}; verify that the download is complete"
    wf = MorphingWorkflowCordex()
    wf.map_categories([str(epw)], keyword_mapping={"station": {"Station": epw.stem}})
    models = info["ensemble_models"] if ensemble else info["models"][:1]
    if ensemble and ensemble_size is not None:
        if ensemble_size < 2:
            raise pytest.UsageError("--fwg-ensemble-size must be at least 2")
        models = models[:ensemble_size]
    assert models, f"No usable climate models in {jar}"
    scenario = next(s for s in info["scenarios"] if all(
        s in info["model_details"][model]["scenarios"] for model in models))
    wf.configure_and_preview(
        fwg_jar_path=str(jar), final_output_dir=str(tmp_path / "out"),
        output_filename_pattern="{station}_{rcp}_{year}", temp_base_dir=str(tmp_path / "temp"),
        fwg_rcm_pairs=models, fwg_create_ensemble=ensemble,
        fwg_scenarios=[scenario], fwg_timeframes=[info["timeframes"][0]],
        fwg_output_profile="MINIMAL", fwg_extra_args={"threads": 1, "io_threads": 1, "save_technical_log": True},
        fwg_model_unzipped_folder=cache_dir,
        delete_temp_files=False,
    )
    assert wf.is_config_valid
    return wf, info


def test_regional_jar_catalog_and_configuration(cordex_jar, tmp_path):
    domain, jar = cordex_jar
    epw = tmp_path / "station.epw"
    epw.write_text("Metadata and command construction only; not a real baseline.")
    wf, info = prepare(tmp_path, jar, epw)
    assert info["framework"] == "CORDEX"
    assert info["cmip_generation"] == "CMIP5"
    assert info["domain"] == wf.cordex_domain == domain
    assert info["scenarios"] == CORDEX_REGIONS[domain]["scenarios"]
    assert set(info["models"]) == {model.replace("_", "-") for model in CORDEX_REGIONS[domain]["rcm_pairs"]}
    assert info["timeframes"] == ["2050", "2080"]
    for details in info["model_details"].values():
        assert details["components"]["domain"] == domain
        assert details["grid_topology"] in {
            "CURVILINEAR_ROTATED", "CURVILINEAR_PROJECTED", "CURVILINEAR_AUXILIARY", "RECTILINEAR_PROJECTED"}
    command = wf._build_command_engine(str(epw), str(epw), str(tmp_path / "temp"))
    assert command[:4] == ["java", "-jar", str(jar), "-g"]
    assert "-models=" + ",".join(info["ensemble_models"]) in command
    assert "-ensemble=true" in command
    assert len(wf.rename_plan[str(epw)]) == 1


@pytest.mark.java
def test_regional_jar_cli_help(cordex_jar, java_executable, tmp_path):
    domain, jar = cordex_jar
    result = subprocess.run([java_executable, "-jar", str(jar), "-h"], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert domain in output
    for token in ("-models=", "-scenarios=", "-timeframes=", "-grid_interpolation_method=", "-output_layout="):
        assert token in output, output
    info = get_fwg_distribution_info(str(jar))
    for value in info["scenarios"] + info["timeframes"]:
        assert value in output, output


@pytest.mark.java
@pytest.mark.morphing
@pytest.mark.parametrize("ensemble", [True, False], ids=["ensemble-workflow", "single-model-api"])
def test_regional_jar_morphing(cordex_jar, java_executable, tmp_path, request, monkeypatch, ensemble):
    domain, jar = cordex_jar
    epw_dir = request.config.getoption("--fwg-epw-dir")
    if not epw_dir:
        pytest.skip("Supply --fwg-epw-dir with real regional EPWs to enable weather generation")
    epw = Path(epw_dir).expanduser().resolve() / f"{domain}.epw"
    if not epw.is_file():
        pytest.skip(f"Supply an EPW inside the {domain} domain at {epw}")
    # The public API invokes 'java'; use the explicitly selected JDK for this test only.
    monkeypatch.setenv("PATH", str(Path(java_executable).parent) + os.pathsep + os.environ.get("PATH", ""))
    cache_root = request.config.getoption("--fwg-cache-dir")
    cache_dir = str(Path(cache_root).expanduser().resolve() / domain) if cache_root else None
    wf, info = prepare(tmp_path, jar, epw, ensemble=ensemble, cache_dir=cache_dir,
                       ensemble_size=request.config.getoption("--fwg-ensemble-size"))
    if ensemble:
        wf.execute_morphing()
        generated = list((tmp_path / "out").glob("*"))
    else:
        params = wf.inputs["fwg_params"]
        generated = [Path(path) for path in morph_epw_cordex(
            epw_paths=str(epw), fwg_jar_path=str(jar), output_dir=str(tmp_path / "out"),
            temp_base_dir=str(tmp_path / "api-temp"), delete_temp_files=False,
            fwg_rcm_pairs=info["models"][:1], fwg_scenarios=params["scenarios"],
            fwg_timeframes=params["timeframes"], fwg_output_profile="MINIMAL",
            fwg_model_unzipped_folder=cache_dir,
            fwg_extra_args={"threads": 1, "io_threads": 1, "save_technical_log": True},
        )]
    assert sorted(path.suffix for path in generated) == [".epw", ".stat"], (
        f"Expected one future EPW/STAT pair; inspect the logs and temporary files in {tmp_path}")
    weather = next(path for path in generated if path.suffix == ".epw")
    lines = weather.read_bytes().splitlines()
    baseline_lines = epw.read_bytes().splitlines()
    assert lines[0].startswith(b"LOCATION,")
    assert len(lines) == len(baseline_lines) and len(lines) >= 8768
    assert all(path.stat().st_size > 0 for path in generated)
