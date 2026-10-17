import os
import json
import zipfile
import pytest

@pytest.fixture
def fwg_jars():
    return {
        "EUROPE_V1": r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v1.0.1.jar",
        "EUROPE_V2": r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v2.0.2.jar",
        "GLOBAL_V3": r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
        "GLOBAL_V4": r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar",
        # FWG Engine distributions
        "GLOBAL_V5": r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar",
        "EUROPE_V3": r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator-CORDEX-CMIP5-Europe-EUR-11-v3.2.0.jar",
        "CORDEX_NAM": r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator-CORDEX-CMIP5-North-America-NAM-44-v1.2.0.jar",
    }

@pytest.fixture
def real_epws():
    base_dir = r"D:\Python\pyfwg\epws\w_pattern"
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
            "climateSource": {"framework": framework, "cmipGeneration": "CMIP6",
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
                }
                jar.writestr(f"futureweathergenerator/resources/{model_id}/model-manifest.json",
                             json.dumps(model_manifest))
            jar.writestr("futureweathergenerator/resources/climate-model-catalog.json", json.dumps(catalog))
        return str(jar_path)
    return _make
