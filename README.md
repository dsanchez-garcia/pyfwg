# pyfwg: Python Future Weather Generator

[![PyPI version](https://badge.fury.io/py/pyfwg.svg)](https://badge.fury.io/py/pyfwg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation Status](https://readthedocs.org/projects/pyfwg/badge/?version=latest)](https://pyfwg.readthedocs.io/en/latest/?badge=latest)
[![DOI](https://zenodo.org/badge/1039407242.svg)](https://doi.org/10.5281/zenodo.16908690)

A robust, step-by-step Python workflow manager for the [Future Weather Generator](https://future-weather-generator.adai.pt/) command-line tool.

`pyfwg` provides a safe and intuitive way to automate the morphing of EnergyPlus Weather (EPW) files for future climate scenarios. It supports both the **Global** and **Europe-specific** versions of the Future Weather Generator tool.

## Key Features

- **Multiple Interfaces**: Use simple one-shot functions for direct tasks, advanced workflow classes for custom renaming, or a powerful iterator for large-scale parametric studies.
- **Step-by-Step Control**: The advanced workflow allows you to map, configure, preview, and then execute, preventing errors before they happen.
- **Flexible Filename Mapping**: Handle both structured (regex-based) and unstructured (keyword-based) filenames with ease.
- **Built-in Validation**: Automatically validates all Future Weather Generator parameters before execution, catching typos and invalid values (e.g., unavailable LCZs).
- **Excel Integration**: Export templates and load run configurations directly from Excel files for easy parametric analysis.
- **Clear and Organized Output**: Automatically renames and organizes the final `.epw` and `.stat` files into a clean directory structure.

## What's New in Version 0.2.0?

Version 0.2.0 is a major update that introduces powerful new capabilities for parametric analysis and expanded tool support. For a full list of changes, see the [CHANGELOG.md](CHANGELOG.md) file.

-   **Parametric Analysis with `MorphingIterator`**: The biggest new feature is the `MorphingIterator` class, designed to automate large batches of simulations. Define all your runs in a Pandas DataFrame or an Excel file and execute them with a single command.
-   **Support for the Europe-Specific Tool**: `pyfwg` now fully supports the European version of the FWG tool with the `MorphingWorkflowEurope` class and `morph_epw_europe` function.
-   **Important API Change**: The original `morph_epw` function has been renamed to `morph_epw_global` to distinguish it from the new Europe-specific function. Also, the `MorphingWorkflow` class has been renamed to `MorphingWorkflowGlobal` to reflect the new new Europe-specific class.

## Requirements

Before using `pyfwg`, you need to have the following installed and configured:

*   **Python 3.9+**
*   **Java**: The `java` command must be accessible from your system's terminal (i.e., it must be in your system's PATH).
*   **Future Weather Generator**: You must download the appropriate `.jar` file from the `official website <https://future-weather-generator.adai.pt/>`_.
    *   The **Global Tool** (`FutureWeatherGenerator_vX.X.X.jar`) has been tested with versions **v3.0.0** and **v3.0.1**.
    *   The **Europe Tool** (`FutureWeatherGenerator_Europe_vX.X.X.jar`) has been tested with version **v1.0.1**.
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

## Documentation
The full documentation is available at [pyfwg.readthedocs.io](https://pyfwg.readthedocs.io/en/latest/).

## Changelog

A detailed history of all changes made to the library is available in the [CHANGELOG.md](CHANGELOG.md) file.

## Acknowledgements

This library would not be possible without the foundational work of **Eugénio Rodrigues (University of Coimbra)**, the creator of the [Future Weather Generator tool](https://future-weather-generator.adai.pt/). `pyfwg` is essentially a Python wrapper designed to automate and streamline the use of his powerful command-line application.

## License

This project is licensed under the GNU (GPLv3) License - see the [LICENSE](LICENSE) file for details.