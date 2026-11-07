import os
import json
import zipfile
import pytest


def pytest_addoption(parser):
    group = parser.getgroup("FWG integration")
    group.addoption("--fwg-jar-dir", default=os.environ.get("FWG_JAR_DIR"),
                    help="Folder with downloaded FWG JARs; absent regions are skipped.")
    group.addoption("--fwg-epw-dir", default=os.environ.get("FWG_EPW_DIR"),
                    help="Enable morphing tests with regional baselines named <domain>.epw (e.g. NAM-44.epw).")
    group.addoption("--fwg-java", default=os.environ.get("FWG_JAVA", "java"),
                    help="Java executable used by integration tests (Java 17+).")
    group.addoption("--fwg-cache-dir", default=os.environ.get("FWG_CACHE_DIR"),
                    help="Optional shared climate-data cache, separated by CORDEX domain.")
    group.addoption("--fwg-ensemble-size", type=int, default=None,
                    help="Limit generation-test ensembles to the first N catalog members (N >= 2).")
    group.addoption("--fwg-extra-jar-dir", action="append", default=[],
                    help="Additional JAR folder for the cross-interface integration suite; repeatable.")

@pytest.fixture
def fwg_jars():
    """
    Paths to the JAR files of the Future Weather Generator, in the folder given by the
    FWG_JAR_DIR environment variable (as in the tutorial notebooks). When it is not set,
    only the filenames are returned.
    """
    jar_dir = os.environ.get("FWG_JAR_DIR", "")
    filenames = {
        "EUROPE_V1": "FutureWeatherGenerator_Europe_v1.0.1.jar",
        "EUROPE_V2": "FutureWeatherGenerator_Europe_v2.0.2.jar",
        "GLOBAL_V3": "FutureWeatherGenerator_v3.0.1.jar",
        "GLOBAL_V4": "FutureWeatherGenerator_v4.0.2.jar",
        # FWG Engine distributions
        "GLOBAL_V5": "FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar",
        "EUROPE_V3": "FutureWeatherGenerator-CORDEX-CMIP5-Europe-EUR-11-v3.2.0.jar",
        "CORDEX_NAM": "FutureWeatherGenerator-CORDEX-CMIP5-North-America-NAM-44-v1.2.0.jar",
    }
    return {key: os.path.join(jar_dir, filename) for key, filename in filenames.items()}

@pytest.fixture
def real_epws():
    # EPW files versioned in the epws folder at the root of the repository
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "epws", "w_pattern")
    files = [
        os.path.join(base_dir, "london_uhi-type-2.epw"),
        os.path.join(base_dir, "sevilla_uhi-type-1.epw")
    ]
    # Filter only those that exist
    return [f for f in files if os.path.exists(f)]

@pytest.fixture
def make_engine_jar(tmp_path):
    """
    Factory fixture that builds a synthetic FWG Engine JAR.
    It only contains the metadata that pyfwg reads (distribution manifest,
    climate-model catalog, model manifests and engine version), laid out as in
    the real distributions (Global v5+, Europe v3+, CORDEX regional).
    """
    def _make(filename, *, version="5.2.0", framework="CMIP", domain=None, scenarios=None,
              models=None, timeframes=("2050", "2080"), engine_version="1.1.0"):
        scenarios = scenarios or ["ssp126", "ssp245", "ssp370", "ssp585"]
        # models: {model_id: {"scenarios": [...], "ensembleEligible": bool}}
        models = models if models is not None else {"CanESM5": {}, "MIROC6": {}}
        manifest = {
            "schemaVersion": "3.0",
            "distribution": {"id": "fwg-test", "name": "FWG Test Distribution", "version": version,
                             "scenarioFamily": "SSP" if framework == "CMIP" else "RCP"},
            "climateSource": {"framework": framework, "cmipGeneration": "CMIP6" if framework == "CMIP" else "CMIP5",
                              "downscalingFramework": "NONE" if framework == "CMIP" else "CORDEX"},
            "scenarios": [{"id": s, "order": 10 * (i + 1)} for i, s in enumerate(scenarios)],
            "timeframes": [{"id": t, "order": 10 * (i + 1)} for i, t in enumerate(timeframes)],
            "domain": {"type": "global" if domain is None else "regional", "region": "Test",
                       "gridDomain": domain or ""},
        }
        catalog = {"schemaVersion": "1.4", "models": []}
        jar_path = tmp_path / filename
        with zipfile.ZipFile(jar_path, "w") as jar:
            jar.writestr("futureweathergenerator/version.properties",
                         f"version={engine_version}\nversion.tag=v{engine_version}\n")
            jar.writestr("futureweathergenerator/resources/distribution-manifest.json", json.dumps(manifest))
            for model_id, details in models.items():
                catalog["models"].append({"id": model_id, "directory": model_id,
                                          "manifest": f"{model_id}/model-manifest.json"})
                model_manifest = {
                    "modelId": model_id,
                    "ensembleEligible": details.get("ensembleEligible", True),
                    "scenarios": details.get("scenarios", scenarios),
                    "futurePeriods": [{"timeframe": t} for t in details.get("timeframes", timeframes)],
                    "grid": {"coordinateReference": {"topology": details.get(
                        "topology", "RECTILINEAR_GEOGRAPHIC" if domain is None else "CURVILINEAR_ROTATED")}},
                }
                jar.writestr(f"futureweathergenerator/resources/{model_id}/model-manifest.json",
                             json.dumps(model_manifest))
            jar.writestr("futureweathergenerator/resources/climate-model-catalog.json", json.dumps(catalog))
        return str(jar_path)
    return _make
