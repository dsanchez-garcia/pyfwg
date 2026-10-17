# pyfwg/workflow.py

import os
import re
import math
import numbers
import shutil
import subprocess
import logging
from typing import List, Optional, Dict, Any, Union, Tuple

# Import the functions from the utils.py file
from .utils import (
    check_lcz_availability, _robust_rmtree, detect_fwg_version, sanitize_epw_minutes,
    detect_fwg_tool, get_fwg_cli_style, get_fwg_distribution_info,
    _detect_cordex_domain, _normalize_scenario_id, _to_bool, _as_integer, _as_number
)

# Import constants from the local constants.py file
from .constants import (
    ALL_POSSIBLE_YEARS,
    DEFAULT_GLOBAL_GCMS, GLOBAL_SCENARIOS,
    DEFAULT_EUROPE_RCMS, EUROPE_SCENARIOS,
    DEFAULT_CORDEX_RCMS, CORDEX_SCENARIOS, CORDEX_REGIONS,
    FWG_CLI_POSITIONAL, FWG_CLI_KEY_VALUE, FWG_CLI_ENGINE,
    ENGINE_INTERPOLATION_METHODS, ENGINE_DECOMPOSITION_METHODS,
    ENGINE_ILLUMINANCE_METHODS, ENGINE_INFRARED_METHODS,
    ENGINE_MORPHING_METHODS, ENGINE_UNCERTAINTY_VARIANTS,
    ENGINE_OUTPUT_PROFILES
)

logger = logging.getLogger(__name__)

# --- String values used by Global v4 / Europe v2 for the legacy integer IDs ---
_LEGACY_INTERPOLATION_METHODS = {0: 'IDW', 1: 'BI', 2: 'AVG4P', 3: 'NP'}
_LEGACY_SOLAR_HOUR_ADJUSTMENTS = {0: 'None', 1: 'By_Month', 2: 'By_Day'}
_LEGACY_DIFFUSE_MODELS = {0: 'Ridley_Boland_Lauret_2010', 1: 'Engerer_2015', 2: 'Paulescu_Blaga_2019'}

# FWG Engine decomposition methods equivalent to the legacy diffuse models.
_LEGACY_DIFFUSE_TO_DECOMPOSITION = {
    0: 'RIDLEY_BOLAND_LAURET_2010', 1: 'ENGERER_2015_METHOD_2', 2: 'PAULESCU_BLAGA_2019',
    'RIDLEY_BOLAND_LAURET_2010': 'RIDLEY_BOLAND_LAURET_2010', 'ENGERER_2015': 'ENGERER_2015_METHOD_2',
    'PAULESCU_BLAGA_2019': 'PAULESCU_BLAGA_2019'
}

# Defaults of the FWG parameters that pyfwg passes to every version of the tool.
# They apply to the parameters that are neither passed as explicit `fwg_`
# arguments nor set in `fwg_params`.
_FWG_PARAM_DEFAULTS = {
    'create_ensemble': True,
    'winter_sd_shift': 0.0,
    'summer_sd_shift': 0.0,
    'month_transition_hours': 72,
    'use_multithreading': True,
    'interpolation_method_id': 0,
    'limit_variables': True,
    'solar_hour_adjustment': 1,
    'diffuse_irradiation_model': 1,
    'epw_original_lcz': 14,
    'target_uhi_lcz': 1,
    'output_type': 'EPW',
}

# Boolean FWG parameters.
_BOOLEAN_PARAMS = ('create_ensemble', 'use_multithreading', 'limit_variables', 'add_uhi')

# Numeric FWG parameters: (minimum, maximum, whether the value must be an integer).
_NUMERIC_PARAM_RANGES = {
    'winter_sd_shift': (-2.0, 2.0, False),
    'summer_sd_shift': (-2.0, 2.0, False),
    'month_transition_hours': (0, 336, True),
    'epw_original_lcz': (1, 17, True),
    'target_uhi_lcz': (1, 17, True),
}

# FWG parameters that take an integer ID or the name of an option.
_OPTION_ID_PARAMS = ('interpolation_method_id', 'solar_hour_adjustment', 'diffuse_irradiation_model')

# Parameters that only the FWG Engine distributions (Global v5+, Europe v3+ and
# CORDEX regional) understand. Their default (None) leaves the tool's default.
_ENGINE_ONLY_PARAMS = (
    'scenarios', 'timeframes', 'decomposition_method', 'illuminance_method', 'infrared_method',
    'morphing_method', 'uncertainty_variant', 'uncertainty_sigma', 'output_profile',
    'model_unzipped_folder'
)

# Command-line options set by pyfwg itself, which cannot be passed through `fwg_extra_args`.
_RESERVED_CLI_OPTIONS = {
    'epw', 'epw2', 'output', 'output_folder', 'output_layout', 'output_type', 'models', 'gcm',
    'ensemble', 'scenarios', 'timeframes', 'temp_shift_winter', 'temp_shift_summer', 'smooth_hours',
    'multithread', 'grid_interpolation_method', 'grid_method', 'epw_dictionary_limits', 'epw_limits',
    'solar_correction', 'solar_adjustment', 'decomposition_method', 'diffuse_method', 'diffuse_model',
    'illuminance_method', 'infrared_method', 'morphing_method', 'uncertainty_variant',
    'uncertainty_sigma', 'output_profile', 'model_unzipped_folder', 'uhi'
}

# Maximum duration of a single run of the tool, in seconds. The FWG Engine also
# validates the baseline and writes reports, so it is given more time.
_TOOL_TIMEOUT_SECONDS = {FWG_CLI_POSITIONAL: 600, FWG_CLI_KEY_VALUE: 600, FWG_CLI_ENGINE: 3600}


def _normalize_option(value: Any) -> str:
    """(Private) Normalizes an option value as the FWG Engine does (e.g., 'warm-dry' -> 'WARM_DRY')."""
    return str(value).strip().replace('-', '_').replace(' ', '_').upper()


def _canonical_model_id(model: Any) -> str:
    """(Private) Returns the model identifier used by the FWG Engine, where '_' and '-' are equivalent."""
    return str(model).strip().replace('_', '-')


def _as_list(value: Any) -> List[Any]:
    """(Private) Converts a single value, a comma-separated string or an iterable into a list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(',') if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _normalize_timeframe(value: Any) -> Any:
    """(Private) Converts a future period (e.g., 2050, 2050.0, '2050' or '2050s') into an integer year."""
    year = _as_int_id(value)
    if year is not None:
        return year
    text = re.sub(r'[^0-9a-z]', '', str(value).lower())
    if text.endswith('s'):
        text = text[:-1]
    return int(text) if text.isdigit() else value


def _as_int_id(value: Any) -> Optional[int]:
    """(Private) Returns an integer ID, also from NumPy integers or floats such as 1.0 (e.g., read from Excel)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _option_from_id(value: Any, options: Dict[int, str], default: str) -> str:
    """(Private) Maps a legacy integer ID to its string value. Strings are passed through unchanged."""
    if value is None:
        return default
    int_id = _as_int_id(value)
    if int_id is not None:
        return options.get(int_id, default)
    return str(value)


def _engine_interpolation_token(value: Any) -> Optional[str]:
    """(Private) Returns the FWG Engine token for an interpolation method ID or name, or None."""
    int_id = _as_int_id(value)
    if int_id is not None:
        return ENGINE_INTERPOLATION_METHODS.get(int_id)
    if isinstance(value, str) and _normalize_option(value) in ENGINE_INTERPOLATION_METHODS.values():
        return _normalize_option(value)
    return None


def _engine_decomposition_from_legacy(value: Any) -> Optional[str]:
    """(Private) Translates a legacy diffuse model (ID or name) into an FWG Engine decomposition method."""
    int_id = _as_int_id(value)
    if int_id is not None:
        return _LEGACY_DIFFUSE_TO_DECOMPOSITION.get(int_id)
    if isinstance(value, str):
        normalized = _normalize_option(value)
        if normalized in ENGINE_DECOMPOSITION_METHODS:
            return normalized
        return _LEGACY_DIFFUSE_TO_DECOMPOSITION.get(normalized)
    return None


