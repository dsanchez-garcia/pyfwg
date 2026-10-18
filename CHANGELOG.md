# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Tutorial Notebooks**: The paths to the JAR files are built from a single configuration cell at the top of each notebook (`FWG_JAR_DIR`, which can also be set with an environment variable), instead of being hardcoded in several cells.

### Fixed
- The tutorial notebooks showed absolute paths of the computer where they were run, including the user name, in their code and saved outputs. The saved outputs now show the `<FWG_JAR_DIR>`, `<TEMP>` and `<HOME>` placeholders instead.
- The code cells of the tutorials were not highlighted in the documentation, because the `ipython3` Pygments lexer was not installed. The `docs` extra now includes `ipython`.
- `copy_tutorials` failed on Python 3.9 with a `TypeError` ("expected str, bytes or os.PathLike object, not NoneType") and copied nothing. The `tutorials` folder has no `__init__.py`, and `importlib.resources.files` only supports such namespace packages from Python 3.10. The folder is now looked up from the `pyfwg` package.

## [0.4.0] - 2026-10-17

### Added
- **Support for the FWG Engine distributions**: The latest Future Weather Generator distributions share a common engine (FWG Engine v1.x) with a new command line. `MorphingWorkflowGlobal`/`morph_epw_global` now support **Global v5.x** (FWG CMIP6 Global) and `MorphingWorkflowEurope`/`morph_epw_europe` support **Europe v3.x** (FWG CORDEX-CMIP5 Europe EUR-11). `pyfwg` builds the new command (`-g` action and organized output layout) and collects the weather files from the `weather` subfolder written by the engine.
- **CORDEX Regional Distributions**: Added the `MorphingWorkflowCordex` class and the `morph_epw_cordex` function for the CORDEX-CMIP5 regional distributions (Middle East and North Africa MNA-22, Africa AFR-22, North America NAM-44, Central America CAM-44, South America SAM-44, West & South Asia WAS-22, Southeast Asia SEA-22 and Australasia AUS-22). The region is identified from the JAR and only its scenarios and GCM-RCM pairs are accepted. Added the `CORDEX_REGIONS`, `CORDEX_SCENARIOS` and `DEFAULT_CORDEX_RCMS` constants.
- **New FWG Engine Arguments**: All workflows, API functions and `MorphingIterator.set_default_values` accept `fwg_scenarios`, `fwg_timeframes`, `fwg_decomposition_method`, `fwg_illuminance_method`, `fwg_infrared_method`, `fwg_morphing_method`, `fwg_uncertainty_variant`, `fwg_uncertainty_sigma`, `fwg_output_profile` and `fwg_model_unzipped_folder`. They default to `None`, which keeps the default of the tool, and are validated before execution. When scenarios or periods are selected, the rename plan only includes them.
- **Additional Command-Line Options**: The new `fwg_extra_args` argument passes any other `-key=value` option to the key-value command lines (Global v4+, Europe v2+ and CORDEX regional), except the options already set by `pyfwg`.
- **New Interpolation Methods**: `fwg_interpolation_method_id` accepts the structured-grid methods of the FWG Engine: `SCI` (4), `SGBI` (5) and `STBI` (6).
- **JAR Inspection Utilities**: Added `get_fwg_distribution_info`, which reads the distribution manifest and the climate-model catalog packaged in FWG Engine JARs (scenarios, periods, models and versions), `detect_fwg_tool` and `get_fwg_cli_style`. The workflows use the JAR metadata, when available, to validate models, scenarios and periods.
- **Version Detection**: `detect_fwg_version` recognizes the new JAR names (e.g., `FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar`) and reads the version from FWG Engine JARs whose filename does not include it.
- **Console Logging Helper**: `pyfwg.enable_console_logging()` shows the log messages of `pyfwg` on the console (colored if `colorlog` is installed), for notebooks and scripts that do not configure logging. See the logging fix below.

