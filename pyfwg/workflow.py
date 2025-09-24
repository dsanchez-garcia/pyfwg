# pyfwg/workflow.py

import os
import re
import shutil
import subprocess
import logging
from typing import List, Optional, Dict, Any, Union

# Import the functions from the utils.py file
from .utils import check_lcz_availability, _robust_rmtree

# Import constants from the local constants.py file
from .constants import (
    ALL_POSSIBLE_YEARS,
    DEFAULT_GLOBAL_GCMS, GLOBAL_SCENARIOS,
    DEFAULT_EUROPE_RCMS, EUROPE_SCENARIOS
)


class _MorphingWorkflowBase:
    """(Private) Base class containing the shared logic for all morphing workflows.

    This class is not intended to be instantiated directly by the user. Instead,
    it serves as a foundation for specialized child classes like
    `MorphingWorkflowGlobal` and `MorphingWorkflowEurope`.

    It implements the entire state machine logic (map, configure & preview,
    execute) in a generic way, relying on configuration provided by the
    child classes' class attributes.
    """

    # --- Define attributes at the class level ---
    # These are now class attributes, accessible without creating an instance.
    tool_scenarios: List[str] = []
    valid_models: set = set()
    model_arg_name: str = ""
    java_class_path_prefix: str = ""
    scenario_placeholder_name: str = ""

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
        logging.info("--- Step 1: Mapping categories from filenames ---")

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
                logging.warning(f"EPW file not found, skipping: {epw_path}")
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
                    logging.warning(f"Pattern did not match '{epw_base_name}'. Skipping.")
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
                logging.info(f"Mapped '{epw_path}': {file_categories}")

                # In keyword-only mode, check for completeness.
                if keyword_mapping and not input_filename_pattern:
                    all_defined_categories = set(keyword_mapping.keys())
                    found_categories = set(file_categories.keys())

                    # If not all categories were found, classify the file as incomplete.
                    if len(found_categories) < len(all_defined_categories):
                        missing = all_defined_categories - found_categories
                        logging.warning(f"File '{os.path.basename(epw_path)}' is missing categories: {list(missing)}.")
                        self.incomplete_epw_categories[epw_path] = file_categories
                    else:
                        # The file is complete.
                        self.epw_categories[epw_path] = file_categories
                else:
                    # In pattern mode, we assume the pattern defines completeness.
                    self.epw_categories[epw_path] = file_categories
            else:
                # If no categories could be mapped, warn the user.
                logging.warning(f"Could not map any categories for '{epw_path}'. Skipping.")

        logging.info("Category mapping complete.")


    def _validate_fwg_params(self, params: Dict[str, Any]) -> bool:
        """(Private) Validates the final FWG parameters against known constraints.

        This helper method is called by `configure_and_preview` to ensure that the
        parameters provided by the user are valid before attempting to run the
        external tool. It uses the class attributes `self.model_arg_name` and
        `self.valid_models` to perform tool-specific validation.

        Args:
            params (Dict[str, Any]): A dictionary containing the final,
                user-friendly `fwg_` parameters after all overrides have been
                applied.

        Returns:
            bool: True if all parameters pass validation, False otherwise.
        """
        is_valid = True

        # Validate the models (GCMs or RCM pairs) using the instance's specific list.
        if params.get(self.model_arg_name):
            for model in params[self.model_arg_name]:
                if model not in self.valid_models:
                    logging.warning(f"Validation failed: Model '{model}' is not valid for this tool.")
                    is_valid = False

        # Validate float range parameters.
        if not -2.0 <= params.get('winter_sd_shift', 0.0) <= 2.0:
            logging.warning(f"Validation failed: 'fwg_winter_sd_shift' must be between -2.0 and 2.0.")
            is_valid = False
        if not -2.0 <= params.get('summer_sd_shift', 0.0) <= 2.0:
            logging.warning(f"Validation failed: 'fwg_summer_sd_shift' must be between -2.0 and 2.0.")
            is_valid = False

        # Validate integer range parameters.
        if not 0 <= params.get('month_transition_hours', 72) <= 336:
            logging.warning(f"Validation failed: 'fwg_month_transition_hours' must be between 0 and 336.")
            is_valid = False
        if not 1 <= params.get('epw_original_lcz', 1) <= 17:
            logging.warning(f"Validation failed: 'fwg_epw_original_lcz' must be between 1 and 17.")
            is_valid = False
        if not 1 <= params.get('target_uhi_lcz', 1) <= 17:
            logging.warning(f"Validation failed: 'fwg_target_uhi_lcz' must be between 1 and 17.")
            is_valid = False

        # Validate integer set parameters.
        validations = {
            'interpolation_method_id': {0, 1, 2},
            'solar_hour_adjustment': {0, 1, 2},
            'diffuse_irradiation_model': {0, 1, 2}
        }
        for param_name, valid_values in validations.items():
            if params.get(param_name) not in valid_values:
                logging.warning(f"Validation failed: '{param_name}' has value {params.get(param_name)}, but allowed values are {valid_values}.")
                is_valid = False

        return is_valid

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
                                    fwg_create_ensemble: bool,
                                    fwg_winter_sd_shift: float,
                                    fwg_summer_sd_shift: float,
                                    fwg_month_transition_hours: int,
                                    fwg_use_multithreading: bool,
                                    fwg_interpolation_method_id: int,
                                    fwg_limit_variables: bool,
                                    fwg_solar_hour_adjustment: int,
                                    fwg_diffuse_irradiation_model: int,
                                    fwg_add_uhi: bool,
                                    fwg_epw_original_lcz: int,
                                    fwg_target_uhi_lcz: int):
        """(Private) Base method for configuring, validating, and previewing the plan.

        This method is the core of the combined Step 2. It is called by the
        public-facing `configure_and_preview` methods of the child classes.

        It performs three main tasks:
        1.  **Configuration**: It merges the base `fwg_params` dictionary with
            any explicit `fwg_` keyword arguments, with the latter taking
            precedence.
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

        logging.info("--- Step 2: Configuring and Previewing Morphing Plan ---")

        # --- 1. Build and Validate Configuration ---
        # Start with the base dictionary, or an empty one if not provided.
        final_fwg_params = fwg_params.copy() if fwg_params else {}

        # Create a dictionary of all explicit keyword arguments. This captures both
        # user-provided values and the default values for any omitted arguments,
        # ensuring all parameters are available for filename placeholders.
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
            'target_uhi_lcz': fwg_target_uhi_lcz
        }
        # Apply the overrides. Any value explicitly passed will replace the one from fwg_params.
        final_fwg_params.update(overrides)

        # Validate the final set of parameters and store the result in the instance's state.
        self.is_config_valid = self._validate_fwg_params(final_fwg_params)

        # Create a user-friendly version for review, filling in defaults if needed.
        review_params = final_fwg_params.copy()
        if review_params.get(self.model_arg_name) is None:
            review_params[self.model_arg_name] = list(self.valid_models)

        # Create a version formatted specifically for the command line.
        formatted_params = {
            'models': ",".join(review_params[self.model_arg_name]),
            'ensemble': '1' if review_params.get('create_ensemble', True) else '0',
            'sd_shift': f"{review_params.get('winter_sd_shift', 0.0)}:{review_params.get('summer_sd_shift', 0.0)}",
            'month_transition_hours': str(review_params.get('month_transition_hours', 72)),
            'do_multithred_computation': str(review_params.get('use_multithreading', True)).lower(),
            'interpolation_method_id': str(review_params.get('interpolation_method_id', 0)),
            'do_limit_variables': str(review_params.get('limit_variables', True)).lower(),
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
            'fwg_params_formatted': formatted_params
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

        # Print the configuration summary and preview header.
        print("\n" + "=" * 60 + "\n          MORPHING CONFIGURATION & PREVIEW\n" + "=" * 60)
        if not self.is_config_valid:
            print("!!! WARNING: Configuration has invalid parameters. See logs above. Execution will be blocked. !!!\n")

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
            for year in ALL_POSSIBLE_YEARS:
                for scenario in self.tool_scenarios:
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
            raise RuntimeError("Configuration has not been set. Please run set_morphing_config() first.")
        # Block execution if the configuration was found to be invalid during the setup step.
        if not self.is_config_valid:
            raise RuntimeError("Morphing configuration is invalid. Please correct the errors reported during set_morphing_config() and run it again.")

        logging.info("--- Step 4: Executing morphing workflow ---")

        # Create the final output and temporary base directories if they don't exist.
        os.makedirs(self.inputs['final_output_dir'], exist_ok=True)
        os.makedirs(self.inputs['temp_base_dir'], exist_ok=True)

        # Iterate through the definitive list of files to be processed,
        # which was determined during the set_morphing_config step.
        for epw_path in self.epws_to_be_morphed:
            # A final check to ensure a valid rename plan exists for this file.
            if epw_path not in self.rename_plan:
                logging.warning(f"Skipping '{os.path.basename(epw_path)}' as it had errors during the preview stage.")
                continue

            # --- Pre-flight check: Validate LCZ availability ---
            # This check is only performed if the user has enabled the UHI feature.
            fwg_params = self.inputs['fwg_params']
            if fwg_params.get('add_uhi', False):
                logging.info(f"Validating LCZ availability for {os.path.basename(epw_path)}...")
                # Call the utility function to perform the check using the configured parameters.
                lcz_validation_result = check_lcz_availability(
                    epw_path=epw_path,
                    original_lcz=fwg_params.get('epw_original_lcz'),
                    target_lcz=fwg_params.get('target_uhi_lcz'),
                    fwg_jar_path=self.inputs['fwg_jar_path'],
                    java_class_path_prefix=self.java_class_path_prefix
                )

                # If validation fails (returns anything other than True), log the error and skip this file.
                if lcz_validation_result is not True:
                    logging.error(f"LCZ validation failed for '{os.path.basename(epw_path)}'. This file will be skipped.")
                    # If the function returned a dictionary, it contains the detailed error messages.
                    if isinstance(lcz_validation_result, dict):
                        # Print the specific error messages (e.g., "The original LCZ '1' is not available.").
                        for error_message in lcz_validation_result.get("invalid_messages", []):
                            logging.error(error_message)
                        # Print the list of available LCZs for the user's convenience.
                        logging.error("The following LCZs are available for this location:")
                        for lcz in lcz_validation_result.get("available", []):
                            logging.error(f"- {lcz}")
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
                    logging.info(f"Deleting temporary directory: {temp_epw_output_dir}")
                    _robust_rmtree(temp_epw_output_dir)

        logging.info("Morphing workflow finished.")

    def _execute_single_morph(self, epw_path: str, temp_output_dir: str) -> bool:
        """(Private) Executes the external Java tool for a single EPW file.

        This helper method performs several key tasks:
        1. Copies the source EPW file into its dedicated temporary directory.
        2. Constructs the actual command using the path to the temporary copy.
        3. Constructs a "display" version of the command for user-friendly logging.
        4. Runs the `java -cp ...` command using `subprocess.run`.
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
            logging.info(f"Copied input file to temporary directory: {temp_epw_path}")
        except Exception as e:
            logging.error(f"Failed to copy EPW to temporary directory: {e}")
            return False

        formatted_params = self.inputs['fwg_params_formatted']

        # Build the command for actual execution.
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

        # Build a separate, "printable" version for logging.
        display_command_list = command[:]
        display_command_list[4] = os.path.abspath(epw_path)
        printable_command = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in display_command_list)

        print("\n" + "-" * 20, f"Executing FWG for {os.path.basename(epw_path)}", "-" * 20)
        print("  Full Command (for reference):", printable_command)

        show_output = self.inputs.get('show_tool_output', False)
        stdout_dest = None if show_output else subprocess.PIPE
        stderr_dest = None if show_output else subprocess.PIPE

        if show_output:
            print("  --- FWG Real-time Output ---")

        try:
            subprocess.run(command, text=True, check=True, timeout=600, stdout=stdout_dest, stderr=stderr_dest)
            if show_output:
                print("  --- End of FWG Output ---")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error morphing {os.path.basename(epw_path)}:")
            if e.stdout: logging.error(f"STDOUT:\n{e.stdout}")
            if e.stderr: logging.error(f"STDERR:\n{e.stderr}")
            return False

    def _process_generated_files(self, source_epw_path: str, temp_dir: str):
        """(Private) Moves and renames generated .epw and .stat files.

        This helper method iterates through all files in a temporary directory
        after a successful morphing run. It specifically looks for `.epw` and
        `.stat` files and matches them against the `rename_plan`.

        Auxiliary files (`.csv`, `.log`, etc.) and the original source EPW
        are ignored and left in the temporary directory for later cleanup.

        Args:
            source_epw_path (str): The path to the original source EPW file,
                used to look up the correct renaming plan.
            temp_dir (str): The temporary directory containing the generated files.
        """
        logging.info(f"Processing generated files in: {temp_dir}")

        plan_for_this_epw = self.rename_plan.get(source_epw_path, {})

        for generated_file in os.listdir(temp_dir):
            if generated_file == os.path.basename(source_epw_path):
                continue

            if not (generated_file.endswith(".epw") or generated_file.endswith(".stat")):
                logging.info(f"Skipping auxiliary file: '{generated_file}'")
                continue

            destination_path = None
            for expected_key, final_epw_path in plan_for_this_epw.items():
                if os.path.splitext(expected_key)[0] in generated_file:
                    if generated_file.endswith(".epw"):
                        destination_path = final_epw_path
                    elif generated_file.endswith(".stat"):
                        destination_path = os.path.splitext(final_epw_path)[0] + ".stat"
                    break

            if destination_path:
                source_path = os.path.join(temp_dir, generated_file)
                logging.info(f"Moving '{source_path}' to '{destination_path}'")
                shutil.move(source_path, destination_path)
            else:
                logging.warning(f"Could not find a rename plan for file '{generated_file}'. It will be left in the temp directory.")

