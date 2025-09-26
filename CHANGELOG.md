# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Your next great feature!

## [0.2.0] - 2025-09-XX

### Added
- **Support for Europe-Specific Tool**:
    - Added `MorphingWorkflowEurope` class for advanced workflows with RCP scenarios and GCM-RCM pairs.
    - Added `morph_epw_europe` function for simple, one-shot morphing.
- **Pre-flight LCZ Validation**: The `execute_morphing` methods and API functions now automatically check for Local Climate Zone (LCZ) availability before running, preventing errors.
- **LCZ Utility Functions**: Added `check_lcz_availability` and `get_available_lczs` to allow users to validate and discover available LCZs for their EPW files.
- **Parametric Analysis with `MorphingIterator`**: A powerful new class for running large batches of morphing simulations defined in a Pandas DataFrame or Excel file.
- **Excel Integration**: Added `export_template_to_excel` and `load_runs_from_excel` utility functions.
- **Optional Colored Logging**: Added `colorlog` as a dependency to provide clear, color-coded terminal output.

### Changed
- **API Renaming**: Renamed the original `morph_epw` function to `morph_epw_global` for clarity.
- **Workflow Refactoring**: Refactored the original `MorphingWorkflow` class into a more robust base class (`_MorphingWorkflowBase`) and two specialized child classes (`MorphingWorkflowGlobal`, `MorphingWorkflowEurope`) to eliminate code duplication and provide a clear, type-safe API.
- **Iterator Workflow**: The `MorphingIterator` now uses a more intuitive three-step process: `generate_morphing_workflows`, `prepare_workflows`, and `run_morphing_workflows`.

### Fixed
- Fixed a bug where the `MorphingIterator` would fail if mandatory parameters were set as defaults instead of in the DataFrame.
- Fixed a bug where temporary files were deleted even when `delete_temp_files=False`.
- Made the deletion of temporary files more robust on Windows to prevent `PermissionError`.
- Corrected the logic for including/excluding tutorial files and the `wip` directory in the final distribution package.

## [0.1.1] - 2025-08-XX

### Fixed
- Initial bug fixes and improvements to the first public release.

[Unreleased]: https://github.com/dsanchez-garcia/pyfwg/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/dsanchez-garcia/pyfwg/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/dsanchez-garcia/pyfwg/releases/tag/v0.1.1