def _format_cli_value(value: Any) -> str:
    """(Private) Formats a Python value as a command-line option value."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple, set)):
        return ','.join(str(item) for item in value)
    return str(value)


def _cli_flag(value: Any, default: bool) -> str:
    """(Private) Formats a boolean option as 'true' or 'false'. None takes the default value."""
    return _format_cli_value(default if value is None else _to_bool(value))


def _normalize_param_types(params: Dict[str, Any]):
    """(Private) Converts the FWG parameters to the types expected by the tool, in place.

    Values read from Excel or from DataFrames with gaps are often floats (e.g.,
    14.0 or 72.0), NumPy numbers or strings (e.g., 'False'). They are converted
    when their meaning is unambiguous: integers (14.0 -> 14), numbers (NumPy ->
    Python) and booleans (1, 'false', etc.). Any other value is left unchanged,
    so that the validation rejects it.

    Args:
        params (Dict[str, Any]): The FWG parameters, modified in place.
    """
    for key in _BOOLEAN_PARAMS:
        if params.get(key) is not None:
            try:
                params[key] = _to_bool(params[key])
            except ValueError:
                pass
    for key, (_, _, is_integer) in _NUMERIC_PARAM_RANGES.items():
        if params.get(key) is not None:
            value = _as_integer(params[key]) if is_integer else _as_number(params[key])
            if value is not None:
                params[key] = value
    # Option IDs (e.g., 0.0 -> 0); names such as 'IDW' are kept.
    for key in _OPTION_ID_PARAMS:
        if params.get(key) is not None:
            option_id = _as_integer(params[key])
            if option_id is not None:
                params[key] = option_id
    if params.get('uncertainty_sigma') is not None:
        sigma = _as_number(params['uncertainty_sigma'])
        if sigma is not None:
            params['uncertainty_sigma'] = sigma
    # The version is stored as a string (e.g., 4.0 -> '4').
    if params.get('fwg_version') is not None:
        major_version = _as_integer(params['fwg_version'])
        params['fwg_version'] = str(major_version) if major_version is not None else str(params['fwg_version'])


def _generated_files_dir(temp_dir: str, cli_style: Optional[str]) -> str:
    """(Private) Returns the folder where the tool writes the weather files of a run.

    FWG Engine distributions write them to the 'weather' subfolder of the
    organized output layout, while older versions write them directly into the
    output folder.
    """
    if cli_style == FWG_CLI_ENGINE:
        return os.path.join(temp_dir, 'weather')
    return temp_dir


def _weather_file_extensions(output_type: Optional[str]) -> Tuple[str, str]:
    """(Private) Returns the extensions of the weather and statistics files for an output type."""
    weather_extension = {'SPAIN_MET': '.met', 'PORTUGAL_CSV': '.csv'}.get(str(output_type or 'EPW').upper(), '.epw')
    return weather_extension, '.stat'


class _MorphingWorkflowBase:
    """(Private) Base class containing the shared logic for all morphing workflows.

    This class is not intended to be instantiated directly by the user. Instead,
    it serves as a foundation for specialized child classes like
    `MorphingWorkflowGlobal` and `MorphingWorkflowEurope`.

    It implements the entire state machine logic (map, configure & preview,
    execute) in a generic way, relying on configuration provided by the
    child classes' class attributes.

    Attributes:
        inputs (Dict[str, Any]): A dictionary that stores all user-provided
            configuration from every step of the workflow. It serves as the
            central "memory" for the instance.
        epw_categories (Dict[str, Dict[str, str]]): A dictionary mapping the
            absolute path of each *successfully and completely* categorized EPW
            file to a dictionary of its categories.
        incomplete_epw_categories (Dict[str, Dict[str, str]]): Similar to
            `epw_categories`, but stores files that were mapped but are missing
            one or more expected categories based on the `keyword_mapping` rules.
        epws_to_be_morphed (List[str]): The definitive list of absolute EPW file
            paths that will be processed when `execute_morphing()` is called.
        rename_plan (Dict[str, Dict[str, str]]): A detailed mapping that outlines
            the renaming and moving operations for each generated file.
        is_config_valid (bool): A boolean flag that is set to `True` only if all
            parameters provided in `configure_and_preview` pass the internal
            validation checks.
        cli_style (Optional[str]): The command-line style of the configured tool:
            'positional' (Global v3, Europe v1), 'key_value' (Global v4,
            Europe v2) or 'engine' (FWG Engine distributions: Global v5+,
            Europe v3+ and CORDEX regional). Set by `configure_and_preview`.
        distribution_info (Optional[Dict[str, Any]]): The metadata packaged in
            FWG Engine JARs (see `get_fwg_distribution_info`), or None if not
            available.
    """
    # --- Define attributes at the class level ---
    # These are now class attributes, accessible without creating an instance.
    tool_scenarios: List[str] = []
    valid_models: set = set()
    model_arg_name: str = ""
    java_class_path_prefix: str = ""
    scenario_placeholder_name: str = ""
    # Distribution family handled by the class: 'global', 'europe' or 'cordex'.
    fwg_tool: str = ""

    def __init__(
            self,
            # tool_scenarios: List[str],
            # valid_models: set,
            # model_arg_name: str,
            # java_class_path_prefix: str,
            # scenario_placeholder_name: str
    ):
        """Initializes the workflow instance's state.

        This sets up the attributes that will store the state of a specific
        workflow run (e.g., user inputs, file plans, etc.). It does not
        take any arguments, as tool-specific configuration is handled by
        the class attributes of its children.
        """
        # --- Tool-specific configuration provided by child classes ---
        # self.tool_scenarios = tool_scenarios
        # self.valid_models = valid_models
        # self.model_arg_name = model_arg_name
        # self.java_class_path_prefix = java_class_path_prefix
        # self.scenario_placeholder_name = scenario_placeholder_name  # e.g., 'ssp' or 'rcp'

        # Instance attributes are now for storing state, not configuration.
        self.inputs: Dict[str, Any] = {}
        self.epw_categories: Dict[str, Dict[str, str]] = {}
        self.incomplete_epw_categories: Dict[str, Dict[str, str]] = {}
        self.epws_to_be_morphed: List[str] = []
        self.rename_plan: Dict[str, Dict[str, str]] = {}
        self.is_config_valid: bool = False
        self.cli_style: Optional[str] = None
        self.distribution_info: Optional[Dict[str, Any]] = None
        self.available_timeframes: List[int] = list(ALL_POSSIBLE_YEARS)

    def map_categories(self,
                       epw_files: List[str],
                       input_filename_pattern: Optional[str] = None,
                       keyword_mapping: Optional[Dict[str, Dict[str, Union[str, List[str]]]]] = None):
        """STEP 1: Identifies and maps categories for each EPW file.

        This method populates the `self.epw_categories` and
        `self.incomplete_epw_categories` attributes by analyzing each filename.
        It supports two primary modes of operation:

        1.  **Pattern Extraction with Normalization:**
            When `input_filename_pattern` is provided, it is used as a regular
            expression to extract "raw" values from structured filenames. The
            pattern MUST use named capture groups (e.g., `(?P<city>...)`).
            If `keyword_mapping` is also provided, it is then used as a
            translation dictionary to normalize the extracted raw values into
            their final, clean form.

        2.  **Keyword-Only Search:**
            When `input_filename_pattern` is `None` and `keyword_mapping` is
            provided, the method searches the entire filename for any of the
            keywords defined in the mapping. This is ideal for unstructured
            or irregularly named files. In this mode, it also checks if all
            defined categories were found for each file.

        Args:
            epw_files (List[str]): A list of absolute or relative paths to the
                EPW files that need to be processed.
            input_filename_pattern (Optional[str], optional): A Python regex
                string with named capture groups. Defaults to None.
                Example: `r'(?P<city>.*?)_(?P<uhi_type>.*)'`
            keyword_mapping (Optional[Dict[str, Dict[str, Union[str, List[str]]]]], optional):
                A dictionary of rules for keyword searching or normalization.
                The innermost value can be a single string for one keyword or a
                list of strings for multiple keywords. Defaults to None.
                Structure: `{category: {final_value: 'keyword' or ['keyword1', 'keyword2']}}`

        Raises:
            ValueError: If neither of `input_filename_pattern` and
                `keyword_mapping` are provided.
        """
        logger.info("--- Step 1: Mapping categories from filenames ---")

        # Ensure that at least one mapping strategy is provided.
        if not input_filename_pattern and not keyword_mapping:
            raise ValueError("You must provide at least one mapping method: 'input_filename_pattern' or 'keyword_mapping'.")

        # Store the provided arguments in the instance's state.
        self.inputs['epw_files'] = epw_files

        # Reset state attributes to ensure the method is idempotent.
        self.epw_categories = {}
        self.incomplete_epw_categories = {}

        # Loop through each provided EPW file path.
        for epw_path in epw_files:
            # Check if the file actually exists before processing.
            if not os.path.exists(epw_path):
                logger.warning(f"EPW file not found, skipping: {epw_path}")
                continue

            # This dictionary will hold the final categories for the current file.
            file_categories = {}
            # Get the filename without the extension (e.g., 'sevilla_uhi-tipo-1').
            epw_base_name = os.path.splitext(os.path.basename(epw_path))[0]

            if input_filename_pattern:
                # --- Mode 1: Pattern Extraction followed by Normalization ---

                # Attempt to match the regex pattern against the filename.
                match = re.search(input_filename_pattern, epw_base_name)
                if not match:
                    logger.warning(f"Pattern did not match '{epw_base_name}'. Skipping.")
                    continue

                # Extract the raw values from the named capture groups.
                raw_values = match.groupdict()
                normalized_values = {}

                # Iterate through the extracted {category: raw_value} pairs.
                for category, raw_value in raw_values.items():
                    # Skip optional groups in the regex that did not match anything.
                    if raw_value is None:
                        continue

                    # Start with the raw value as the default.
                    final_value = raw_value

                    # If a mapping dictionary is provided, try to normalize the raw value.
                    if keyword_mapping and category in keyword_mapping:
                        # Look for the raw value in the keyword lists.
                        for mapped_val, keywords_or_str in keyword_mapping[category].items():
                            # Normalize a single string to a list for consistent processing.
                            keywords_list = [keywords_or_str] if isinstance(keywords_or_str, str) else keywords_or_str
                            if raw_value.lower() in [k.lower() for k in keywords_list]:
                                final_value = mapped_val  # Replace with the clean value.
                                break
                    normalized_values[category] = final_value
                file_categories = normalized_values

            elif keyword_mapping:
                # --- Mode 2: Keyword-only search (no pattern) ---

                # Use the full, lowercase filename for searching.
                epw_name_lower = os.path.basename(epw_path).lower()
                # Iterate through the user-defined mapping rules.
                for category, rules in keyword_mapping.items():
                    for final_value, keywords_or_str in rules.items():
                        # Normalize a single string to a list for consistent processing.
                        keywords_list = [keywords_or_str] if isinstance(keywords_or_str, str) else keywords_or_str
                        # If any keyword is found in the filename, assign the category and stop.
                        if any(keyword.lower() in epw_name_lower for keyword in keywords_list):
                            file_categories[category] = final_value
                            break  # Move to the next category.

            # After processing, check if any categories were successfully found.
            if file_categories:
                logger.info(f"Mapped '{epw_path}': {file_categories}")

                # In keyword-only mode, check for completeness.
                if keyword_mapping and not input_filename_pattern:
                    all_defined_categories = set(keyword_mapping.keys())
                    found_categories = set(file_categories.keys())

                    # If not all categories were found, classify the file as incomplete.
                    if len(found_categories) < len(all_defined_categories):
                        missing = all_defined_categories - found_categories
                        logger.warning(f"File '{os.path.basename(epw_path)}' is missing categories: {list(missing)}.")
                        self.incomplete_epw_categories[epw_path] = file_categories
                    else:
                        # The file is complete.
                        self.epw_categories[epw_path] = file_categories
                else:
                    # In pattern mode, we assume the pattern defines completeness.
                    self.epw_categories[epw_path] = file_categories
            else:
                # If no categories could be mapped, warn the user.
                logger.warning(f"Could not map any categories for '{epw_path}'. Skipping.")

        logger.info("Category mapping complete.")


    def _validate_fwg_params(self, params: Dict[str, Any]) -> bool:
        """(Private) Validates the final FWG parameters against known constraints.

        This helper method is called by `configure_and_preview` to ensure that the
        parameters provided by the user are valid before attempting to run the
        external tool. It uses the class attributes `self.model_arg_name` and
        `self.valid_models` to perform tool-specific validation, and the
        detected version of the tool to check the options of its command line.

        Args:
            params (Dict[str, Any]): A dictionary containing the final,
                user-friendly `fwg_` parameters after all overrides have been
                applied.

        Returns:
            bool: True if all parameters pass validation, False otherwise.
        """
        is_valid = True

        # Determine the command-line style of the tool, which defines the valid options.
        version = str(params.get('fwg_version') or '3')
        try:
            cli_style = get_fwg_cli_style(version, self.fwg_tool or 'global')
        except ValueError as e:
            logger.warning(f"Validation failed: {e}")
            return False
        is_engine = cli_style == FWG_CLI_ENGINE

        # Validate the models (GCMs or RCM pairs) using the instance's specific list.
        if params.get(self.model_arg_name):
            # The FWG Engine treats '_' and '-' as equivalent in model identifiers.
            known_models = {_canonical_model_id(m) for m in self.valid_models} if is_engine else self.valid_models
            for model in params[self.model_arg_name]:
                model_key = _canonical_model_id(model) if is_engine else model
                if model_key not in known_models:
                    logger.warning(f"Validation failed: Model '{model}' is not valid for this tool.")
                    is_valid = False

        # Validate the boolean parameters (accepted strings and numbers are converted beforehand).
        for key in _BOOLEAN_PARAMS:
            value = params.get(key)
            if value is not None and not isinstance(value, bool):
                logger.warning(f"Validation failed: 'fwg_{key}' must be True or False, but it is {value!r}.")
                is_valid = False

        # Validate the type and range of the numeric parameters.
        for key, (minimum, maximum, is_integer) in _NUMERIC_PARAM_RANGES.items():
            value = params.get(key)
            if value is None:
                continue
            expected_type = numbers.Integral if is_integer else numbers.Real
            if isinstance(value, bool) or not isinstance(value, expected_type) or not minimum <= value <= maximum:
                kind = 'an integer' if is_integer else 'a number'
                logger.warning(
                    f"Validation failed: 'fwg_{key}' must be {kind} between {minimum} and {maximum}, "
                    f"but it is {value!r}.")
                is_valid = False

        # Validate enum parameters (Integer IDs or V4 Strings).
        if cli_style == FWG_CLI_POSITIONAL:
            validations = {
                'interpolation_method_id': {0, 1, 2},
                'solar_hour_adjustment': {0, 1, 2},
                'diffuse_irradiation_model': {0, 1, 2}
            }
        elif cli_style == FWG_CLI_KEY_VALUE:
            validations = {
                'interpolation_method_id': set(_LEGACY_INTERPOLATION_METHODS) | set(_LEGACY_INTERPOLATION_METHODS.values()),
                'solar_hour_adjustment': set(_LEGACY_SOLAR_HOUR_ADJUSTMENTS) | set(_LEGACY_SOLAR_HOUR_ADJUSTMENTS.values()),
                'diffuse_irradiation_model': set(_LEGACY_DIFFUSE_MODELS) | set(_LEGACY_DIFFUSE_MODELS.values())
            }
        else:
            # The FWG Engine ignores the solar hour adjustment, and the legacy diffuse
            # model is checked below as an alias of the decomposition method.
            validations = {}
            interpolation_method = params.get('interpolation_method_id')
            if interpolation_method is not None and _engine_interpolation_token(interpolation_method) is None:
                logger.warning(
                    f"Validation failed: 'fwg_interpolation_method_id' has value '{interpolation_method}', "
                    f"but allowed values are {ENGINE_INTERPOLATION_METHODS}.")
                is_valid = False
            diffuse_model = params.get('diffuse_irradiation_model')
            if diffuse_model is not None and _engine_decomposition_from_legacy(diffuse_model) is None:
                logger.warning(
                    f"Validation failed: 'fwg_diffuse_irradiation_model' has value '{diffuse_model}'. "
                    f"Use 'fwg_decomposition_method' with one of {ENGINE_DECOMPOSITION_METHODS}.")
                is_valid = False

        for key, allowed_values in validations.items():
            value = params.get(key)
            try:
                # Booleans are not IDs, although True == 1.
                is_allowed = value is None or (not isinstance(value, bool) and value in allowed_values)
            except TypeError:
                is_allowed = False
            if not is_allowed:
                logger.warning(
                    f"Validation failed: 'fwg_{key}' has value '{value}', but allowed values are "
                    f"{sorted(allowed_values, key=str)}.")
                is_valid = False

        # Parameters of the FWG Engine cannot be used with older versions of the tool.
        engine_only_params = [f"fwg_{name}" for name in _ENGINE_ONLY_PARAMS if params.get(name) is not None]
        if engine_only_params and not is_engine:
            logger.warning(
                f"Validation failed: {engine_only_params} require an FWG Engine distribution "
                f"(Global v5+, Europe v3+ or CORDEX regional), but version {version} of the tool was detected.")
            is_valid = False
        if is_engine and not self._validate_engine_params(params):
            is_valid = False

        if params.get('extra_args') is not None and not self._validate_extra_args(params['extra_args'], cli_style):
            is_valid = False

        # Validate output type.
        if params.get('output_type'):
            valid_output_types = {'EPW', 'SPAIN_MET', 'PORTUGAL_CSV'}
            if params['output_type'] not in valid_output_types:
                logger.warning(f"Validation failed: 'fwg_output_type' has value '{params['output_type']}', but allowed values are {valid_output_types}.")
                if params['output_type'].upper() == 'MET':
                    logger.warning("Suggestion: Did you mean 'SPAIN_MET'?")
                elif params['output_type'].upper() == 'CSV':
                    logger.warning("Suggestion: Did you mean 'PORTUGAL_CSV'?")
                is_valid = False

        return is_valid

    def _validate_engine_params(self, params: Dict[str, Any]) -> bool:
        """(Private) Validates the options that only the FWG Engine distributions support.

        Scenarios, future periods and models are checked against the
        distribution (read from the JAR when possible), and the remaining
        options against the values accepted by the engine's command line.

        Args:
            params (Dict[str, Any]): The final FWG parameters.

        Returns:
            bool: True if all FWG Engine options are valid, False otherwise.
        """
        is_valid = True

        # Validate the selected scenarios and future periods.
        selections = {
            'scenarios': (params.get('scenarios'), self.tool_scenarios),
            'timeframes': (params.get('timeframes'), self.available_timeframes),
        }
        for key, (selected, available) in selections.items():
            if selected is None:
                continue
            if not selected:
                logger.warning(f"Validation failed: 'fwg_{key}' must contain at least one value.")
                is_valid = False
            for value in selected:
                if value not in available:
                    logger.warning(f"Validation failed: '{value}' is not available in 'fwg_{key}'. Available values: {available}.")
                    is_valid = False

        # Validate the options that take a fixed set of values.
        option_validations = {
            'decomposition_method': set(ENGINE_DECOMPOSITION_METHODS) | {'ENGERER_2015'},
            'illuminance_method': set(ENGINE_ILLUMINANCE_METHODS),
            'infrared_method': set(ENGINE_INFRARED_METHODS),
            'morphing_method': set(ENGINE_MORPHING_METHODS),
            'uncertainty_variant': set(ENGINE_UNCERTAINTY_VARIANTS),
            'output_profile': set(ENGINE_OUTPUT_PROFILES),
        }
        for key, allowed_values in option_validations.items():
            value = params.get(key)
            if value is not None and _normalize_option(value) not in allowed_values:
                logger.warning(f"Validation failed: 'fwg_{key}' has value '{value}', but allowed values are {sorted(allowed_values)}.")
                is_valid = False

        sigma = params.get('uncertainty_sigma')
        if sigma is not None:
            try:
                is_valid_sigma = math.isfinite(float(sigma)) and float(sigma) >= 0.0
            except (TypeError, ValueError):
                is_valid_sigma = False
            if not is_valid_sigma:
                logger.warning("Validation failed: 'fwg_uncertainty_sigma' must be a finite, non-negative number.")
                is_valid = False

        # The engine rejects seasonal temperature spreads combined with a non-central case.
        variant = params.get('uncertainty_variant')
        if variant is not None and _normalize_option(variant) != 'CENTRAL':
            if params.get('winter_sd_shift') or params.get('summer_sd_shift'):
                logger.warning(
                    "Validation failed: a non-central 'fwg_uncertainty_variant' cannot be combined with "
                    "non-zero 'fwg_winter_sd_shift' or 'fwg_summer_sd_shift'.")
                is_valid = False

        # Check that every model provides the selected scenarios and periods, when the
        # JAR metadata lists them.
        model_details = {
            _canonical_model_id(model): details
            for model, details in ((self.distribution_info or {}).get('model_details') or {}).items()
        }
        if model_details:
            requested_models = params.get(self.model_arg_name)
            if requested_models is None:
                requested_models = (self.distribution_info or {}).get('ensemble_models') or []
            requested_scenarios = params.get('scenarios') or self.tool_scenarios
            requested_timeframes = [str(t) for t in params.get('timeframes') or self.available_timeframes]
            for model in requested_models:
                details = model_details.get(_canonical_model_id(model))
                if not details:
                    continue
                missing_scenarios = [s for s in requested_scenarios if details['scenarios'] and s not in details['scenarios']]
                missing_timeframes = [t for t in requested_timeframes if details['timeframes'] and t not in details['timeframes']]
                if missing_scenarios or missing_timeframes:
                    logger.warning(
                        f"Validation failed: Model '{model}' does not provide the scenarios {missing_scenarios} "
                        f"or future periods {missing_timeframes}. Restrict 'fwg_scenarios'/'fwg_timeframes' "
                        f"or select other models.")
                    is_valid = False

        return is_valid

    @staticmethod
    def _validate_extra_args(extra_args: Any, cli_style: str) -> bool:
        """(Private) Validates the additional command-line options of `fwg_extra_args`.

        Args:
            extra_args (Any): The value of `fwg_extra_args`.
            cli_style (str): The command-line style of the tool.

        Returns:
            bool: True if the options can be passed to the tool, False otherwise.
        """
        if cli_style == FWG_CLI_POSITIONAL:
            logger.warning(
                "Validation failed: 'fwg_extra_args' requires a key-value command line "
                "(Global v4+, Europe v2+ or CORDEX regional).")
            return False
        if not isinstance(extra_args, dict):
            logger.warning("Validation failed: 'fwg_extra_args' must be a dictionary of option names and values.")
            return False

        is_valid = True
        for key, value in extra_args.items():
            name = str(key).lstrip('-')
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name):
                logger.warning(f"Validation failed: '{key}' is not a valid option name for 'fwg_extra_args'.")
                is_valid = False
            elif name in _RESERVED_CLI_OPTIONS:
                logger.warning(
                    f"Validation failed: option '{name}' is set by pyfwg and cannot be passed through "
                    f"'fwg_extra_args'. Use the corresponding 'fwg_' argument instead.")
                is_valid = False
            if value is None:
                logger.warning(f"Validation failed: option '{name}' in 'fwg_extra_args' has no value.")
                is_valid = False
        return is_valid

    def _reset_tool_capabilities(self):
        """(Private) Restores the scenarios, models and periods defined by the class."""
        self.tool_scenarios = list(type(self).tool_scenarios)
        self.valid_models = set(type(self).valid_models)
        self.available_timeframes = list(ALL_POSSIBLE_YEARS)
        self.distribution_info = None

    def _engine_capabilities(self, fwg_jar_path: str,
                             distribution_info: Optional[Dict[str, Any]]) -> Tuple[List[str], set, List[int]]:
        """(Private) Returns the scenarios, models and future periods of an FWG Engine distribution.

        The metadata packaged in the JAR is used when available. Otherwise, the
        constants of the workflow class are used.

        Args:
            fwg_jar_path (str): Path to the FWG JAR file.
            distribution_info (Optional[Dict[str, Any]]): The metadata read from the JAR, if any.

        Returns:
            Tuple[List[str], set, List[int]]: The scenarios, models and periods.
        """
        if distribution_info:
            scenarios = distribution_info.get('scenarios') or list(type(self).tool_scenarios)
            models = set(distribution_info.get('models') or type(self).valid_models)
            timeframes = [_normalize_timeframe(t) for t in distribution_info.get('timeframes') or []]
            timeframes = [t for t in timeframes if isinstance(t, int)] or list(ALL_POSSIBLE_YEARS)
            return scenarios, models, timeframes
        return list(type(self).tool_scenarios), set(type(self).valid_models), list(ALL_POSSIBLE_YEARS)

    def _check_jar_matches_workflow(self, fwg_jar_path: str, fwg_version: Optional[str] = None):
        """(Private) Blocks the execution if the JAR clearly belongs to another FWG distribution.

        Args:
            fwg_jar_path (str): Path to the FWG JAR file.
            fwg_version (Optional[str], optional): The resolved version of the tool.
        """
        detected_tool = detect_fwg_tool(fwg_jar_path)
        if detected_tool is None or not self.fwg_tool:
            return
        workflow_classes = {
            'global': 'MorphingWorkflowGlobal', 'europe': 'MorphingWorkflowEurope', 'cordex': 'MorphingWorkflowCordex'
        }
        # The Europe distribution (EUR-11) is also a CORDEX regional distribution.
        compatible_tools = {self.fwg_tool, 'europe'} if self.fwg_tool == 'cordex' else {self.fwg_tool}
        if detected_tool not in compatible_tools:
            message = (f"The JAR '{os.path.basename(fwg_jar_path)}' belongs to the '{detected_tool}' distribution of "
                       f"the tool, but {type(self).__name__} works with the '{self.fwg_tool}' distribution.")
            if detected_tool in workflow_classes:
                message += f" Use {workflow_classes[detected_tool]} instead."
            else:
                message += " This distribution is not supported by pyfwg."
            logger.error(message)
            self.is_config_valid = False
            return

        # Only the versions of the Europe distribution that run on the FWG Engine (v3+) are
        # CORDEX regional distributions. Europe v1.x and v2.x use older command lines.
        if detected_tool != self.fwg_tool and fwg_version is not None:
            try:
                detected_cli_style = get_fwg_cli_style(fwg_version, detected_tool)
            except ValueError:
                # An invalid version is already reported when the command-line style is resolved.
                return
            if detected_cli_style != FWG_CLI_ENGINE:
                logger.error(
                    f"The JAR '{os.path.basename(fwg_jar_path)}' is version {fwg_version} of the '{detected_tool}' "
                    f"distribution, which does not run on the FWG Engine. {type(self).__name__} requires an FWG "
                    f"Engine distribution (Europe v3+ or a CORDEX regional distribution). "
                    f"Use {workflow_classes[detected_tool]} instead.")
                self.is_config_valid = False

    def _prepare_engine_params(self, fwg_jar_path: str, params: Dict[str, Any]):
        """(Private) Adapts the parameters to an FWG Engine distribution.

        It reads the distribution metadata from the JAR, normalizes the selected
        scenarios and future periods, translates legacy options and disables
        the options that the FWG Engine no longer supports.

        Args:
            fwg_jar_path (str): Path to the FWG JAR file.
            params (Dict[str, Any]): The final FWG parameters, modified in place.
        """
        self.distribution_info = get_fwg_distribution_info(fwg_jar_path)
        self.tool_scenarios, self.valid_models, self.available_timeframes = self._engine_capabilities(
            fwg_jar_path, self.distribution_info)
        if self.distribution_info:
            logger.info(
                f"Detected {self.distribution_info.get('name')} v{self.distribution_info.get('version')} "
                f"(FWG Engine {self.distribution_info.get('engine_version') or 'unknown version'}).")

        # The FWG Engine does not support the Urban Heat Island effect.
        if params.get('add_uhi'):
            logger.warning(
                "The FWG Engine distributions (Global v5+, Europe v3+ and CORDEX regional) do not support the "
                "Urban Heat Island (UHI) effect, so 'fwg_add_uhi' is ignored. Use FWG Global v4.x or Europe v2.x "
                "(or pyfwg.uhi_morph with those versions) to apply it.")
        params['add_uhi'] = False

        # The legacy diffuse model is an alias of the decomposition method. Only
        # a non-default value is translated, so that the engine's default applies otherwise.
        diffuse_model = params.get('diffuse_irradiation_model')
        if params.get('decomposition_method') is None and diffuse_model not in (None, 1, 'Engerer_2015'):
            decomposition_method = _engine_decomposition_from_legacy(diffuse_model)
            if decomposition_method:
                params['decomposition_method'] = decomposition_method
                logger.info(
                    f"'fwg_diffuse_irradiation_model={diffuse_model}' is applied as "
                    f"'fwg_decomposition_method={decomposition_method}'. Use 'fwg_decomposition_method' to "
                    f"select any of the FWG Engine methods: {ENGINE_DECOMPOSITION_METHODS}.")

        # Normalize the selected scenarios (e.g., 'SSP2-4.5' -> 'ssp245') and periods.
        if params.get('scenarios') is not None:
            available_scenarios = {_normalize_scenario_id(s): s for s in self.tool_scenarios}
            params['scenarios'] = [available_scenarios.get(_normalize_scenario_id(s), s)
                                   for s in _as_list(params['scenarios'])]
        if params.get('timeframes') is not None:
            params['timeframes'] = [_normalize_timeframe(t) for t in _as_list(params['timeframes'])]

        # The engine needs at least two models to build an ensemble. With a single
        # model, the ensemble is equivalent to the output of that model.
        models = params.get(self.model_arg_name)
        if models is not None and len(models) == 1 and params.get('create_ensemble', True):
            logger.warning(
                f"The FWG Engine needs at least two models to create an ensemble. Since only '{models[0]}' "
                f"was selected, 'fwg_create_ensemble' is set to False.")
            params['create_ensemble'] = False

    def _configure_and_preview_base(self, *,
                                    final_output_dir: str,
                                    output_filename_pattern: str,
                                    scenario_mapping: Optional[Dict[str, str]],
                                    # --- All workflow and FWG arguments ---
                                    fwg_jar_path: str,
                                    run_incomplete_files: bool,
                                    delete_temp_files: bool,
                                    temp_base_dir: str,
                                    fwg_show_tool_output: bool,
                                    fwg_params: Optional[Dict[str, Any]],
                                    fwg_models: Optional[List[str]],
                                    fwg_create_ensemble: Optional[bool],
                                    fwg_winter_sd_shift: Optional[float],
                                    fwg_summer_sd_shift: Optional[float],
                                    fwg_month_transition_hours: Optional[int],
                                    fwg_use_multithreading: Optional[bool],
                                    fwg_interpolation_method_id: Optional[Union[int, str]],
                                    fwg_limit_variables: Optional[bool],
                                    fwg_solar_hour_adjustment: Optional[Union[int, str]],
                                    fwg_diffuse_irradiation_model: Optional[Union[int, str]],
                                    fwg_add_uhi: Optional[bool],
                                    fwg_epw_original_lcz: Optional[int],
                                    fwg_target_uhi_lcz: Optional[int],
                                    fwg_output_type: Optional[str] = None,
                                    fwg_version: Optional[Union[str, int]] = None,
                                    # --- FWG Engine arguments (Global v5+, Europe v3+, CORDEX regional) ---
                                    fwg_scenarios: Optional[List[str]] = None,
                                    fwg_timeframes: Optional[List[Union[int, str]]] = None,
                                    fwg_decomposition_method: Optional[str] = None,
                                    fwg_illuminance_method: Optional[str] = None,
                                    fwg_infrared_method: Optional[str] = None,
                                    fwg_morphing_method: Optional[str] = None,
                                    fwg_uncertainty_variant: Optional[str] = None,
                                    fwg_uncertainty_sigma: Optional[float] = None,
                                    fwg_output_profile: Optional[str] = None,
                                    fwg_model_unzipped_folder: Optional[str] = None,
                                    fwg_extra_args: Optional[Dict[str, Any]] = None):
        """(Private) Base method for configuring, validating, and previewing the plan.

        This method is the core of the combined Step 2. It is called by the
        public-facing `configure_and_preview` methods of the child classes.

        It performs three main tasks:
        1.  **Configuration**: It merges the base `fwg_params` dictionary with
            any explicit `fwg_` keyword arguments, with the latter taking
            precedence unless they are None. Parameters set in neither place
            take the defaults of pyfwg, and all values are converted to the
            types expected by the tool (e.g., 14.0 -> 14). It also detects the
            version of the tool and adapts the parameters to its command line.
        2.  **Validation**: It validates the final set of parameters against
            the tool's known constraints and sets the `self.is_config_valid` flag.
        3.  **Preview Generation**: It constructs and prints a detailed "dry run"
            plan, which is also stored in `self.rename_plan`.

        Args:
            (All arguments are passed down from the public-facing methods).
        """
        # Guard clause: Ensure that the mapping step has been completed.
        if not self.epw_categories and not self.incomplete_epw_categories:
            raise RuntimeError("Please run map_categories() first. No files were successfully mapped.")

        logger.info("--- Step 2: Configuring and Previewing Morphing Plan ---")

        # Start by assuming valid config; detection or validation may set it to False.
        self.is_config_valid = True
        self._reset_tool_capabilities()

        # --- 1. Build and Validate Configuration ---
        # Start with the base dictionary, or an empty one if not provided.
        final_fwg_params = fwg_params.copy() if fwg_params else {}

        # Create a dictionary of all explicit keyword arguments. Arguments that were
        # not passed are None, so they do not replace the values of fwg_params.
        overrides = {
            self.model_arg_name: fwg_models,
            'create_ensemble': fwg_create_ensemble,
            'winter_sd_shift': fwg_winter_sd_shift,
            'summer_sd_shift': fwg_summer_sd_shift,
            'month_transition_hours': fwg_month_transition_hours,
            'use_multithreading': fwg_use_multithreading,
            'interpolation_method_id': fwg_interpolation_method_id,
            'limit_variables': fwg_limit_variables,
            'solar_hour_adjustment': fwg_solar_hour_adjustment,
            'diffuse_irradiation_model': fwg_diffuse_irradiation_model,
            'add_uhi': fwg_add_uhi,
            'epw_original_lcz': fwg_epw_original_lcz,
            'target_uhi_lcz': fwg_target_uhi_lcz,
            'output_type': fwg_output_type,
            'fwg_version': fwg_version,
            'scenarios': fwg_scenarios,
            'timeframes': fwg_timeframes,
            'decomposition_method': fwg_decomposition_method,
            'illuminance_method': fwg_illuminance_method,
            'infrared_method': fwg_infrared_method,
            'morphing_method': fwg_morphing_method,
            'uncertainty_variant': fwg_uncertainty_variant,
            'uncertainty_sigma': fwg_uncertainty_sigma,
            'output_profile': fwg_output_profile,
            'model_unzipped_folder': fwg_model_unzipped_folder,
            'extra_args': fwg_extra_args
        }
        # Apply the overrides. Any value explicitly passed will replace the one from
        # fwg_params; arguments left as None keep the value of fwg_params, if any.
        final_fwg_params.update({key: value for key, value in overrides.items() if value is not None})
        for key in overrides:
            final_fwg_params.setdefault(key, None)
        if final_fwg_params.get(self.model_arg_name) is not None:
            final_fwg_params[self.model_arg_name] = _as_list(final_fwg_params[self.model_arg_name])
        # Parameters set in neither place take the defaults of pyfwg, so that all of
        # them are available for the command line and the filename placeholders.
        for key, default_value in _FWG_PARAM_DEFAULTS.items():
            if final_fwg_params.get(key) is None:
                final_fwg_params[key] = default_value
        # Convert the values to the types expected by the tool (e.g., 14.0 read from
        # Excel -> 14, or 'False' -> False). Invalid values are rejected below.
        _normalize_param_types(final_fwg_params)

        # --- 1b. Resolve FWG Version ---
        # If the version wasn't explicitly provided, try to detect it from the JAR path.
        if final_fwg_params.get('fwg_version') is None:
            try:
                # We use fwg_jar_path which is passed to the method
                detected_version = detect_fwg_version(fwg_jar_path)
                final_fwg_params['fwg_version'] = detected_version
                logger.info(f"Auto-detected FWG version: {detected_version}")
            except ValueError as e:
                logger.error(f"Version detection failed: {e}")
                # We can't safely proceed without a version
                final_fwg_params['fwg_version'] = '3' # Safe fallback for validation if needed, but we mark as invalid
                self.is_config_valid = False
            except Exception as e:
                logger.error(f"Unexpected error during version detection: {e}")
                final_fwg_params['fwg_version'] = '3'
                self.is_config_valid = False

        # Ensure version is stored as a string for consistency
        if final_fwg_params.get('fwg_version'):
            final_fwg_params['fwg_version'] = str(final_fwg_params['fwg_version'])

        # --- 1c. Resolve the command-line style of the tool ---
        try:
            self.cli_style = get_fwg_cli_style(final_fwg_params['fwg_version'], self.fwg_tool or 'global')
        except ValueError as e:
            logger.error(f"Version check failed: {e}")
            self.cli_style = FWG_CLI_POSITIONAL
            self.is_config_valid = False
        self._check_jar_matches_workflow(fwg_jar_path, final_fwg_params['fwg_version'])

        if self.cli_style == FWG_CLI_ENGINE:
            self._prepare_engine_params(fwg_jar_path, final_fwg_params)
        elif final_fwg_params.get('add_uhi') is None:
            # Older versions of the tool apply the UHI effect by default.
            final_fwg_params['add_uhi'] = True

        # Validate the final set of parameters and store the result in the instance's state.
        # We only set it if it hasn't been set to False by version detection failure.
        validation_result = self._validate_fwg_params(final_fwg_params)
        if hasattr(self, 'is_config_valid'):
            self.is_config_valid = self.is_config_valid and validation_result
        else:
            self.is_config_valid = validation_result

        # Create a user-friendly version for review, filling in defaults if needed.
        requested_models = final_fwg_params.get(self.model_arg_name)
        review_params = final_fwg_params.copy()
        if review_params.get(self.model_arg_name) is None:
            ensemble_models = (self.distribution_info or {}).get('ensemble_models')
            review_params[self.model_arg_name] = list(ensemble_models) if ensemble_models else sorted(self.valid_models)

        if not review_params.get('create_ensemble', True) and len(review_params[self.model_arg_name]) > 1:
            logger.warning(
                "With 'fwg_create_ensemble=False', the tool generates one file per model for each scenario and "
                "year, but they share the same output filename. Only the first file of each name will be kept; "
                "run one model per workflow (e.g., with MorphingIterator) to keep all of them.")

        # Create a version formatted specifically for the command line.
        formatted_params = {
            'models': ",".join(review_params[self.model_arg_name]),
            'ensemble': '1' if review_params.get('create_ensemble', True) else '0',
            'sd_shift': f"{review_params.get('winter_sd_shift', 0.0)}:{review_params.get('summer_sd_shift', 0.0)}",
            'month_transition_hours': str(review_params.get('month_transition_hours', 72)),
            'do_multithred_computation': 'true' if review_params.get('use_multithreading', True) else 'false',
            'interpolation_method_id': str(review_params.get('interpolation_method_id', 0)),
            'do_limit_variables': 'true' if review_params.get('limit_variables', True) else 'false',
            'solar_hour_adjustment_option': str(review_params.get('solar_hour_adjustment', 1)),
            'diffuse_irradiation_model_option': str(review_params.get('diffuse_irradiation_model', 1)),
            'uhi_combined': f"{'1' if review_params.get('add_uhi', True) else '0'}:{review_params.get('epw_original_lcz', 14)}:{review_params.get('target_uhi_lcz', 1)}"
        }

        # Determine the final list of files to be processed.
        files_to_process = list(self.epw_categories.keys())
        if run_incomplete_files:
            files_to_process.extend(self.incomplete_epw_categories.keys())
        self.epws_to_be_morphed = files_to_process

        # Store all settings in the instance's central 'inputs' dictionary.
        self.inputs.update({
            'final_output_dir': final_output_dir,
            'output_filename_pattern': output_filename_pattern,
            'scenario_mapping': scenario_mapping or {},
            'fwg_jar_path': fwg_jar_path,
            'run_incomplete_files': run_incomplete_files,
            'delete_temp_files': delete_temp_files,
            'temp_base_dir': temp_base_dir,
            'show_tool_output': fwg_show_tool_output,
            'fwg_params': review_params,
            'fwg_params_formatted': formatted_params,
            'fwg_cli_style': self.cli_style,
            # The models explicitly requested by the user (None means the tool's default).
            'fwg_requested_models': requested_models
        })

        # --- 2. Generate and Display Rename Plan ---
        # Reset the rename plan to ensure the method is rerunnable.
        self.rename_plan = {}
        # Combine complete and incomplete files to provide a full preview.
        all_mapped_files = {**self.epw_categories, **self.incomplete_epw_categories}

        # Validate that the pattern contains the required dynamic placeholders.
        required_placeholder = f"{{{self.scenario_placeholder_name}}}"
        if required_placeholder not in output_filename_pattern or '{year}' not in output_filename_pattern:
            raise ValueError(f"The 'output_filename_pattern' must contain both '{required_placeholder}' and '{{year}}'.")

        # The FWG Engine can generate a subset of the scenarios and future periods.
        planned_scenarios = review_params.get('scenarios') or list(self.tool_scenarios)
        planned_years = review_params.get('timeframes') or (
            list(self.available_timeframes) if self.cli_style == FWG_CLI_ENGINE else list(ALL_POSSIBLE_YEARS))

        # Print the configuration summary and preview header.
        print("\n" + "=" * 60 + "\n          MORPHING CONFIGURATION & PREVIEW\n" + "=" * 60)
        if not self.is_config_valid:
            print("!!! WARNING: Configuration has invalid parameters. See the log messages above (if they are not "
                  "shown, call pyfwg.enable_console_logging()). Execution will be blocked. !!!\n")

        print(f"  - FWG JAR Path: {self.inputs['fwg_jar_path']}")
        print(f"  - Final Output Directory: {os.path.abspath(self.inputs['final_output_dir'])}")
        print(f"  - EPWs to be Morphed ({len(self.epws_to_be_morphed)} files):")
        for epw in self.epws_to_be_morphed:
            print(f"    - {os.path.basename(epw)}")

        # Create a dictionary for filename formatting where keys have the 'fwg_' prefix.
        # This uses the final, resolved parameters (including defaults).
        fwg_placeholders = {f'fwg_{key}': value for key, value in self.inputs['fwg_params'].items()}
        # Rename the generic 'models' key to the specific argument name (fwg_gcms or fwg_rcm_pairs).
        fwg_placeholders[f"fwg_{self.model_arg_name}"] = fwg_placeholders.pop(f"fwg_{self.model_arg_name}")

        # Print the detailed rename plan for each file.
        for epw_path, mapped_data in all_mapped_files.items():
            is_incomplete = epw_path in self.incomplete_epw_categories
            status_flag = " [INCOMPLETE MAPPING]" if is_incomplete else ""
            print(f"\n  For input file: {os.path.basename(epw_path)}{status_flag}")

            # Combine all available data sources for formatting the filename.
            # This includes categories from the filename and all FWG parameters.
            filename_data_template = {
                **mapped_data,
                **fwg_placeholders,  # Use the new dictionary with 'fwg_' prefixes
                'year': None,  # Placeholder for the loop
                self.scenario_placeholder_name: None  # Placeholder for the loop
            }

            # Validate that all placeholders in the pattern can be filled.
            all_placeholders = set(re.findall(r'{(.*?)}', output_filename_pattern))
            missing_keys = all_placeholders - set(filename_data_template.keys())
            if missing_keys:
                print(f"    -> ERROR: This file is missing required data for the output pattern: {list(missing_keys)}. Renaming will fail.")
                continue

            # If validation passes, initialize the plan for this file.
            self.rename_plan[epw_path] = {}
            for year in planned_years:
                for scenario in planned_scenarios:
                    # Create the final data dictionary for this specific output file.
                    filename_data = filename_data_template.copy()
                    filename_data.update({
                        'scenario': scenario,
                        self.scenario_placeholder_name: self.inputs['scenario_mapping'].get(scenario, scenario),
                        'year': year
                    })

                    # Generate the final filename.
                    new_base_name = output_filename_pattern.format(**filename_data)
                    final_epw_path = os.path.join(final_output_dir, new_base_name + ".epw")

                    # The key for the plan is the raw filename the tool creates.
                    generated_file_key = f"{scenario}_{year}.epw"

                    # Populate the plan.
                    self.rename_plan[epw_path][generated_file_key] = final_epw_path
                    print(f"    -> Generated '{generated_file_key}' will be moved to: {os.path.abspath(final_epw_path)}")

        print("=" * 60 + "\nConfiguration set. Call execute_morphing() to start the process.")

    def execute_morphing(self):
        """STEP 3: Executes the morphing process if the configuration is valid.

        This method is the final action in the workflow and takes no arguments.
        It relies entirely on the state and configuration set by the previous
        `configure_and_preview` step.

        It includes a critical pre-flight check: before processing each file,
        it automatically validates the specified Local Climate Zones (LCZs) if
        the Urban Heat Island (UHI) feature is enabled. If the validation fails
        for a file, it is skipped with a detailed error message, and the workflow
        continues with the next file.

        Raises:
            RuntimeError: If `configure_and_preview()` has not been run first, or
                if the configuration was found to be invalid during that step.
        """
        # --- Guard Clauses ---
        # Ensure the configuration has been set before proceeding.
        if 'fwg_params' not in self.inputs:
            raise RuntimeError("Configuration has not been set. Please run configure_and_preview() first.")
        # Block execution if the configuration was found to be invalid during the setup step.
        if not self.is_config_valid:
            raise RuntimeError("Morphing configuration is invalid. Please correct the errors reported during configure_and_preview() and run it again.")

        logger.info("--- Step 4: Executing morphing workflow ---")

        # Create the final output and temporary base directories if they don't exist.
        os.makedirs(self.inputs['final_output_dir'], exist_ok=True)
        os.makedirs(self.inputs['temp_base_dir'], exist_ok=True)

        # Iterate through the definitive list of files to be processed,
        # which was determined during the set_morphing_config step.
        for epw_path in self.epws_to_be_morphed:
            # A final check to ensure a valid rename plan exists for this file.
            if epw_path not in self.rename_plan:
                logger.warning(f"Skipping '{os.path.basename(epw_path)}' as it had errors during the preview stage.")
                continue

            # --- Pre-flight check: Validate LCZ availability ---
            # This check is only performed if the user has enabled the UHI feature.
            fwg_params = self.inputs['fwg_params']
            if fwg_params.get('add_uhi', False):
                logger.info(f"Validating LCZ availability for {os.path.basename(epw_path)}...")
                # Call the utility function to perform the check using the configured parameters.
                lcz_validation_result = check_lcz_availability(
                    epw_path=epw_path,
                    original_lcz=fwg_params.get('epw_original_lcz'),
                    target_lcz=fwg_params.get('target_uhi_lcz'),
                    fwg_jar_path=self.inputs['fwg_jar_path'],

                    java_class_path_prefix=self.java_class_path_prefix,
                    fwg_version=fwg_params.get('fwg_version')
                )

                # If validation fails (returns anything other than True), log the error and skip this file.
                if lcz_validation_result is not True:
                    logger.error(f"LCZ validation failed for '{os.path.basename(epw_path)}'. This file will be skipped.")
                    # If the function returned a dictionary, it contains the detailed error messages.
                    if isinstance(lcz_validation_result, dict):
                        # Print the specific error messages (e.g., "The original LCZ '1' is not available.").
                        for error_message in lcz_validation_result.get("invalid_messages", []):
                            logger.error(error_message)
                        # Print the list of available LCZs for the user's convenience.
                        logger.error("The following LCZs are available for this location:")
                        for lcz in lcz_validation_result.get("available", []):
                            logger.error(f"- {lcz}")
                    continue  # Skip to the next EPW file in the loop.

            # --- Morphing Execution ---
            # If validation passes (or was skipped), proceed with the morphing.
            # Create a unique temporary subdirectory for this specific EPW file.
            temp_epw_output_dir = os.path.join(self.inputs['temp_base_dir'], os.path.splitext(os.path.basename(epw_path))[0])
            os.makedirs(temp_epw_output_dir, exist_ok=True)

            # Call the private helper method to run the external tool.
            success = self._execute_single_morph(epw_path, temp_epw_output_dir)

            # If the morphing was successful, process the output files.
            if success:
                self._process_generated_files(epw_path, temp_epw_output_dir)
                # Check the instance's state to decide whether to clean up.
                if self.inputs.get('delete_temp_files', False):
                    logger.info(f"Deleting temporary directory: {temp_epw_output_dir}")
                    _robust_rmtree(temp_epw_output_dir)

        logger.info("Morphing workflow finished.")

    def _current_cli_style(self) -> str:
        """(Private) Returns the command-line style of the configured tool."""
        cli_style = self.inputs.get('fwg_cli_style') or self.cli_style
        if cli_style:
            return cli_style
        version = (self.inputs.get('fwg_params') or {}).get('fwg_version') or '3'
        return get_fwg_cli_style(version, self.fwg_tool or 'global')

    def _execute_single_morph(self, epw_path: str, temp_output_dir: str) -> bool:
        """(Private) Executes the external Java tool for a single EPW file.

        This helper method performs several key tasks:
        1. Copies the source EPW file into its dedicated temporary directory.
        2. Constructs the actual command using the path to the temporary copy.
        3. Constructs a "display" version of the command for user-friendly logging.
        4. Runs the `java` command using `subprocess.run`.
        5. Manages console output and handles errors.

        Args:
            epw_path (str): The absolute path to the source EPW file.
            temp_output_dir (str): The path to the dedicated temporary directory
                for this EPW file's output.

        Returns:
            bool: True if the subprocess completed successfully, False otherwise.
        """
        try:
            temp_epw_path = os.path.join(temp_output_dir, os.path.basename(epw_path))
            shutil.copy2(epw_path, temp_epw_path)
            logger.info(f"Copied input file to temporary directory: {temp_epw_path}")

            # --- Sanitization Step ---
            # Some date-time libraries (like java.time in FWG) fail when encountering minute 60.
            # We sanitize the temporary copy of the EPW file to use minute 0 instead.
            sanitize_epw_minutes(temp_epw_path)
            # -------------------------
        except Exception as e:
            logger.error(f"Failed to copy EPW to temporary directory: {e}")
            return False

        formatted_params = self.inputs['fwg_params_formatted']

        # Each generation of the tool uses a different command line:
        # - Positional arguments: Global v3 / Europe v1.
        # - Key-value pairs: Global v4 / Europe v2.
        # - FWG Engine (key-value pairs and the '-g' action): Global v5+, Europe v3+, CORDEX regional.
        cli_style = self._current_cli_style()
        if cli_style == FWG_CLI_ENGINE:
            command = self._build_command_engine(epw_path, temp_epw_path, temp_output_dir)
        elif cli_style == FWG_CLI_KEY_VALUE:
            command = self._build_command_new_cli(epw_path, temp_epw_path, temp_output_dir)
        else:
            command = self._build_command_v3(epw_path, temp_epw_path, temp_output_dir, formatted_params)

        # Build a separate, "printable" version for logging.
        if cli_style == FWG_CLI_POSITIONAL:
            display_command_list = command[:]
            # For the legacy CLI, the EPW path is at index 4
            display_command_list[4] = os.path.abspath(epw_path)
        else:
            # For the key-value CLIs, the EPW path is within the -epw= argument
            display_command_list = [f'-epw={os.path.abspath(epw_path)}' if arg.startswith('-epw=') else arg
                                    for arg in command]

        printable_command = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in display_command_list)

        print("\n" + "-" * 20, f"Executing FWG for {os.path.basename(epw_path)}", "-" * 20)
        print("  Full Command (for reference):", printable_command)

        show_output = self.inputs.get('show_tool_output', False)
        stdout_dest = None if show_output else subprocess.PIPE
        stderr_dest = None if show_output else subprocess.PIPE

        if show_output:
            print("  --- FWG Real-time Output ---")

        try:
            subprocess.run(command, text=True, check=True, timeout=_TOOL_TIMEOUT_SECONDS.get(cli_style, 600),
                           stdout=stdout_dest, stderr=stderr_dest)
            if show_output:
                print("  --- End of FWG Output ---")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error morphing {os.path.basename(epw_path)}:")
            if e.stdout: logger.error(f"STDOUT:\n{e.stdout}")
            if e.stderr: logger.error(f"STDERR:\n{e.stderr}")
            return False
        except subprocess.TimeoutExpired as e:
            logger.error(f"Error morphing {os.path.basename(epw_path)}: the tool did not finish within {e.timeout} seconds.")
            return False

    def _build_command_v3(self, original_epw_path: str, temp_epw_path: str, temp_output_dir: str, formatted_params: Dict[str, str]) -> List[str]:
        """(Private) Constructs the legacy Java command (v3.x / Europe v1.x)."""
        class_path = f"{self.java_class_path_prefix}.Morph"
        command = [
            'java', '-cp', self.inputs['fwg_jar_path'], class_path,
            os.path.abspath(temp_epw_path),
            formatted_params['models'],
            formatted_params['ensemble'],
            formatted_params['sd_shift'],
            formatted_params['month_transition_hours'],
            os.path.abspath(temp_output_dir) + '/',
            formatted_params['do_multithred_computation'],
            formatted_params['interpolation_method_id'],
            formatted_params['do_limit_variables'],
            formatted_params['solar_hour_adjustment_option'],
            formatted_params['diffuse_irradiation_model_option'],
            formatted_params['uhi_combined']
        ]
        return command

    def _build_command_new_cli(self, original_epw_path: str, temp_epw_path: str, temp_output_dir: str) -> List[str]:
        """(Private) Constructs the FWG CLI command using key-value pairs (Global v4.x / Europe v2.x)."""
        params = self.inputs['fwg_params']

        # --- Map Integer Enums to String Values for new CLI tools ---
        # The user can now provide either the legacy integer ID or the V4 string directly.

        # Interpolation Method: {0: 'IDW', 1: 'BI', 2: 'AVG4P', 3: 'NP'}
        grid_interp = _option_from_id(params.get('interpolation_method_id'), _LEGACY_INTERPOLATION_METHODS, 'IDW')

        # Solar Correction: {0: 'None', 1: 'By_Month', 2: 'By_Day'}
        solar_corr = _option_from_id(params.get('solar_hour_adjustment'), _LEGACY_SOLAR_HOUR_ADJUSTMENTS, 'By_Month')

        # Diffuse Method: {0: 'Ridley_Boland_Lauret_2010', 1: 'Engerer_2015', 2: 'Paulescu_Blaga_2019'}
        diffuse_method = _option_from_id(params.get('diffuse_irradiation_model'), _LEGACY_DIFFUSE_MODELS, 'Engerer_2015')

        # Models List
        models = params.get(self.model_arg_name, [])
        models_str = ",".join(models) if isinstance(models, list) else str(models)

        # UHI String: true:orig:target or false
        if _cli_flag(params.get('add_uhi'), True) == 'true':
            uhi_val = f"true:{params.get('epw_original_lcz', 14)}:{params.get('target_uhi_lcz', 1)}"
        else:
            uhi_val = "false"

        # Construct the CLI arguments
        command = [
            'java', '-jar', self.inputs['fwg_jar_path'],
            f'-epw={os.path.abspath(temp_epw_path)}',
            f'-output_folder={os.path.abspath(temp_output_dir)}{os.sep}', # Ensure trailing slash if tool needs it
            f'-models={models_str}',
            f'-ensemble={_cli_flag(params.get("create_ensemble"), True)}',
            f'-temp_shift_winter={params.get("winter_sd_shift", 0.0)}',
            f'-temp_shift_summer={params.get("summer_sd_shift", 0.0)}',
            f'-smooth_hours={params.get("month_transition_hours", 72)}',
            f'-multithread={_cli_flag(params.get("use_multithreading"), True)}',
            f'-grid_interpolation_method={grid_interp}',
            f'-epw_dictionary_limits={_cli_flag(params.get("limit_variables"), True)}',
            f'-solar_correction={solar_corr}',
            f'-diffuse_method={diffuse_method}',
            f'-uhi={uhi_val}',
            f'-output_type={params.get("output_type", "EPW")}'
        ]
        command += self._extra_args_options(params)

        return command

    def _build_command_engine(self, original_epw_path: str, temp_epw_path: str, temp_output_dir: str) -> List[str]:
        """(Private) Constructs the command of the FWG Engine (Global v5+, Europe v3+, CORDEX regional).

        Options left as None are omitted, so that the defaults of the tool apply.
        The output layout is always 'ORGANIZED', which writes the weather files
        to the 'weather' subfolder of the output folder.
        """
        params = self.inputs['fwg_params']

        def flag(key: str, default: bool) -> str:
            return _cli_flag(params.get(key), default)

        command = [
            'java', '-jar', self.inputs['fwg_jar_path'],
            '-g',  # Action: generate future weather files.
            f'-epw={os.path.abspath(temp_epw_path)}',
            f'-output_folder={os.path.abspath(temp_output_dir)}{os.sep}',
            '-output_layout=ORGANIZED',
        ]

        # Without an explicit list, the tool uses all its ensemble-eligible models.
        requested_models = self.inputs.get('fwg_requested_models')
        if requested_models:
            command.append(f'-models={",".join(requested_models)}')

        command += [
            f'-ensemble={flag("create_ensemble", True)}',
            f'-temp_shift_winter={params.get("winter_sd_shift", 0.0)}',
            f'-temp_shift_summer={params.get("summer_sd_shift", 0.0)}',
            # The engine requires an integer number of hours.
            f'-smooth_hours={int(float(params.get("month_transition_hours", 72)))}',
            f'-multithread={flag("use_multithreading", True)}',
            f'-grid_interpolation_method={_engine_interpolation_token(params.get("interpolation_method_id", 0)) or "IDW"}',
            f'-epw_dictionary_limits={flag("limit_variables", True)}',
            f'-output_type={params.get("output_type") or "EPW"}',
        ]

        # Optional FWG Engine options.
        model_unzipped_folder = params.get('model_unzipped_folder')
        optional_options = {
            'scenarios': params.get('scenarios'),
            'timeframes': params.get('timeframes'),
            'decomposition_method': params.get('decomposition_method'),
            'illuminance_method': params.get('illuminance_method'),
            'infrared_method': params.get('infrared_method'),
            'morphing_method': params.get('morphing_method'),
            'uncertainty_variant': params.get('uncertainty_variant'),
            'uncertainty_sigma': params.get('uncertainty_sigma'),
            'output_profile': params.get('output_profile'),
            'model_unzipped_folder': os.path.abspath(model_unzipped_folder) if model_unzipped_folder else None,
        }
        normalized_options = {'decomposition_method', 'illuminance_method', 'infrared_method', 'morphing_method',
                              'uncertainty_variant', 'output_profile'}
        for option, value in optional_options.items():
            if value is None:
                continue
            if option in normalized_options:
                value = _normalize_option(value)
            command.append(f'-{option}={_format_cli_value(value)}')

        command += self._extra_args_options(params)
        return command

    @staticmethod
    def _extra_args_options(params: Dict[str, Any]) -> List[str]:
        """(Private) Formats the options of `fwg_extra_args` as '-key=value' arguments."""
        extra_args = params.get('extra_args') or {}
        return [f"-{str(key).lstrip('-')}={_format_cli_value(value)}" for key, value in extra_args.items()]

    def _process_generated_files(self, source_epw_path: str, temp_dir: str):
        """(Private) Moves and renames the generated weather files and their .stat files.

        This helper method iterates through the files generated in a temporary
        directory after a successful morphing run (for FWG Engine
        distributions, its 'weather' subfolder). It looks for the weather files
        of the selected output type (.epw, .met or .csv) and their .stat files,
        and matches them against the `rename_plan`.

        Auxiliary files (reports, logs, etc.) and the original source EPW are
        ignored and remain in the temporary directory.

        Args:
            source_epw_path (str): The path to the original source EPW file,
                used to look up the correct renaming plan.
            temp_dir (str): The temporary directory containing the generated files.
        """
        search_dir = _generated_files_dir(temp_dir, self._current_cli_style())
        logger.info(f"Processing generated files in: {search_dir}")
        if not os.path.isdir(search_dir):
            logger.warning(f"No generated files were found in '{search_dir}'.")
            return

        plan_for_this_epw = self.rename_plan.get(source_epw_path, {})
        allowed_extensions = _weather_file_extensions(self.inputs.get('fwg_params', {}).get('output_type'))
        moved_destinations = set()

        for generated_file in sorted(os.listdir(search_dir)):
            if generated_file == os.path.basename(source_epw_path):
                continue

            _, ext = os.path.splitext(generated_file)
            if ext.lower() not in allowed_extensions:
                # Special mention for Analysis Files/Folders in V4 Global and V2 Europe
                if generated_file.startswith(('00_', '01_', '02_', '03_', '04_')):
                    logger.info(f"Analysis file/folder detected: '{generated_file}'. It will remain in the temporary directory.")
                else:
                    logger.info(f"Skipping auxiliary file: '{generated_file}'")
                continue

            destination_path = None
            for expected_key, final_epw_path in plan_for_this_epw.items():
                # Check if the generated filename (without extension) matches the expected key
                # expected_key is usually "Model_Scenario_Year"
                if os.path.splitext(expected_key)[0] in generated_file:
                    # Construct destination path:
                    # Take the planned final EPW path (which ends in .epw), strip extension,
                    # and append the ACTUAL extension of the generated file.
                    # This handles .epw, .stat, .met, .csv dynamically.
                    base_dest_path = os.path.splitext(final_epw_path)[0]
                    destination_path = base_dest_path + ext
                    break

            if destination_path is None:
                if any(scenario in generated_file for scenario in self.tool_scenarios):
                    logger.warning(f"Could not find a rename plan for file '{generated_file}'. It will be left in the temp directory.")
                else:
                    # E.g., the present-day control or the corrected baseline of the FWG Engine.
                    logger.info(f"'{generated_file}' is not a future scenario file. It will be left in the temp directory.")
            elif destination_path in moved_destinations:
                logger.warning(f"Another generated file was already moved to '{destination_path}'. "
                                f"'{generated_file}' will be left in the temp directory.")
            else:
                source_path = os.path.join(search_dir, generated_file)
                logger.info(f"Moving '{source_path}' to '{destination_path}'")
                shutil.move(source_path, destination_path)
                moved_destinations.add(destination_path)

class MorphingWorkflowGlobal(_MorphingWorkflowBase):
    """Manages the morphing workflow for the GLOBAL Future Weather Generator tool.

    This class inherits all the step-by-step logic from the base workflow
    and is pre-configured to work specifically with the global climate models
    (GCMs) and SSP scenarios.

    It supports Global v3.x, v4.x and the FWG Engine distribution
    'FWG CMIP6 Global' (v5+). The version is detected from the JAR file.

    The intended usage is to follow the three-step process:

    1. `map_categories()`: Analyze input filenames to extract categories.
    2. `configure_and_preview()`: Define and validate all execution parameters
       and preview the results.
    3. `execute_morphing()`: Run the final computation.

    This class is ideal for advanced use cases that require custom file renaming
    and detailed control over the morphing process for global climate data.

    Attributes:
        inputs (Dict[str, Any]): A dictionary that stores all user-provided
            configuration from every step of the workflow. It serves as the
            central "memory" for the instance.
        epw_categories (Dict[str, Dict[str, str]]): A dictionary mapping the
            absolute path of each *successfully and completely* categorized EPW
            file to a dictionary of its categories.
        incomplete_epw_categories (Dict[str, Dict[str, str]]): Similar to
            `epw_categories`, but stores files that were mapped but are missing
            one or more expected categories based on the `keyword_mapping` rules.
        epws_to_be_morphed (List[str]): The definitive list of absolute EPW file
            paths that will be processed when `execute_morphing()` is called.
        rename_plan (Dict[str, Dict[str, str]]): A detailed mapping that outlines
            the renaming and moving operations for each generated file.
        is_config_valid (bool): A boolean flag that is set to `True` only if all
            parameters provided in `configure_and_preview` pass the internal
            validation checks.
    """
    # These override the empty attributes from the base class.
    tool_scenarios = GLOBAL_SCENARIOS
    valid_models = DEFAULT_GLOBAL_GCMS
    model_arg_name = 'gcms'
    java_class_path_prefix = 'futureweathergenerator'
    scenario_placeholder_name = 'ssp'
    fwg_tool = 'global'

    # def __init__(self):
    #     """Initializes the workflow for the GLOBAL tool.
    #
    #     This sets up the base class with the correct constants for global
    #     morphing, including the list of valid GCMs and the SSP scenarios
    #     that the tool will generate.
    #     """
    #     # Call the parent constructor with the specific constants for the global tool.
    #     super().__init__(
    #         tool_scenarios=GLOBAL_SCENARIOS,
    #         valid_models=DEFAULT_GLOBAL_GCMS,
    #         model_arg_name='gcms',  # The command-line argument for models is 'gcms'.
    #         java_class_path_prefix='futureweathergenerator',
    #         scenario_placeholder_name='ssp'
    #     )

    def configure_and_preview(self, *,
                              final_output_dir: str,
                              output_filename_pattern: str,
                              scenario_mapping: Optional[Dict[str, str]] = None,
                              fwg_jar_path: str,
                              run_incomplete_files: bool = False,
                              delete_temp_files: bool = True,
                              temp_base_dir: str = './morphing_temp_results',
                              fwg_show_tool_output: bool = False,
                              fwg_params: Optional[Dict[str, Any]] = None,
                              # --- Explicit Global Tool Arguments ---
                              fwg_gcms: Optional[List[str]] = None,
                              fwg_create_ensemble: Optional[bool] = None,
                              fwg_winter_sd_shift: Optional[float] = None,
                              fwg_summer_sd_shift: Optional[float] = None,
                              fwg_month_transition_hours: Optional[int] = None,
                              fwg_use_multithreading: Optional[bool] = None,
                              fwg_interpolation_method_id: Optional[Union[int, str]] = None,
                              fwg_limit_variables: Optional[bool] = None,
                              fwg_solar_hour_adjustment: Optional[Union[int, str]] = None,
                              fwg_diffuse_irradiation_model: Optional[Union[int, str]] = None,
                              fwg_add_uhi: Optional[bool] = None,
                              fwg_epw_original_lcz: Optional[int] = None,
                              fwg_target_uhi_lcz: Optional[int] = None,
                              fwg_output_type: Optional[str] = None,
                              fwg_version: Optional[Union[str, int]] = None,
                              # --- FWG Engine Arguments (Global v5+) ---
                              fwg_scenarios: Optional[List[str]] = None,
                              fwg_timeframes: Optional[List[Union[int, str]]] = None,
                              fwg_decomposition_method: Optional[str] = None,
                              fwg_illuminance_method: Optional[str] = None,
                              fwg_infrared_method: Optional[str] = None,
                              fwg_morphing_method: Optional[str] = None,
                              fwg_uncertainty_variant: Optional[str] = None,
                              fwg_uncertainty_sigma: Optional[float] = None,
                              fwg_output_profile: Optional[str] = None,
                              fwg_model_unzipped_folder: Optional[str] = None,
                              fwg_extra_args: Optional[Dict[str, Any]] = None):
        """STEP 2: Configures, validates, and previews the plan for the GLOBAL tool.

        This method combines configuration and preview into a single, robust step.
        It gathers all parameters for the morphing execution, validates them
        against the known constraints for the global tool, and then generates a
        detailed "dry run" plan of the final filenames for user review.

        The `output_filename_pattern` can now include placeholders for any FWG
        parameter (e.g., `{fwg_interpolation_method_id}`).

        The explicit `fwg_` arguments default to None, which means that they are
        not set: the value in `fwg_params` is used if present and, otherwise, the
        default given below. Only the arguments that are passed override
        `fwg_params`. Values such as 14.0 or 'False' (e.g., read from Excel) are
        converted to the expected type (14 or False).

        The arguments of the FWG Engine (Global v5+) default to None, which
        keeps the default of the tool. They cannot be used with v3.x or v4.x.

        Args:
            final_output_dir (str): The path for the final output files.
            output_filename_pattern (str): The template for final filenames.
                Must contain `{ssp}` and `{year}`.
            scenario_mapping (Optional[Dict[str, str]], optional): Mapping for
                scenario names. Defaults to None.
            fwg_jar_path (str): Path to the `FutureWeatherGenerator.jar` file.
            run_incomplete_files (bool, optional): If True, also processes
                partially categorized files. Defaults to False.
            delete_temp_files (bool, optional): If True, deletes temporary
                folders after processing. Defaults to True.
            temp_base_dir (str, optional): Base directory for temporary files.
                Defaults to './morphing_temp_results'.
            fwg_show_tool_output (bool, optional): If True, prints the FWG
                tool's console output in real-time. Defaults to False.
            fwg_params (Optional[Dict[str, Any]], optional): A dictionary for
                base FWG parameters, with keys without the `fwg_` prefix (e.g.,
                {'winter_sd_shift': 1.0, 'gcms': ['CanESM5']}). Any explicit
                `fwg_` argument that is passed will override this. Defaults to None.
            fwg_gcms (Optional[List[str]], optional): A specific list of GCMs
                to use. If None, the full default list is used.
            fwg_create_ensemble (Optional[bool], optional): If True, creates an
                ensemble. Defaults to True.
            fwg_winter_sd_shift (Optional[float], optional): Winter standard
                deviation shift. Defaults to 0.0.
            fwg_summer_sd_shift (Optional[float], optional): Summer standard
                deviation shift. Defaults to 0.0.
            fwg_month_transition_hours (Optional[int], optional): Hours for month
                transition. Defaults to 72.
            fwg_use_multithreading (Optional[bool], optional): Use multithreading.
                Defaults to True.
            fwg_interpolation_method_id (Optional[Union[int, str]], optional):
                Interpolation method ID or name. Defaults to 0 ('IDW'). Global
                v5+ also accepts 4/'SCI', 5/'SGBI' and 6/'STBI'.
            fwg_limit_variables (Optional[bool], optional): Limit variables to
                physical bounds. Defaults to True.
            fwg_solar_hour_adjustment (Optional[Union[int, str]], optional): Solar
                hour adjustment option. Defaults to 1 ('By_Month'). Ignored by Global v5+.
            fwg_diffuse_irradiation_model (Optional[Union[int, str]], optional):
                Diffuse irradiation model option. Defaults to 1 ('Engerer_2015').
                For Global v5+, use `fwg_decomposition_method` instead.
            fwg_add_uhi (Optional[bool], optional): Add UHI effect. If None, it is
                applied with v3.x and v4.x. Global v5+ does not support UHI.
            fwg_epw_original_lcz (Optional[int], optional): Original EPW LCZ.
                Defaults to 14.
            fwg_target_uhi_lcz (Optional[int], optional): Target UHI LCZ.
                Defaults to 1.
            fwg_output_type (Optional[str], optional): Output format (e.g., 'EPW',
                'SPAIN_MET'). Defaults to 'EPW'.
            fwg_version (Optional[Union[str, int]], optional): Version of the tool.
                If None, it is detected from the JAR.
            fwg_scenarios (Optional[List[str]], optional): Subset of scenarios to
                generate (e.g., ['ssp245', 'ssp585']). Global v5+ only.
            fwg_timeframes (Optional[List[Union[int, str]]], optional): Subset of
                future periods to generate (e.g., [2050]). Global v5+ only.
            fwg_decomposition_method (Optional[str], optional): Solar decomposition
                model (e.g., 'MULTIMODEL_CONSTRAINED_ENSEMBLE'). Global v5+ only.
            fwg_illuminance_method (Optional[str], optional): 'PEREZ_1990' or
                'SOURCE_CALIBRATED_LUMINOUS_EFFICACY'. Global v5+ only.
            fwg_infrared_method (Optional[str], optional): 'FWG_CURRENT' or
                'CLARK_ALLEN_WALTON'. Global v5.2+ only.
            fwg_morphing_method (Optional[str], optional): 'CLASSIC_MONTHLY' or
                'DISTRIBUTION_AWARE' (experimental). Global v5+ only.
            fwg_uncertainty_variant (Optional[str], optional): Uncertainty case
                (e.g., 'CENTRAL', 'PLUS_ONE_SIGMA', 'WARM_DRY'). Global v5+ only.
            fwg_uncertainty_sigma (Optional[float], optional): Standard-deviation
                multiplier of the uncertainty case. Global v5+ only.
            fwg_output_profile (Optional[str], optional): Reports written by the
                tool: 'MINIMAL', 'STANDARD', 'FULL' or 'CUSTOM'. Global v5+ only.
            fwg_model_unzipped_folder (Optional[str], optional): Folder to cache
                the unzipped climate-model data across runs. Global v5+ only.
            fwg_extra_args (Optional[Dict[str, Any]], optional): Additional
                command-line options (e.g., {'threads': 4}). Global v4+ only.
        """
        # This method acts as a user-friendly, type-hinted interface.
        # It collects all the specific arguments and passes them down to the
        # generic base method for the actual logic.
        super()._configure_and_preview_base(
            # Pass the workflow-related arguments directly.
            final_output_dir=final_output_dir,
            output_filename_pattern=output_filename_pattern,
            scenario_mapping=scenario_mapping,
            fwg_jar_path=fwg_jar_path,
            run_incomplete_files=run_incomplete_files,
            delete_temp_files=delete_temp_files,
            temp_base_dir=temp_base_dir,
            fwg_show_tool_output=fwg_show_tool_output,
            fwg_params=fwg_params,

            # Pass the specific model argument ('fwg_gcms') as the generic 'fwg_models'
            # that the base method expects.
            fwg_models=fwg_gcms,

            # Pass all other common FWG parameters straight through.
            fwg_create_ensemble=fwg_create_ensemble,
            fwg_winter_sd_shift=fwg_winter_sd_shift,
            fwg_summer_sd_shift=fwg_summer_sd_shift,
            fwg_month_transition_hours=fwg_month_transition_hours,
            fwg_use_multithreading=fwg_use_multithreading,
            fwg_interpolation_method_id=fwg_interpolation_method_id,
            fwg_limit_variables=fwg_limit_variables,
            fwg_solar_hour_adjustment=fwg_solar_hour_adjustment,
            fwg_diffuse_irradiation_model=fwg_diffuse_irradiation_model,
            fwg_add_uhi=fwg_add_uhi,
            fwg_epw_original_lcz=fwg_epw_original_lcz,
            fwg_target_uhi_lcz=fwg_target_uhi_lcz,
            fwg_output_type=fwg_output_type,
            fwg_version=fwg_version,
            fwg_scenarios=fwg_scenarios,
            fwg_timeframes=fwg_timeframes,
            fwg_decomposition_method=fwg_decomposition_method,
            fwg_illuminance_method=fwg_illuminance_method,
            fwg_infrared_method=fwg_infrared_method,
            fwg_morphing_method=fwg_morphing_method,
            fwg_uncertainty_variant=fwg_uncertainty_variant,
            fwg_uncertainty_sigma=fwg_uncertainty_sigma,
            fwg_output_profile=fwg_output_profile,
            fwg_model_unzipped_folder=fwg_model_unzipped_folder,
            fwg_extra_args=fwg_extra_args
        )