class MorphingWorkflowGlobal(_MorphingWorkflowBase):
    """Manages the morphing workflow for the GLOBAL FutureWeatherGenerator tool.

    This class inherits all the step-by-step logic from the base workflow
    and is pre-configured to work specifically with the global climate models
    (GCMs) and SSP scenarios.

    The intended usage is to follow the three-step process:
    1. `map_categories()`: Analyze input filenames.
    2. `configure_and_preview()`: Define and validate all execution parameters.
    3. `execute_morphing()`: Run the final computation.
    """

    # These override the empty attributes from the base class.
    tool_scenarios = GLOBAL_SCENARIOS
    valid_models = DEFAULT_GLOBAL_GCMS
    model_arg_name = 'gcms'
    java_class_path_prefix = 'futureweathergenerator'
    scenario_placeholder_name = 'ssp'

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
                              fwg_create_ensemble: bool = True,
                              fwg_winter_sd_shift: float = 0.0,
                              fwg_summer_sd_shift: float = 0.0,
                              fwg_month_transition_hours: int = 72,
                              fwg_use_multithreading: bool = True,
                              fwg_interpolation_method_id: int = 0,
                              fwg_limit_variables: bool = True,
                              fwg_solar_hour_adjustment: int = 1,
                              fwg_diffuse_irradiation_model: int = 1,
                              fwg_add_uhi: bool = True,
                              fwg_epw_original_lcz: int = 14,
                              fwg_target_uhi_lcz: int = 1):
        """STEP 2: Configures, validates, and previews the plan for the GLOBAL tool.

        This method combines configuration and preview into a single, robust step.
        It gathers all parameters for the morphing execution, validates them
        against the known constraints for the global tool, and then generates a
        detailed "dry run" plan of the final filenames for user review.

        The `output_filename_pattern` can now include placeholders for any FWG
        parameter (e.g., `{fwg_interpolation_method_id}`).

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
                base FWG parameters. Any explicit `fwg_` argument will
                override this. Defaults to None.
            fwg_gcms (Optional[List[str]], optional): A specific list of GCMs
                to use. If None, the full default list is used.
            (All other `fwg_` arguments are self-explanatory and correspond to
            the FutureWeatherGenerator tool's options).
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
            fwg_target_uhi_lcz=fwg_target_uhi_lcz
        )

class MorphingWorkflowEurope(_MorphingWorkflowBase):
    """Manages the morphing workflow for the EUROPE-specific FutureWeatherGenerator tool.

    This class inherits all the step-by-step logic from the base workflow
    and is pre-configured to work specifically with the European GCM-RCM model
    pairs and RCP scenarios.

    The intended usage is to follow the four-step process:
    1. `map_categories()`: Analyze input filenames.
    2. `preview_rename_plan()`: Review the expected output.
    3. `set_morphing_config()`: Define and validate all execution parameters.
    4. `execute_morphing()`: Run the final computation.
    """

    tool_scenarios = EUROPE_SCENARIOS
    valid_models = DEFAULT_EUROPE_RCMS
    model_arg_name = 'rcm_pairs'
    java_class_path_prefix = 'futureweathergenerator_europe'
    scenario_placeholder_name = 'rcp'

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
                              fwg_create_ensemble: bool = True,
                              fwg_winter_sd_shift: float = 0.0,
                              fwg_summer_sd_shift: float = 0.0,
                              fwg_month_transition_hours: int = 72,
                              fwg_use_multithreading: bool = True,
                              fwg_interpolation_method_id: int = 0,
                              fwg_limit_variables: bool = True,
                              fwg_solar_hour_adjustment: int = 1,
                              fwg_diffuse_irradiation_model: int = 1,
                              fwg_add_uhi: bool = True,
                              fwg_epw_original_lcz: int = 14,
                              fwg_target_uhi_lcz: int = 1):
        """STEP 2: Configures, validates, and previews the plan for the EUROPE tool.

        This method combines configuration and preview into a single, robust step.
        The `output_filename_pattern` can now include placeholders for any FWG
        parameter (e.g., `{fwg_interpolation_method_id}`).

        Args:
            final_output_dir (str): The path for the final output files.
            output_filename_pattern (str): The template for final filenames.
                Must contain `{rcp}` and `{year}`.
            scenario_mapping (Optional[Dict[str, str]], optional): Mapping for
                scenario names. Defaults to None.
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
                base FWG parameters. Any explicit `fwg_` argument will
                override this. Defaults to None.
            fwg_rcm_pairs (Optional[List[str]], optional): A specific list of
                GCM-RCM pairs to use. If None, the full default list is used.
            (All other `fwg_` arguments are self-explanatory and correspond to
            the FutureWeatherGenerator tool's options).
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
            fwg_target_uhi_lcz=fwg_target_uhi_lcz
        )