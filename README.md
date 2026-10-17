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
- **Built-in Validation**: Automatically validates all Future Weather Generator parameters before execution, catching typos and invalid values (e.g., unavailable LCZs).
- **Excel Integration**: Export templates and load run configurations directly from Excel files for easy parametric analysis.
- **Clear and Organized Output**: Automatically renames and organizes the final `.epw` and `.stat` files into a clean directory structure.

## What's New in Version 0.4.0?

Version 0.4.0 adds support for the **FWG Engine**, the shared engine of the latest Future Weather Generator distributions: **Global v5.x**, **Europe v3.x** and the new **CORDEX regional** distributions. Earlier versions keep working exactly as before.

-   **Global v5.x and Europe v3.x**: Use them with the same classes and functions as before (`MorphingWorkflowGlobal`, `morph_epw_global`, etc.). `pyfwg` detects the version from the JAR and builds the new command line for you.
-   **CORDEX regional distributions**: The new `MorphingWorkflowCordex` class and `morph_epw_cordex` function support the Middle East and North Africa, Africa, North America, Central America, South America, West & South Asia, Southeast Asia and Australasia distributions. The region is detected from the JAR, and its scenarios and GCM-RCM pairs are validated.
-   **New FWG Engine options**: Select scenarios and future periods (`fwg_scenarios`, `fwg_timeframes`), solar decomposition, illuminance and infrared models, uncertainty cases (`fwg_uncertainty_variant`), output profile and a shared climate-data cache (`fwg_model_unzipped_folder`). Any other option of the tool can be passed with `fwg_extra_args`.
-   **JAR inspection**: `get_fwg_distribution_info` reads the scenarios, periods and climate models packaged in FWG Engine JARs, which `pyfwg` also uses to validate your configuration.
-   **Urban Heat Island**: The FWG Engine no longer supports the UHI effect. By default, `pyfwg` applies it only with the versions that support it (Global v3/v4 and Europe v1/v2).

## Requirements

Before using `pyfwg`, you need to have the following installed and configured:

