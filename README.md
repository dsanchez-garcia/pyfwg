# pyfwg: Python Future Weather Generator

[![PyPI version](https://badge.fury.io/py/pyfwg.svg)](https://badge.fury.io/py/pyfwg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation Status](https://img.shields.io/readthedocs/pyfwg/latest)](https://pyfwg.readthedocs.io/en/latest/?badge=latest)
[![DOI](https://zenodo.org/badge/1039407242.svg)](https://doi.org/10.5281/zenodo.16908690)

A robust, step-by-step Python workflow manager for the [Future Weather Generator](https://future-weather-generator.adai.pt/) command-line tool.

`pyfwg` provides a safe and intuitive way to automate the morphing of EnergyPlus Weather (EPW) files for future climate scenarios. It supports the **Global**, **Europe-specific** and **CORDEX regional** versions of the Future Weather Generator tool.

## Key Features

- **Multiple Interfaces**: Use simple one-shot functions for direct tasks, advanced workflow classes for custom renaming, or a powerful iterator for large-scale parametric studies.
- **Step-by-Step Control**: The advanced workflow allows you to map, configure, preview, and then execute, preventing errors before they happen.
- **Flexible Filename Mapping**: Handle both structured (regex-based) and unstructured (keyword-based) filenames with ease.
- **Built-in Validation**: Automatically validates all Future Weather Generator parameters before execution, catching typos and invalid values (e.g., unavailable models or scenarios).
- **Excel Integration**: Export templates and load run configurations directly from Excel files for easy parametric analysis.
- **Clear and Organized Output**: Automatically renames and organizes the final `.epw` and `.stat` files into a clean directory structure.

## What's New in Version 0.4.0?

Version 0.4.0 adds support for the **FWG Engine**, the shared engine of the latest Future Weather Generator distributions: **Global v5.x**, **Europe v3.x** and the new **CORDEX regional** distributions. Supported binaries are Global 5.2.0, Europe EUR-11 3.2.0 and the other eight regional distributions 1.2.0. Older Global/Europe releases are outside the supported scope.

-   **Global v5.x and Europe v3.x**: Use them with the same classes and functions as before (`MorphingWorkflowGlobal`, `morph_epw_global`, etc.). `pyfwg` detects the version from the JAR and builds the new command line for you.
-   **CORDEX regional distributions**: `MorphingWorkflowCordex` and `morph_epw_cordex` accept all nine CORDEX-CMIP5 domains, including Europe EUR-11 v3+. The region is detected from the JAR, and its scenarios and GCM-RCM pairs are validated against the installed catalog.
-   **New FWG Engine options**: Select scenarios and future periods (`fwg_scenarios`, `fwg_timeframes`), solar decomposition, illuminance and infrared models, uncertainty cases (`fwg_uncertainty_variant`), output profile and a shared climate-data cache (`fwg_model_unzipped_folder`). Any other option of the tool can be passed with `fwg_extra_args`.
-   **JAR inspection**: `get_fwg_distribution_info` reads the scenarios, periods and climate models packaged in FWG Engine JARs, which `pyfwg` also uses to validate your configuration.
-   **Urban Heat Island**: The supported FWG Engine distributions do not implement the UHI effect or LCZ morphing.

## Requirements

Before using `pyfwg`, you need to have the following installed and configured:

*   **Python 3.9+**
*   **Java**: The `java` command must be accessible from your system's terminal (i.e., it must be in your system's PATH).
*   **Future Weather Generator**: You must download the appropriate `.jar` file from the [official website](https://future-weather-generator.adai.pt/).
    *   The **FWG Engine distributions** have been tested with **Global v5.2.0** and all nine **CORDEX-CMIP5** regions: **Europe EUR-11 v3.2.0** and the other eight regional distributions **v1.2.0** (FWG Engine v1.1.0). Regional generation checks on 2026-10-28 covered one real EPW per domain, one scenario and the 2050 period, with both a single model and the full eligible ensemble. See the [CORDEX guide](docs/source/cordex.rst) for the reproducible checks and their scope.

## Installation

You can install `pyfwg` directly from PyPI:

```bash
pip install pyfwg
```

### Showing the Log Messages

`pyfwg` reports its progress, warnings and validation errors with Python's standard `logging` module (the `pyfwg` logger), and it does not change the logging configuration of your application. If your script or notebook does not configure logging, call `enable_console_logging()` to show these messages on the console (colored if `colorlog` is installed):

```python
import pyfwg

pyfwg.enable_console_logging()  # Or, e.g., level='WARNING' to show only warnings and errors
```

## Quick Start: Simple Morphing

Store the JARs in any folder, including an external drive, and pass their full paths. Paths with spaces are supported. Keep the drive connected during generation. The climate-data cache and output folders can be on separate drives.

```python
import os
from pathlib import Path
from pyfwg import morph_epw_global

jar_dir = Path(os.environ.get("FWG_JAR_DIR", "path/to/jars"))
created_files = morph_epw_global(
    epw_paths="epws/sevilla.epw",
    fwg_jar_path=str(jar_dir / "FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar"),
    output_dir="./global-results",
    fwg_gcms=["CanESM5"],
    fwg_create_ensemble=False,
    fwg_add_uhi=False,
    fwg_scenarios=["ssp245"],
    fwg_timeframes=[2050],
    fwg_output_profile="MINIMAL",
    fwg_model_unzipped_folder="./fwg-cache/global/5.2.0",
)
print(created_files)
```

Read `get_fwg_distribution_info(jar_path)` to discover the models, scenarios and periods packaged in a JAR. A multi-model ensemble needs at least two distinct eligible models. The supported Engine distributions do not implement UHI. `get_fwg_parameters_info()` describes the available parameters.

## Advanced Usage: Workflow Classes

Use `MorphingWorkflowGlobal` to preview custom names before generation. Map categories from filenames, configure the run, then execute:

```python
from pyfwg import MorphingWorkflowGlobal

workflow = MorphingWorkflowGlobal()
workflow.map_categories(
    epw_files=["epws/sevilla.epw"],
    keyword_mapping={"city": {"Seville": "sevilla"}},
)
workflow.configure_and_preview(
    fwg_jar_path=str(jar_dir / "FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar"),
    final_output_dir="./global-workflow",
    output_filename_pattern="{city}_{ssp}_{year}",
    fwg_gcms=["CanESM5"], fwg_create_ensemble=False, fwg_add_uhi=False,
    fwg_scenarios=["ssp245"], fwg_timeframes=[2050],
    fwg_model_unzipped_folder="./fwg-cache/global/5.2.0",
)
if workflow.is_config_valid:
    workflow.execute_morphing()
```

For Europe EUR-11 3.2.0, use `MorphingWorkflowEurope` / `morph_epw_europe`, or the Cordex interfaces below. Select models with `fwg_rcm_pairs` and name scenarios with `{rcp}`. Read the installed catalog rather than assuming a fallback model list is present in every distribution.

## Parametric Runs and Excel

`MorphingIterator` accepts one workflow class and a DataFrame with one row per run. Row values override iterator defaults. Choose `MorphingWorkflowGlobal` for Global, `MorphingWorkflowEurope` for Europe, or `MorphingWorkflowCordex` for any of the nine regions. A Cordex batch may use a different regional JAR in every row.

```python
from pyfwg import (
    MorphingIterator, MorphingWorkflowCordex,
    export_template_to_excel, load_runs_from_excel,
)

iterator = MorphingIterator(MorphingWorkflowCordex)
iterator.set_default_values(output_filename_pattern="{region}_{rcp}_{year}")
export_template_to_excel(iterator, "new-regional-study.xlsx")
# Fill the workbook and save it before executing the next lines.
runs = load_runs_from_excel("new-regional-study.xlsx")
iterator.generate_morphing_workflows(runs)
# Inspect the plan before starting generation.
iterator.run_morphing_workflows()
```

Export to a new filename to avoid replacing a workbook you edited. Use Python list/dictionary notation in structured cells, and load with `load_runs_from_excel` so those values are converted correctly. The [interface and Excel guide](docs/source/compatibility.rst) explains cell formats, precedence and the tested combinations. The notebooks include populated DataFrame and XLSX examples.

## Using the CORDEX Regional Tools

All nine CORDEX-CMIP5 domains, including Europe `EUR-11` v3+, are supported by `MorphingWorkflowCordex`, `morph_epw_cordex` and `MorphingIterator(MorphingWorkflowCordex)`. They use `fwg_rcm_pairs` and the `{rcp}` filename placeholder.

*   **Region detection**: The region is detected from the JAR, and only its scenarios and GCM-RCM pairs are accepted. They are listed in `pyfwg.CORDEX_REGIONS` (e.g., the Middle East and North Africa distribution only provides `rcp85`).
*   **No UHI**: These distributions do not support the Urban Heat Island effect.
*   **Regional grids**: `BI` (`fwg_interpolation_method_id=1`) requires a rectilinear geographic grid and is rejected for the rotated/projected grids in these distributions. Use `IDW` (the default), `NP`, `AVG4P`, `SCI`, `SGBI` or `STBI`. The EPW location must lie inside the selected region's model grids; Java checks the actual spatial coverage.

| Region | Domain | RCP scenarios |
| --- | --- | --- |
| Europe | EUR-11 | 2.6, 4.5, 8.5 |
| Middle East and North Africa | MNA-22 | 8.5 |
| Africa | AFR-22 | 2.6, 8.5 |
| North America | NAM-44 | 4.5, 8.5 |
| Central America | CAM-44 | 2.6, 4.5, 8.5 |
| South America | SAM-44 | 2.6, 4.5, 8.5 |
| West & South Asia | WAS-22 | 2.6, 8.5 |
| Southeast Asia | SEA-22 | 4.5, 8.5 |
| Australasia | AUS-22 | 2.6, 8.5 |

The installed JAR's catalog takes precedence over these fallback lists. Inspect it before selecting products:

```python
from pyfwg import morph_epw_cordex, get_fwg_distribution_info

jar_path_nam = r"D:\path\to\your\FutureWeatherGenerator-CORDEX-CMIP5-North-America-NAM-44-v1.2.0.jar"

info = get_fwg_distribution_info(jar_path_nam)
print(info['domain'], info['scenarios'], info['models'])

created_files = morph_epw_cordex(
    epw_paths='epws/toronto.epw',
    fwg_jar_path=jar_path_nam,
    output_dir='results/NAM-44',
    fwg_rcm_pairs=[info['models'][0]],  # One model for an initial generation check
    fwg_scenarios=['rcp85'],
    fwg_timeframes=[2050]
)
```

### Testing downloaded regional JARs

From the repository, run `python -m pytest`. Unit tests cover all nine domains without Java. To check the catalogs and CLI help of downloaded JARs:

```text
python -m pytest tests/test_cordex_integration.py --fwg-jar-dir "path/to/jars" -m "not morphing" -v -rs
```

Use `--fwg-java "path/to/jdk/bin/java.exe"` if needed. `FWG_JAR_DIR` and `FWG_JAVA` are equivalent environment variables. Missing regions are reported as skipped; every JAR version present is checked. These checks verify metadata, command construction and CLI startup. They do not generate weather.

For actual generation, put valid regional baselines in a separate folder named `EUR-11.epw`, `MNA-22.epw`, `AFR-22.epw`, `NAM-44.epw`, `CAM-44.epw`, `SAM-44.epw`, `WAS-22.epw`, `SEA-22.epw` and `AUS-22.epw`, then run:

```text
python -m pytest tests/test_cordex_integration.py --fwg-jar-dir "path/to/jars" --fwg-epw-dir "path/to/regional-epws" -m morphing -v -rs
```

Each available region runs its full eligible ensemble through the workflow and one model through the simple API, using one shared scenario and one period. The tests require a nonempty EPW/STAT pair and check the EPW record count. Missing regional baselines are skipped. Use real weather from inside each domain; changing the coordinates of a European example is not a valid regional baseline. Set `--fwg-cache-dir "path/to/cache"` to reuse extracted models between tests. Europe v3.2.0 contains about 11.3 GB of uncompressed climate data; allow additional space for extraction. See the [CORDEX guide](docs/source/cordex.rst) for details and limitations, including baseline rejection by SolarQC.

## Documentation

The full documentation is available at [pyfwg.readthedocs.io](https://pyfwg.readthedocs.io/en/latest/).

The [interface and Excel guide](docs/source/compatibility.rst) records the supported JAR/class combinations, real API/workflow/DataFrame/XLSX checks and validation limits. Global v3/v4 and Europe v1/v2 are outside the supported scope; historical adapters in the source do not imply current binary compatibility.

The 2026-10-29 interface validation passed all four routes for all ten available JARs (40 generations), plus nine-region XLSX batches with one model and with full eligible ensembles (18 more generations). The 58 EPW/STAT pairs were checked for hourly records, station coordinates and temperature changes. Regional JARs were also verified from an external drive. These checks use one scenario/period per distribution; they do not cover every scientific setting.

Start with the [CORDEX regional notebook](pyfwg/tutorials/cordex_regions_example.ipynb) for all nine JARs, catalog inspection, a direct API call, a workflow preview and a batch across regions. The [direct API](pyfwg/tutorials/epw_morph_global_europe_example.ipynb), [workflow](pyfwg/tutorials/morphingworkflow_global_europe_example.ipynb) and [iterator](pyfwg/tutorials/morphingiterator_example.ipynb) notebooks use the current Global, Europe and regional distributions. Their outputs, tables and climate-comparison figures are saved and rendered on Read the Docs without running Java.

Each notebook also has a `*_simple.ipynb` alternative with explicit paths and direct calls, without preventive path checks or fallback branches. The full versions retain their helpers and an opt-in generation switch; the simplified versions generate weather when their cells run. See the [comparison of both styles](docs/source/tutorial_comparison.rst). Install notebook/plotting dependencies with `pip install pyfwg[tutorials]`.

To obtain the notebooks and bundled example files from an installed package:

```python
from pyfwg import copy_tutorials
copy_tutorials('./pyfwg_tutorials')
```

The full notebooks configure `FWG_JAR_DIR`, optional `FWG_GLOBAL_JAR_PATH`, `FWG_EPW_DIR`, `FWG_CACHE_DIR`, `FWG_OUTPUT_DIR` and optional `FWG_JAVA`. Environment variables override an optional, Git-ignored `fwg.local.json`, which overrides notebook defaults. Regional examples use real EPWs named `<domain>.epw`, with public sample links in the regional notebook, and separate caches by distribution/version. Set `FWG_RUN_MORPHING=1` or `RUN_MORPHING=True` to regenerate the saved examples; generation otherwise stays disabled. The simplified copies use explicit paths and run directly. See the [CORDEX guide](docs/source/cordex.rst) for disk requirements, SolarQC diagnostics, the validation matrix and baseline-period limitations.

## Changelog

A detailed history of all changes made to the library is available in the [CHANGELOG](https://github.com/dsanchez-garcia/pyfwg/blob/main/CHANGELOG.md) file.

## Acknowledgements

This library would not be possible without the foundational work of **Eugénio Rodrigues (University of Coimbra)**, the creator of the [Future Weather Generator tool](https://future-weather-generator.adai.pt/). `pyfwg` is essentially a Python wrapper designed to automate and streamline the use of his powerful command-line application.

## License

This project is licensed under the GNU (GPLv3) License - see the [LICENSE](https://github.com/dsanchez-garcia/pyfwg/blob/main/LICENSE) file for details.