### Changed
- **UHI Default**: `fwg_add_uhi` now defaults to `None`. The UHI effect is applied as before with Global v3/v4 and Europe v1/v2 and skipped with the FWG Engine, which does not support it (an explicit `fwg_add_uhi=True` is ignored with a warning). `uhi_morph` raises a `ValueError` and `check_lcz_availability` returns `False` for FWG Engine JARs.
- **Legacy Solar Options with the FWG Engine**: `fwg_solar_hour_adjustment` is ignored (the engine deprecated it), and `fwg_diffuse_irradiation_model` is only translated into `fwg_decomposition_method` when it differs from its default, so that the engine's default (`MULTIMODEL_CONSTRAINED_ENSEMBLE`) is used otherwise.
- **Single-Model Ensembles**: The FWG Engine requires at least two models to create an ensemble, so `fwg_create_ensemble` is set to `False` (with a warning) when a single model is selected.
- **Parameter Precedence**: The explicit `fwg_` arguments of the workflows and of the simple API functions now default to `None`, which means "not set". Only the arguments that are passed override `fwg_params`; the others take the value of `fwg_params` or, if it is not set there, the same default as before (e.g., 72 hours for `fwg_month_transition_hours`). `MorphingIterator` no longer fills the `fwg_` parameters that a run leaves empty with those defaults, so the `fwg_params` of the run apply (empty cells appear as missing values in `morphing_workflows_plan_df`).
- **Enum Validation**: The allowed values of the interpolation method, solar hour adjustment and diffuse model are now enforced for each version of the tool (they were defined but not applied).
- **Iterator Defaults**: `MorphingIterator.set_default_values` also accepts `fwg_output_type`, and ignores with a warning any argument that the workflow class does not accept (e.g., `fwg_add_uhi` for `MorphingWorkflowCordex`).
- **Excel Integration**: `load_runs_from_excel` also converts the `scenario_mapping`, `fwg_params`, `fwg_scenarios`, `fwg_timeframes` and `fwg_extra_args` columns.
- **Global v4 / Europe v2 Commands**: `fwg_limit_variables` is now passed to the tool (`-epw_dictionary_limits`); it was previously ignored. The default list of models is passed in a deterministic (sorted) order.

### Fixed
- `fwg_params` was ignored for most parameters: the explicit `fwg_` arguments always replaced its values with their defaults (e.g., `fwg_params={'month_transition_hours': 24}` ran with 72 hours). See "Parameter Precedence" above.
- Integer parameters given as floats or NumPy numbers (e.g., `14.0` or `72.0`, as pandas reads the Excel columns that have empty cells) reached the tool as `-smooth_hours=72.0` or `-uhi=true:14.0:2.0` (`1:14.0:2.0` with Global v3), also in `uhi_morph`, and appeared with decimals in the filename placeholders. They are now converted to integers. Values with decimals (e.g., an LCZ of 14.5) and non-numeric values make the configuration invalid, instead of raising a `TypeError` or being truncated.
- Boolean flags were interpreted differently by each version of the tool: `fwg_add_uhi=1` disabled the UHI effect with Global v4, and `fwg_add_uhi='False'` (as read from Excel) applied it with Global v3. All flags now accept `True`/`False` (also NumPy booleans), `1`/`0` and `'true'`/`'false'` in any case, with the same meaning in every version; any other value makes the configuration invalid.
- `sanitize_epw_minutes`, which is applied to the copy of every EPW file passed to the tool, removed the non-UTF-8 characters of the header (e.g., `Málaga` became `Mlaga`) and changed the line endings. It now processes the file as bytes and only modifies the data records after the header.
- The overwrite check of `MorphingIterator.generate_morphing_workflows` reported a false "Definitive file overwrite" error for runs that write to different `final_output_dir` folders, only used the `output_filename_pattern` of the first run, and checked a single filename per run instead of one per input file, so real collisions went unnoticed. The workflows are now prepared first, and the check compares the absolute paths of all the files in their rename plans. When the check raises an error, no workflows are left prepared.
- `MorphingIterator` failed with "The truth value of an array is ambiguous" when a column with lists (e.g., `fwg_gcms`) had a default value set with `set_default_values`.
- Importing `pyfwg` removed the handlers of the root logger and set its level to INFO, changing the logging configuration of the application. The modules now log to the `pyfwg` logger, which only has a `NullHandler`. Call `pyfwg.enable_console_logging()` to show the messages on the console as before.
- `uhi_morph(raise_on_error=False)` still raised the errors of the tool. It now logs them and returns `False` (and `True` when the UHI effect is applied).
- `MorphingWorkflowCordex` accepted the JARs of Europe v1.x and v2.x and built the FWG Engine command line for them. It now requires an FWG Engine distribution (Europe v3+ or a CORDEX regional distribution) and suggests `MorphingWorkflowEurope` otherwise.
- The `MorphingIterator` examples of the README and of the class docstring used `runs_df.loc = {...}`, which raises an `AttributeError`. They now use `runs_df.loc[len(runs_df)] = {...}`.
- `openpyxl` is now a dependency, since `export_template_to_excel` and `load_runs_from_excel` failed on a clean installation without it.
- The simple API functions no longer move the temporary copy of the input EPW file to the output folder, and they now move the `.met` and `.csv` weather files of the `SPAIN_MET` and `PORTUGAL_CSV` output types. Only the files of the future scenarios are moved; other weather files (e.g., the baseline processed by the FWG Engine) remain in the temporary directory.
- Only the weather and `.stat` files of the selected output type are renamed, and a generated file is no longer silently overwritten when several files map to the same final name (the first one is kept and a warning is logged).
- A run of the tool that exceeds the time limit is reported as failed instead of stopping the whole workflow.
- `check_lcz_availability` logs unexpected errors instead of failing silently.
- Error messages referred to `set_morphing_config()` instead of `configure_and_preview()`.

