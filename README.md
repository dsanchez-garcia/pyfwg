# pyfwg: Python Future Weather Generator

[![PyPI version](https://badge.fury.io/py/pyfwg.svg)](https://badge.fury.io/py/pyfwg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation Status](https://readthedocs.org/projects/pyfwg/badge/?version=latest)](https://pyfwg.readthedocs.io/en/latest/?badge=latest)

A robust, step-by-step Python workflow manager for the [FutureWeatherGenerator](https://future-weather-generator.adai.pt/) command-line tool.

`pyfwg` provides a safe and intuitive way to automate the morphing of EnergyPlus Weather (EPW) files. It offers two main interfaces:
- A simple, one-shot function for direct morphing.
- A powerful `MorphingWorkflow` class for complex scenarios involving filename parsing, category mapping, and detailed process control.

## Key Features

- **Simple and Advanced APIs**: Use a single function for quick tasks or a full workflow class for complex projects.
- **Step-by-Step Control**: Analyze, preview, configure, and then execute, preventing errors before they happen.
- **Flexible Filename Mapping**: Handle both structured (regex-based) and unstructured (keyword-based) filenames with ease.
- **Built-in Validation**: Automatically validates all `FutureWeatherGenerator` parameters before execution to catch typos and invalid values.
- **Clear and Organized Output**: Automatically renames and organizes the final `.epw` and `.stat` files into a clean directory structure.

## Requirements

Before using `pyfwg`, you need to have the following installed and configured:

*   **Python 3.9+**
*   **Java**: The `java` command must be accessible from your system's terminal (i.e., it must be in your system's PATH).
*   **FutureWeatherGenerator**: You must download the tool's `.jar` file. This library has been tested with FutureWeatherGenerator **v3.0.0** and **v3.0.1**.
    *   [Download from the official website](https://future-weather-generator.adai.pt/)

## Installation

You can install `pyfwg` directly from PyPI:

```bash
pip install pyfwg
```

## Quick Start: Simple Morphing

For direct morphing without complex renaming, use the `morph_epw` function. It provides full control over the FWG tool's parameters in a single call.

```python
from pyfwg import morph_epw

# 1. Define paths
jar_path = r"D:\path\to\your\FutureWeatherGenerator_v3.0.0.jar"
epw_file = 'epws/sevilla_present.epw'

# 2. Run the morphing process
# The generated files will appear in './morphed_epws' by default.
created_files = morph_epw(
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

For complex projects with custom renaming rules, the `MorphingWorkflow` class gives you full control over each step.

```python
from pyfwg import MorphingWorkflow

# --- STEP 0: Instantiate the workflow ---
workflow = MorphingWorkflow()

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

# --- STEP 2: Define the output and preview the plan ---
workflow.preview_rename_plan(
    final_output_dir='./final_results',
    output_filename_pattern='{city}_{uhi_type}_{ssp}_{year}',
    scenario_mapping={'ssp585': 'SSP5-8.5'}
)

# --- STEP 3: Set and validate the execution configuration ---
workflow.set_morphing_config(
    fwg_jar_path=r"D:\path\to\your\FutureWeatherGenerator_v3.0.0.jar",
    fwg_interpolation_method_id=2, # Override a specific parameter
    fwg_show_tool_output=True
)

# --- STEP 4: Execute the morphing process ---
# This is only called after you are satisfied with the preview and config.
if workflow.is_config_valid:
    workflow.execute_morphing()
```

## Acknowledgements

This library would not be possible without the foundational work of **Eugénio Rodrigues (University of Coimbra)**, the creator of the [FutureWeatherGenerator tool](https://future-weather-generator.adai.pt/). `pyfwg` is essentially a Python wrapper designed to automate and streamline the use of his powerful command-line application.

## License

This project is licensed under the GNU (GPLv3) License - see the [LICENSE](LICENSE) file for details.