*   **Python 3.9+**
*   **Java**: The `java` command must be accessible from your system's terminal (i.e., it must be in your system's PATH).
*   **Future Weather Generator**: You must download the appropriate `.jar` file from the [official website](https://future-weather-generator.adai.pt/).
    *   The **Global Tool** (`FutureWeatherGenerator_vX.X.X.jar`) has been tested with versions **v3.0.0**, **v3.0.1**, and **v4.0.2**.
    *   The **Europe Tool** (`FutureWeatherGenerator_Europe_vX.X.X.jar`) has been tested with versions **v1.0.1** and **v2.0.2**.
    *   The **FWG Engine distributions** have been tested with **Global v5.2.0** (`FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar`, FWG Engine v1.1.0). Europe v3.x (`FutureWeatherGenerator-CORDEX-CMIP5-Europe-EUR-11-v3.X.X.jar`) and the CORDEX regional distributions (`FutureWeatherGenerator-CORDEX-CMIP5-<Region>-<Domain>-v1.X.X.jar`) share the same engine and command-line interface.
## Installation

You can install `pyfwg` directly from PyPI:

```bash
pip install pyfwg
```

## Quick Start: Simple Morphing

For direct morphing without complex renaming, use the `morph_epw_global` function.

```python
from pyfwg import morph_epw_global

# 1. Define paths
jar_path = r"D:\path\to\your\FutureWeatherGenerator_v3.0.1.jar"
epw_file = 'epws/sevilla_present.epw'

# 2. Run the morphing process
# The generated files will appear in './morphed_epws' by default.
created_files = morph_epw_global(
    epw_paths=epw_file,
    fwg_jar_path=jar_path,
    fwg_show_tool_output=True, # See the tool's progress
    fwg_gcms=['CanESM5', 'MIROC6'] # Use a specific set of GCMs
)

print("Successfully created files:")
for f in created_files:
    print(f)
```

### Using FWG v4.x

If you are using version 4, usage is identical! `pyfwg` handles the different command-line syntax (key-value arguments) for you automatically.

```python
# Just point to your v4 JAR
jar_path_v4 = r"D:\path\to\your\FutureWeatherGenerator_v4.0.2.jar"

morph_epw_global(
    epw_paths='epws/weather.epw',
    fwg_jar_path=jar_path_v4,
    # Optional: explicitly set version if detection fails
    # fwg_version='4', 
    fwg_target_uhi_lcz=3
)
```

### Using FWG v5.x (FWG Engine)

Global v5.x (and Europe v3.x) run on the FWG Engine. `pyfwg` builds its command line automatically, and you can use its new options. Options left as `None` keep the defaults of the tool.

```python
jar_path_v5 = r"D:\path\to\your\FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar"

morph_epw_global(
    epw_paths='epws/weather.epw',
    fwg_jar_path=jar_path_v5,
    fwg_gcms=['CanESM5', 'MIROC6'],
    fwg_scenarios=['ssp245', 'ssp585'],    # Only generate these scenarios...
    fwg_timeframes=[2050],                 # ...and this future period
    fwg_uncertainty_variant='WARM_DRY',    # Uncertainty case (default: 'CENTRAL')
    fwg_model_unzipped_folder='./fwg_cache'  # Reuse the unzipped climate data across runs
)
```

The FWG Engine does not support the Urban Heat Island (UHI) effect, so the LCZ arguments are not used with these versions. Use `pyfwg.get_fwg_parameters_info()` to list all the options and their allowed values.

## Advanced Usage: The MorphingWorkflow Class

For complex projects with custom renaming rules, the `MorphingWorkflowGlobal` class gives you full control over each step.

```python
from pyfwg import MorphingWorkflowGlobal

# --- STEP 0: Instantiate the workflow ---
workflow = MorphingWorkflowGlobal()

# --- STEP 1: Map categories from source filenames ---
# Use a regex pattern and normalization rules
workflow.map_categories(
    epw_files=['epws/SVQ_uhi-tipo-2.epw'],
    input_filename_pattern=r'(?P<city>.*?)_(?P<uhi_type>.*)',
    keyword_mapping={
        'city': {'seville': ['sevilla', 'svq']},
        'uhi_type': {'type_2': ['uhi-tipo-2']}
    }
)

# --- STEP 2: Configure and preview the plan ---
workflow.configure_and_preview(
    final_output_dir='./final_results',
    output_filename_pattern='{city}_{uhi_type}_{ssp}_{year}',
    fwg_jar_path=r"D:\path\to\your\FutureWeatherGenerator_v3.0.1.jar",
    fwg_gcms=['CanESM5']
)

# --- STEP 3: Execute the morphing process ---
# This is only called after you are satisfied with the preview and config.
workflow.execute_morphing()
```
## Parametric Runs with the `MorphingIterator`

The `MorphingIterator` is the most powerful feature of `pyfwg`, designed for running **large-scale parametric studies** or processing batches of EPW files that **each require different configurations**.

This is ideal for scenarios where, for example, different EPW files have different available Local Climate Zones (LCZs) and need to be processed with unique parameters. It uses a Pandas DataFrame to define each run, giving you a structured and easily manageable way to define your entire analysis.

```python
import pandas as pd
from pyfwg import MorphingIterator, MorphingWorkflowGlobal

# 1. Initialize the iterator
iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)

# 2. Set default values for the entire batch
iterator.set_default_values(
    fwg_jar_path=r"D:\path\to\your\FutureWeatherGenerator_v3.0.1.jar",
    output_filename_pattern='{city}_{ssp}_{year}_LCZ-{fwg_epw_original_lcz}-to-{fwg_target_uhi_lcz}'
)

# 3. Define the runs that will change in a DataFrame
runs_df = iterator.get_template_dataframe()
runs_df.loc = {
    'epw_paths': 'epws/sevilla.epw',
    'final_output_dir': './results/sevilla_run',
    'fwg_epw_original_lcz': 2, # Use a specific LCZ for Seville
    'fwg_target_uhi_lcz': 3
}
runs_df.loc = {
    'epw_paths': 'epws/london.epw',
    'final_output_dir': './results/london_run',
    'fwg_epw_original_lcz': 6, # Use a different, valid LCZ for London
    'fwg_target_uhi_lcz': 8
}

# 4. Generate the plan and prepare the workflows
iterator.generate_morphing_workflows(
    runs_df=runs_df,
    keyword_mapping={'city': {'sevilla': 'sevilla', 'london': 'london'}}
)

# 5. Execute the entire batch
iterator.run_morphing_workflows()
```
## Using the Europe-Specific Tool

The `pyfwg` library also fully supports the Europe-specific version of the Future Weather Generator. The usage is nearly identical to the global version, with the following key differences:

*   **Class and Function Names**: You must import and use the Europe-specific versions: `MorphingWorkflowEurope` and `morph_epw_europe`.
*   **JAR File Path**: Ensure your `fwg_jar_path` points to the correct `FutureWeatherGenerator_Europe_vX.X.X.jar` file.
*   **Climate Models**: The model parameter is now `fwg_rcm_pairs` instead of `fwg_gcms`. You can import the list of valid pairs from `pyfwg.DEFAULT_EUROPE_RCMS`.
*   **Scenario Placeholder**: For `MorphingWorkflowEurope`, the climate scenarios are RCPs, not SSPs. Therefore, the required placeholder in your `output_filename_pattern` is `{rcp}` instead of `{ssp}`.

### Quick Example

Here is how a call to the simple API function `morph_epw_europe` would look:

```python
from pyfwg import morph_epw_europe, DEFAULT_EUROPE_RCMS

# 1. Define paths
jar_path_europe = r"D:\path\to\your\FutureWeatherGenerator_Europe_v1.0.1.jar"
epw_file = 'epws/brussels.epw'

# 2. Run the morphing process
created_files = morph_epw_europe(
    epw_paths=epw_file,
    fwg_jar_path=jar_path_europe,
    fwg_show_tool_output=True,
    # Note the use of fwg_rcm_pairs
    fwg_rcm_pairs=[list(DEFAULT_EUROPE_RCMS)[0]] # Use the first available RCM pair
)
```

## Using the CORDEX Regional Tools

The CORDEX regional distributions of the Future Weather Generator (e.g., North America `NAM-44` or Africa `AFR-22`) are supported by `MorphingWorkflowCordex` and `morph_epw_cordex`. They work like the Europe-specific versions (`fwg_rcm_pairs` and the `{rcp}` placeholder), with two differences:

*   **Region detection**: The region is detected from the JAR, and only its scenarios and GCM-RCM pairs are accepted. They are listed in `pyfwg.CORDEX_REGIONS` (e.g., the Middle East and North Africa distribution only provides `rcp85`).
*   **No UHI**: These distributions do not support the Urban Heat Island effect.

```python
from pyfwg import morph_epw_cordex, CORDEX_REGIONS

jar_path_nam = r"D:\path\to\your\FutureWeatherGenerator-CORDEX-CMIP5-North-America-NAM-44-v1.2.0.jar"

print(CORDEX_REGIONS['NAM-44'])  # Scenarios and GCM-RCM pairs of North America

created_files = morph_epw_cordex(
    epw_paths='epws/toronto.epw',
    fwg_jar_path=jar_path_nam,
    fwg_scenarios=['rcp85']
)
```

## Documentation
The full documentation is available at [pyfwg.readthedocs.io](https://pyfwg.readthedocs.io/en/latest/).

## Changelog

A detailed history of all changes made to the library is available in the [CHANGELOG](https://github.com/dsanchez-garcia/pyfwg/blob/main/CHANGELOG.md) file.

## Acknowledgements

This library would not be possible without the foundational work of **Eugénio Rodrigues (University of Coimbra)**, the creator of the [Future Weather Generator tool](https://future-weather-generator.adai.pt/). `pyfwg` is essentially a Python wrapper designed to automate and streamline the use of his powerful command-line application.

## License

This project is licensed under the GNU (GPLv3) License - see the [LICENSE](https://github.com/dsanchez-garcia/pyfwg/blob/main/LICENSE) file for details.