## [0.3.0] - 2025-12-29

### Added
- **New Utility: `get_fwg_parameters_info`**: Added a helper function to retrieve all available FWG parameters, their descriptions, defaults, and allowed values. This is especially useful for guiding users when using the new string-based parameter inputs in V4.
- **Improved Notebooks**: Updated all tutorial notebooks to include examples of how to use `get_fwg_parameters_info` to explore and validate parameter values.
- **Enhanced `MorphingWorkflowEurope`**: Added support for the `PORTUGAL_CSV` output type in Europe v2, allowing for generation of Portuguese-specific meteorological files.
- **Support for Future Weather Generator v4.x**: `pyfwg` now fully supports the new version of the global tool, which uses a different command-line interface (dynamic key-value arguments instead of positional ones).
- **Auto-Detection of Tool Version**: Added `detect_fwg_version` utility. The library now automatically detects whether the provided JAR file is v3 or v4 based on the filename (e.g., `FutureWeatherGenerator_v4.0.2.jar`).
- **Manual Version Override**: Added a new `fwg_version` parameter to `morph_epw_global`, `morph_epw_europe`, and all `MorphingWorkflow` classes. This allows users to manually specify the version (e.g., `fwg_version='4'`) if auto-detection fails or non-standard filenames are used.
- **Dynamic Command Construction**: Implemented internal logic (`_build_command_v4`) to construct the correct Java commands for v4, including handling of the new key-value parameter format (e.g., `-uhi=true:14:1`).

### Changed
- **Workflow Parameter Mapping**: Updated `MorphingWorkflowGlobal` to map integer IDs (like Interpolation Method or Solar Model) to their corresponding string values required by FWG v4 (e.g., `0` -> `'IDW'`).
- **Flexible Parameter Inputs**: `pyfwg` now accepts **both** legacy integer IDs (automapped to V4 strings) AND direct string values (e.g., `'IDW'`, `'By_Day'`, `'AVG4P'`) for V4 parameters in `morph_epw_global`, `morph_epw_europe` and all workflow classes.
- **Iterator Enhancement**: Updated `MorphingIterator` to accept and pass the new `fwg_version` parameter to all generated workflows.
- **Validation Logic**: Updated internal validation to support both v3 and v4 model names and parameters.