class MorphingWorkflowEurope(_MorphingWorkflowBase):
    """Manages the morphing workflow for the EUROPE-specific Future Weather Generator tool.

    This class inherits all the step-by-step logic from the base workflow
    and is pre-configured to work specifically with the European GCM-RCM model
    pairs and RCP scenarios.

    It supports Europe v1.x, v2.x and the FWG Engine distribution
    'FWG CORDEX-CMIP5 Europe (EUR-11)' (v3+). The version is detected from the
    JAR file.

    The intended usage is to follow the three-step process:

    1. `map_categories()`: Analyze input filenames to extract categories.
    2. `configure_and_preview()`: Define and validate all execution parameters
       and preview the results.
    3. `execute_morphing()`: Run the final computation.

    This class is ideal for advanced use cases that require custom file renaming
    and detailed control over the morphing process for European climate data.

    Attributes:
        inputs (Dict[str, Any]): A dictionary that stores all user-provided
            configuration from every step of the workflow. It serves as the
            central "memory" for the instance.
        epw_categories (Dict[str, Dict[str, str]]): A dictionary mapping the
            absolute path of each *successfully and completely* categorized EPW
            file to a dictionary of its categories.
        incomplete_epw_categories (Dict[str, Dict[str, str]]): Similar to
            `epw_categories`, but stores files that were mapped but are missing
            one or more expected categories based on the `keyword_mapping` rules.
        epws_to_be_morphed (List[str]): The definitive list of absolute EPW file
            paths that will be processed when `execute_morphing()` is called.
        rename_plan (Dict[str, Dict[str, str]]): A detailed mapping that outlines
            the renaming and moving operations for each generated file.
        is_config_valid (bool): A boolean flag that is set to `True` only if all
            parameters provided in `configure_and_preview` pass the internal
            validation checks.
    """

    tool_scenarios = EUROPE_SCENARIOS
    valid_models = DEFAULT_EUROPE_RCMS
    model_arg_name = 'rcm_pairs'
    java_class_path_prefix = 'futureweathergenerator_europe'
    scenario_placeholder_name = 'rcp'
    fwg_tool = 'europe'

    # def __init__(self):
    #     """Initializes the workflow for the EUROPE tool.
    #
    #     This sets up the base class with the correct constants for European
    #     morphing, including the list of valid GCM-RCM pairs and the RCP
    #     scenarios that the tool will generate.
    #     """
    #     # Call the parent constructor with the specific constants for the Europe tool.
    #     super().__init__(
    #         tool_scenarios=EUROPE_SCENARIOS,
    #         valid_models=DEFAULT_EUROPE_RCMS,
    #         model_arg_name='rcm_pairs',  # The command-line argument for models is 'rcm_pairs'.
    #         java_class_path_prefix='futureweathergenerator_europe',
    #         scenario_placeholder_name='rcp'
    #     )

    def configure_and_preview(self, *,
                              final_output_dir: str,
                              output_filename_pattern: str,
                              scenario_mapping: Optional[Dict[str, str]] = None,
                              fwg_jar_path: str,
                              run_incomplete_files: bool = False,
                              delete_temp_files: bool = True,
                              temp_base_dir: str = './morphing_temp_results_europe',
                              fwg_show_tool_output: bool = False,
                              fwg_params: Optional[Dict[str, Any]] = None,
                              # --- Explicit Europe Tool Arguments ---
                              fwg_rcm_pairs: Optional[List[str]] = None,
                              fwg_create_ensemble: Optional[bool] = None,
                              fwg_winter_sd_shift: Optional[float] = None,
                              fwg_summer_sd_shift: Optional[float] = None,
                              fwg_month_transition_hours: Optional[int] = None,
                              fwg_use_multithreading: Optional[bool] = None,
                              fwg_interpolation_method_id: Optional[Union[int, str]] = None,
                              fwg_limit_variables: Optional[bool] = None,
                              fwg_solar_hour_adjustment: Optional[Union[int, str]] = None,
                              fwg_diffuse_irradiation_model: Optional[Union[int, str]] = None,
                              fwg_add_uhi: Optional[bool] = None,
                              fwg_epw_original_lcz: Optional[int] = None,
                              fwg_target_uhi_lcz: Optional[int] = None,
                              fwg_output_type: Optional[str] = None,
                              fwg_version: Optional[Union[str, int]] = None,
                              # --- FWG Engine Arguments (Europe v3+) ---
                              fwg_scenarios: Optional[List[str]] = None,
                              fwg_timeframes: Optional[List[Union[int, str]]] = None,
                              fwg_decomposition_method: Optional[str] = None,
                              fwg_illuminance_method: Optional[str] = None,
                              fwg_infrared_method: Optional[str] = None,
                              fwg_morphing_method: Optional[str] = None,
                              fwg_uncertainty_variant: Optional[str] = None,
                              fwg_uncertainty_sigma: Optional[float] = None,
                              fwg_output_profile: Optional[str] = None,
                              fwg_model_unzipped_folder: Optional[str] = None,
                              fwg_extra_args: Optional[Dict[str, Any]] = None):
        """STEP 2: Configures, validates, and previews the plan for the EUROPE tool.

        This method combines configuration and preview into a single, robust step.
        It gathers all parameters for the morphing execution, validates them
        against the known constraints for the Europe-specific tool, and then
        generates a detailed "dry run" plan of the final filenames for user review.

        The `output_filename_pattern` can now include placeholders for any FWG
        parameter (e.g., `{fwg_interpolation_method_id}`).

        The explicit `fwg_` arguments default to None, which means that they are
        not set: the value in `fwg_params` is used if present and, otherwise, the
        default given below. Only the arguments that are passed override
        `fwg_params`.

        The arguments of the FWG Engine (Europe v3+) default to None, which
        keeps the default of the tool. They cannot be used with v1.x or v2.x.

        Args:
            final_output_dir (str): The path for the final output files.
            output_filename_pattern (str): The template for final filenames.
                Must contain `{rcp}` and `{year}`.
            scenario_mapping (Optional[Dict[str, str]], optional): Mapping for
                scenario names (e.g., {'rcp26': 'RCP-2.6'}). Defaults to None.
            fwg_jar_path (str): Path to the `FutureWeatherGenerator_Europe.jar` file.
            run_incomplete_files (bool, optional): If True, also processes
                partially categorized files. Defaults to False.
            delete_temp_files (bool, optional): If True, deletes temporary
                folders after processing. Defaults to True.
            temp_base_dir (str, optional): Base directory for temporary files.
                Defaults to './morphing_temp_results_europe'.
            fwg_show_tool_output (bool, optional): If True, prints the FWG
                tool's console output in real-time. Defaults to False.
            fwg_params (Optional[Dict[str, Any]], optional): A dictionary for
                base FWG parameters, with keys without the `fwg_` prefix (e.g.,
                {'winter_sd_shift': 1.0, 'rcm_pairs': [...]}). Any explicit
                `fwg_` argument that is passed will override this. Defaults to None.
            fwg_rcm_pairs (Optional[List[str]], optional): A specific list of
                GCM-RCM pairs to use. If None, the full default list is used.
            fwg_create_ensemble (Optional[bool], optional): If True, creates an
                ensemble. Defaults to True.
            fwg_winter_sd_shift (Optional[float], optional): Winter standard
                deviation shift. Defaults to 0.0.
            fwg_summer_sd_shift (Optional[float], optional): Summer standard
                deviation shift. Defaults to 0.0.
            fwg_month_transition_hours (Optional[int], optional): Hours for month
                transition. Defaults to 72.
            fwg_use_multithreading (Optional[bool], optional): Use multithreading.
                Defaults to True.
            fwg_interpolation_method_id (Optional[Union[int, str]], optional):
                Interpolation method ID or name. Defaults to 0 ('IDW'). Europe
                v3+ also accepts 4/'SCI', 5/'SGBI' and 6/'STBI'.
            fwg_limit_variables (Optional[bool], optional): Limit variables to
                physical bounds. Defaults to True.
            fwg_solar_hour_adjustment (Optional[Union[int, str]], optional): Solar
                hour adjustment option. Defaults to 1 ('By_Month'). Ignored by Europe v3+.
            fwg_diffuse_irradiation_model (Optional[Union[int, str]], optional):
                Diffuse irradiation model option. Defaults to 1 ('Engerer_2015').
                For Europe v3+, use `fwg_decomposition_method` instead.
            fwg_add_uhi (Optional[bool], optional): Add UHI effect. If None, it is
                applied with v1.x and v2.x. Europe v3+ does not support UHI.
            fwg_epw_original_lcz (Optional[int], optional): Original EPW LCZ.
                Defaults to 14.
            fwg_target_uhi_lcz (Optional[int], optional): Target UHI LCZ.
                Defaults to 1.
            fwg_output_type (Optional[str], optional): Output format (e.g., 'EPW',
                'SPAIN_MET'). Defaults to 'EPW'.
            fwg_version (Optional[Union[str, int]], optional): Version of the tool.
                If None, it is detected from the JAR.
            (The FWG Engine arguments `fwg_scenarios` to `fwg_extra_args` are
            explained in the `MorphingWorkflowGlobal.configure_and_preview`
            docstring; scenarios are RCPs, e.g., ['rcp45', 'rcp85']).
        """
        # This method acts as a user-friendly, type-hinted interface for the Europe tool.
        # It collects all the specific arguments and passes them down to the
        # generic base method for the actual logic.
        super()._configure_and_preview_base(
            # Pass the workflow-related arguments directly.
            final_output_dir=final_output_dir,
            output_filename_pattern=output_filename_pattern,
            scenario_mapping=scenario_mapping,
            fwg_jar_path=fwg_jar_path,
            run_incomplete_files=run_incomplete_files,
            delete_temp_files=delete_temp_files,
            temp_base_dir=temp_base_dir,
            fwg_show_tool_output=fwg_show_tool_output,
            fwg_params=fwg_params,

            # Pass the specific model argument ('fwg_rcm_pairs') as the generic 'fwg_models'
            # that the base method expects.
            fwg_models=fwg_rcm_pairs,

            # Pass all other common FWG parameters straight through.
            fwg_create_ensemble=fwg_create_ensemble,
            fwg_winter_sd_shift=fwg_winter_sd_shift,
            fwg_summer_sd_shift=fwg_summer_sd_shift,
            fwg_month_transition_hours=fwg_month_transition_hours,
            fwg_use_multithreading=fwg_use_multithreading,
            fwg_interpolation_method_id=fwg_interpolation_method_id,
            fwg_limit_variables=fwg_limit_variables,
            fwg_solar_hour_adjustment=fwg_solar_hour_adjustment,
            fwg_diffuse_irradiation_model=fwg_diffuse_irradiation_model,
            fwg_add_uhi=fwg_add_uhi,
            fwg_epw_original_lcz=fwg_epw_original_lcz,
            fwg_target_uhi_lcz=fwg_target_uhi_lcz,
            fwg_output_type=fwg_output_type,
            fwg_version=fwg_version,
            fwg_scenarios=fwg_scenarios,
            fwg_timeframes=fwg_timeframes,
            fwg_decomposition_method=fwg_decomposition_method,
            fwg_illuminance_method=fwg_illuminance_method,
            fwg_infrared_method=fwg_infrared_method,
            fwg_morphing_method=fwg_morphing_method,
            fwg_uncertainty_variant=fwg_uncertainty_variant,
            fwg_uncertainty_sigma=fwg_uncertainty_sigma,
            fwg_output_profile=fwg_output_profile,
            fwg_model_unzipped_folder=fwg_model_unzipped_folder,
            fwg_extra_args=fwg_extra_args
        )

