
import os
import pytest

@pytest.fixture
def fwg_jars():
    return {
        "EUROPE_V1": r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v1.0.1.jar",
        "EUROPE_V2": r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v2.0.2.jar",
        "GLOBAL_V3": r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
        "GLOBAL_V4": r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar"
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