### Fixed
- **LCZ Availability Check**: Improved error handling in `get_available_lczs` to gracefully handle cases where the Java tool might fail or return unexpected output.
- **Workflow Cleanup**: Fixed a minor bug in temporary file cleanup to ensure all analysis folders are handled correctly.

## [0.2.1] - 2025-09-29

### Changed
- Improved overwrite validation in `MorphingIterator`. It now collects and reports all colliding filenames in a single, comprehensive error message, instead of failing on the first one found. This makes debugging `output_filename_pattern` configurations much easier.

## [0.2.0] - 2025-09-28

### Added
- **Support for Europe-Specific Tool**:
    - Added `MorphingWorkflowEurope` class for advanced workflows with RCP scenarios and GCM-RCM pairs.
    - Added `morph_epw_europe` function for simple, one-shot morphing.
- **Parametric Analysis with `MorphingIterator`**: A powerful new class for running large batches of morphing simulations defined in a Pandas DataFrame or Excel file.
- **Excel Integration**: Added `export_template_to_excel` and `load_runs_from_excel` utility functions to allow users to define parametric runs in a spreadsheet.
- **Pre-flight LCZ Validation**: The `execute_morphing` methods and API functions now automatically check for Local Climate Zone (LCZ) availability before running, preventing errors.
- **LCZ Utility Functions**: Added `check_lcz_availability` and `get_available_lczs` to allow users to validate and discover available LCZs for their EPW files.
- **Robust Filename Overwrite Prevention**: The `MorphingIterator` now intelligently detects all parameters and file categories that vary between runs and raises an error if they are not included as placeholders in the `output_filename_pattern`, preventing accidental data loss.
- **Execution Plan Inspection**: The `MorphingIterator` now stores the final, detailed DataFrame of all runs in the `morphing_workflows_plan_df` attribute and the prepared instances in `prepared_workflows` for user inspection before execution.
- **Optional Colored Logging**: Added `colorlog` as a dependency to provide clear, color-coded terminal output for warnings and errors.

### Changed
- **API Renaming**: Renamed the original `morph_epw` function to `morph_epw_global` for clarity.
- **Workflow Refactoring**: Refactored the original `MorphingWorkflow` class into a more robust base class (`_MorphingWorkflowBase`) and two specialized child classes (`MorphingWorkflowGlobal`, `MorphingWorkflowEurope`) to eliminate code duplication and provide a clear, type-safe API.
- **Improved `MorphingIterator` Workflow**: The iterator now uses a more intuitive three-step process: `generate_morphing_workflows`, `prepare_workflows`, and `run_morphing_workflows`.
- **Enhanced `MorphingIterator` Flexibility**: The `set_default_values` method now has an explicit signature for all possible arguments, improving auto-completion and providing warnings for inapplicable parameters.

### Fixed
- Fixed a critical bug in `MorphingIterator` where default values for parameters not present in the user's DataFrame were not being applied correctly.
- Fixed a bug where the `MorphingIterator` was checking for the internal parameter name (`gcms`) instead of the public-facing one (`fwg_gcms`), causing validation to fail incorrectly.
- Fixed a bug in the `uhi_morph` utility where error logs were printed to the console even when handled internally, cleaning up the output for validation checks.
- Fixed a bug where temporary files were deleted even when `delete_temp_files=False`.
- Made the deletion of temporary files more robust on Windows to prevent `PermissionError`.
- Corrected the logic for including/excluding tutorial files and the `wip` directory in the final distribution package.

## [0.1.0] - 2025-08-20

### Fixed
- Initial bug fixes and improvements to the first public release.

[Unreleased]: https://github.com/dsanchez-garcia/pyfwg/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/dsanchez-garcia/pyfwg/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/dsanchez-garcia/pyfwg/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/dsanchez-garcia/pyfwg/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/dsanchez-garcia/pyfwg/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/dsanchez-garcia/pyfwg/releases/tag/v0.1.0