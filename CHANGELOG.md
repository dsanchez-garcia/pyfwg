# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]


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

[Unreleased]: https://github.com/dsanchez-garcia/pyfwg/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/dsanchez-garcia/pyfwg/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/dsanchez-garcia/pyfwg/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/dsanchez-garcia/pyfwg/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/dsanchez-garcia/pyfwg/releases/tag/v0.1.1