class MorphingWorkflowCordex(_MorphingWorkflowBase):
    """Manages the morphing workflow for the CORDEX regional Future Weather Generator tools.

    This class works with the regional distributions released on the FWG
    Engine, which use GCM-RCM model pairs and RCP scenarios:
    Middle East and North Africa (MNA-22), Africa (AFR-22), North America
    (NAM-44), Central America (CAM-44), South America (SAM-44), West & South
    Asia (WAS-22), Southeast Asia (SEA-22) and Australasia (AUS-22). It also
    accepts the Europe (EUR-11) distribution v3+.

    The region is identified from the JAR file (its packaged distribution
    manifest or, otherwise, its filename), and the available scenarios and
    GCM-RCM pairs are taken from it (see `pyfwg.CORDEX_REGIONS`). For example,
    the Middle East and North Africa distribution only provides 'rcp85'.

    The Urban Heat Island (UHI) effect is not available in these
    distributions, so this class has no UHI arguments.

    The intended usage is to follow the three-step process:

    1. `map_categories()`: Analyze input filenames to extract categories.
    2. `configure_and_preview()`: Define and validate all execution parameters
       and preview the results.
    3. `execute_morphing()`: Run the final computation.

    Attributes:
        inputs (Dict[str, Any]): A dictionary that stores all user-provided
            configuration from every step of the workflow. It serves as the
            central "memory" for the instance.
        epw_categories (Dict[str, Dict[str, str]]): A dictionary mapping the
            absolute path of each *successfully and completely* categorized EPW
            file to a dictionary of its categories.
        incomplete_epw_categories (Dict[str, Dict[str, str]]): Similar to
            `epw_categories`, but stores files that were mapped but are missing
            one or more expected categories based on the `keyword_mapping` rules.
        epws_to_be_morphed (List[str]): The definitive list of absolute EPW file
            paths that will be processed when `execute_morphing()` is called.
        rename_plan (Dict[str, Dict[str, str]]): A detailed mapping that outlines
            the renaming and moving operations for each generated file.
        is_config_valid (bool): A boolean flag that is set to `True` only if all
            parameters provided in `configure_and_preview` pass the internal
            validation checks.
        cordex_domain (Optional[str]): The CORDEX domain of the configured JAR
            (e.g., 'NAM-44'), or None if it could not be identified.
    """

    # Class-level values cover all regions; they are narrowed to the region of
    # the JAR in `configure_and_preview`.
    tool_scenarios = CORDEX_SCENARIOS
    valid_models = DEFAULT_CORDEX_RCMS
    model_arg_name = 'rcm_pairs'
    java_class_path_prefix = 'futureweathergenerator'
    scenario_placeholder_name = 'rcp'
    fwg_tool = 'cordex'

    def __init__(self):
        """Initializes the workflow for the CORDEX regional tools."""
        super().__init__()
        self.cordex_domain: Optional[str] = None

    def _engine_capabilities(self, fwg_jar_path: str,
                             distribution_info: Optional[Dict[str, Any]]) -> Tuple[List[str], set, List[int]]:
        """(Private) Returns the scenarios, models and future periods of the region of the JAR."""
        self.cordex_domain = _detect_cordex_domain(fwg_jar_path)
        if distribution_info:
            return super()._engine_capabilities(fwg_jar_path, distribution_info)
        if self.cordex_domain in CORDEX_REGIONS:
            region = CORDEX_REGIONS[self.cordex_domain]
            logger.info(f"CORDEX domain detected from the JAR filename: {self.cordex_domain} ({region['name']}).")
            return list(region['scenarios']), set(region['rcm_pairs']), list(ALL_POSSIBLE_YEARS)
        logger.warning(
            f"Could not identify the CORDEX domain of '{os.path.basename(fwg_jar_path)}'. Scenarios and GCM-RCM "
            f"pairs are validated against all regions; the tool will report any unavailable option.")
        return list(CORDEX_SCENARIOS), set(DEFAULT_CORDEX_RCMS), list(ALL_POSSIBLE_YEARS)

    def configure_and_preview(self, *,
                              final_output_dir: str,
                              output_filename_pattern: str,
                              scenario_mapping: Optional[Dict[str, str]] = None,
                              fwg_jar_path: str,
                              run_incomplete_files: bool = False,
                              delete_temp_files: bool = True,
                              temp_base_dir: str = './morphing_temp_results_cordex',
                              fwg_show_tool_output: bool = False,
                              fwg_params: Optional[Dict[str, Any]] = None,
                              # --- Explicit CORDEX Tool Arguments ---
                              fwg_rcm_pairs: Optional[List[str]] = None,
                              fwg_create_ensemble: Optional[bool] = None,
                              fwg_winter_sd_shift: Optional[float] = None,
                              fwg_summer_sd_shift: Optional[float] = None,
                              fwg_month_transition_hours: Optional[int] = None,
                              fwg_use_multithreading: Optional[bool] = None,
                              fwg_interpolation_method_id: Optional[Union[int, str]] = None,
                              fwg_limit_variables: Optional[bool] = None,
                              fwg_output_type: Optional[str] = None,
                              fwg_version: Optional[Union[str, int]] = None,
                              fwg_scenarios: Optional[List[str]] = None,
                              fwg_timeframes: Optional[List[Union[int, str]]] = None,
                              fwg_decomposition_method: Optional[str] = None,
                              fwg_illuminance_method: Optional[str] = None,
                              fwg_infrared_method: Optional[str] = None,
                              fwg_morphing_method: Optional[str] = None,
                              fwg_uncertainty_variant: Optional[str] = None,
                              fwg_uncertainty_sigma: Optional[float] = None,
                              fwg_output_profile: Optional[str] = None,
                              fwg_model_unzipped_folder: Optional[str] = None,
                              fwg_extra_args: Optional[Dict[str, Any]] = None):
        """STEP 2: Configures, validates, and previews the plan for a CORDEX regional tool.

        This method combines configuration and preview into a single, robust step.
        It gathers all parameters for the morphing execution, validates them
        against the scenarios and GCM-RCM pairs of the region of the JAR, and
        then generates a detailed "dry run" plan of the final filenames for user
        review. Only the scenarios available in the region are planned.

        Only FWG Engine distributions are accepted: the CORDEX regional
        distributions and Europe v3+. For Europe v1.x and v2.x, use
        `MorphingWorkflowEurope`.

        The explicit `fwg_` arguments default to None, which means that they are
        not set: the value in `fwg_params` is used if present and, otherwise, the
        default given below. Only the arguments that are passed override
        `fwg_params`.

        Args:
            final_output_dir (str): The path for the final output files.
            output_filename_pattern (str): The template for final filenames.
                Must contain `{rcp}` and `{year}`.
            scenario_mapping (Optional[Dict[str, str]], optional): Mapping for
                scenario names (e.g., {'rcp85': 'RCP-8.5'}). Defaults to None.
            fwg_jar_path (str): Path to the regional JAR file (e.g.,
                'FutureWeatherGenerator-CORDEX-CMIP5-North-America-NAM-44-v1.2.0.jar').
            run_incomplete_files (bool, optional): If True, also processes
                partially categorized files. Defaults to False.
            delete_temp_files (bool, optional): If True, deletes temporary
                folders after processing. Defaults to True.
            temp_base_dir (str, optional): Base directory for temporary files.
                Defaults to './morphing_temp_results_cordex'.
            fwg_show_tool_output (bool, optional): If True, prints the FWG
                tool's console output in real-time. Defaults to False.
            fwg_params (Optional[Dict[str, Any]], optional): A dictionary for
                base FWG parameters, with keys without the `fwg_` prefix (e.g.,
                {'winter_sd_shift': 1.0, 'rcm_pairs': [...]}). Any explicit
                `fwg_` argument that is passed will override this. Defaults to None.
            fwg_rcm_pairs (Optional[List[str]], optional): A specific list of
                GCM-RCM pairs of the region. If None, the tool uses all of them.
            fwg_create_ensemble (Optional[bool], optional): If True, creates an
                ensemble (it requires at least two GCM-RCM pairs). Defaults to True.
            fwg_winter_sd_shift (Optional[float], optional): Winter standard
                deviation shift. Defaults to 0.0.
            fwg_summer_sd_shift (Optional[float], optional): Summer standard
                deviation shift. Defaults to 0.0.
            fwg_month_transition_hours (Optional[int], optional): Hours for month
                transition. Defaults to 72.
            fwg_use_multithreading (Optional[bool], optional): Use multithreading.
                Defaults to True.
            fwg_interpolation_method_id (Optional[Union[int, str]], optional):
                Interpolation method ID or name (0/'IDW', 2/'AVG4P', 3/'NP',
                4/'SCI', 5/'SGBI', 6/'STBI'). Defaults to 0 ('IDW'). 'BI'
                requires rectilinear grids, which the CORDEX regions do not use.
            fwg_limit_variables (Optional[bool], optional): Limit variables to
                physical bounds. Defaults to True.
            fwg_output_type (Optional[str], optional): Output format (e.g., 'EPW',
                'SPAIN_MET'). Defaults to 'EPW'.
            fwg_version (Optional[Union[str, int]], optional): Version of the tool.
                If None, it is detected from the JAR.
            (The FWG Engine arguments `fwg_scenarios` to `fwg_extra_args` are
            explained in the `MorphingWorkflowGlobal.configure_and_preview`
            docstring; scenarios are RCPs, e.g., ['rcp85']).
        """
        super()._configure_and_preview_base(
            # Pass the workflow-related arguments directly.
            final_output_dir=final_output_dir,
            output_filename_pattern=output_filename_pattern,
            scenario_mapping=scenario_mapping,
            fwg_jar_path=fwg_jar_path,
            run_incomplete_files=run_incomplete_files,
            delete_temp_files=delete_temp_files,
            temp_base_dir=temp_base_dir,
            fwg_show_tool_output=fwg_show_tool_output,
            fwg_params=fwg_params,
            fwg_models=fwg_rcm_pairs,
            fwg_create_ensemble=fwg_create_ensemble,
            fwg_winter_sd_shift=fwg_winter_sd_shift,
            fwg_summer_sd_shift=fwg_summer_sd_shift,
            fwg_month_transition_hours=fwg_month_transition_hours,
            fwg_use_multithreading=fwg_use_multithreading,
            fwg_interpolation_method_id=fwg_interpolation_method_id,
            fwg_limit_variables=fwg_limit_variables,
            # Options of older tools that the FWG Engine does not use. Their values
            # in fwg_params (if any) are handled as in the other workflows.
            fwg_solar_hour_adjustment=None,
            fwg_diffuse_irradiation_model=None,
            fwg_add_uhi=None,
            fwg_epw_original_lcz=None,
            fwg_target_uhi_lcz=None,
            fwg_output_type=fwg_output_type,
            fwg_version=fwg_version,
            fwg_scenarios=fwg_scenarios,
            fwg_timeframes=fwg_timeframes,
            fwg_decomposition_method=fwg_decomposition_method,
            fwg_illuminance_method=fwg_illuminance_method,
            fwg_infrared_method=fwg_infrared_method,
            fwg_morphing_method=fwg_morphing_method,
            fwg_uncertainty_variant=fwg_uncertainty_variant,
            fwg_uncertainty_sigma=fwg_uncertainty_sigma,
            fwg_output_profile=fwg_output_profile,
            fwg_model_unzipped_folder=fwg_model_unzipped_folder,
            fwg_extra_args=fwg_extra_args
        )
