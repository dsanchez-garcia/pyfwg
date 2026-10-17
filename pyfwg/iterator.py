# pyfwg/iterator.py
import os
import re

import pandas as pd
import inspect
import logging
from typing import Type, List, Dict, Any, Union, Optional

# Import the base class to use its type hint
from .workflow import _MorphingWorkflowBase

logger = logging.getLogger(__name__)

# Marker that represents a missing value when comparing the values of a column.
_MISSING = object()


def _is_missing(value: Any) -> bool:
    """(Private) Returns True for None and NaN-like scalars. Lists, dicts and other containers are never missing."""
    return value is None or (pd.api.types.is_scalar(value) and bool(pd.isna(value)))


def _comparable(value: Any) -> Any:
    """(Private) Returns a hashable version of a cell value (lists become tuples) to count distinct values."""
    if isinstance(value, (list, tuple)):
        return tuple(_comparable(item) for item in value)
    if _is_missing(value):
        return _MISSING
    return value

class MorphingIterator:
    """Automates running multiple morphing configurations from a structured input.

    This class is designed to perform parametric analysis by iterating over
    different sets of parameters for a given morphing workflow. It uses a
    Pandas DataFrame to define the different runs.

    The typical usage is a structured, multi-step process that provides
    clarity and control at each stage:

    **Step 1: Initialization**
        Instantiate the iterator with the desired workflow class.
        ```python
        iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)
        ```

    **Step 2: Define Common Parameters (Optional)**
        Use the `set_default_values()` method to define parameters that will be
        the same for all runs in the batch, such as `fwg_jar_path`.

    **Step 3: Define the Runs DataFrame**
        Create a DataFrame that specifies what changes between each run. This
        can be done in two ways:

        *   **A) Programmatically with Pandas:**
            Use `get_template_dataframe()` to get a blank template, then add
            rows for each run.
            ```python
            runs_df = iterator.get_template_dataframe()
            runs_df.loc[len(runs_df)] = {'epw_paths': 'file1.epw', 'fwg_gcms': ['CanESM5']}
            runs_df.loc[len(runs_df)] = {'epw_paths': 'file2.epw', 'fwg_gcms': ['MIROC6']}
            ```

        *   **B) Using an Excel Template:**
            Use the utility functions to export a template, edit it in Excel,
            and then load it back.
            ```python
            from pyfwg import export_template_to_excel, load_runs_from_excel
            export_template_to_excel(iterator, 'my_runs.xlsx')
            # (User edits the Excel file here)
            runs_df = load_runs_from_excel('my_runs.xlsx')
            ```

    **Step 4: Generate the Full Execution Plan**
        Call `generate_morphing_workflows()` with the DataFrame of runs. This
        method applies all defaults (from the class and from `set_default_values`),
        parses filenames, prepares all the underlying workflow instances, and
        stores the complete plan for review.

    **Step 5: Inspect and Verify (Optional)**
        Before running, you can inspect the `iterator.morphing_workflows_plan_df`
        DataFrame and the `iterator.prepared_workflows` list to ensure
        everything is configured as expected.

    **Step 6: Execute the Batch Run**
        Call `run_morphing_workflows()` to execute the entire batch of prepared
        simulations.

    Attributes:
        workflow_class (Type[_MorphingWorkflowBase]): The workflow class that
            will be used for each iteration.
        custom_defaults (Dict[str, Any]): A dictionary of default parameters
            set by the user via `set_default_values`.
        prepared_workflows (List[_MorphingWorkflowBase]): A list of fully
            configured, ready-to-run workflow instances. Populated by
            `generate_morphing_workflows`.
        morphing_workflows_plan_df (Optional[pd.DataFrame]): A detailed
            DataFrame showing the complete configuration for every run in the
            batch. Populated by `generate_morphing_workflows`.
    """
    def __init__(self, workflow_class: Type[_MorphingWorkflowBase]):
        """Initializes the iterator with a specific workflow class."""
        self.workflow_class = workflow_class
        self.custom_defaults: Dict[str, Any] = {}
        self.prepared_workflows: List[_MorphingWorkflowBase] = []
        self.morphing_workflows_plan_df: Optional[pd.DataFrame] = None
        logger.info(f"MorphingIterator initialized for {workflow_class.__name__}.")

    def set_default_values(self, *,
                           # --- All possible workflow and FWG arguments are listed here ---
                           final_output_dir: Optional[str] = None,
                           output_filename_pattern: Optional[str] = None,
                           scenario_mapping: Optional[Dict[str, str]] = None,
                           fwg_jar_path: Optional[str] = None,
                           run_incomplete_files: Optional[bool] = None,
                           delete_temp_files: Optional[bool] = None,
                           temp_base_dir: Optional[str] = None,
                           fwg_show_tool_output: Optional[bool] = None,
                           fwg_params: Optional[Dict[str, Any]] = None,
                           # --- Model-specific arguments ---
                           fwg_gcms: Optional[List[str]] = None,
                           fwg_rcm_pairs: Optional[List[str]] = None,
                           # --- Common FWG arguments ---
                           fwg_create_ensemble: Optional[bool] = None,
                           fwg_winter_sd_shift: Optional[float] = None,
                           fwg_summer_sd_shift: Optional[float] = None,
                           fwg_month_transition_hours: Optional[int] = None,
                           fwg_use_multithreading: Optional[bool] = None,
                           fwg_interpolation_method_id: Optional[int] = None,
                           fwg_limit_variables: Optional[bool] = None,
                           fwg_solar_hour_adjustment: Optional[int] = None,
                           fwg_diffuse_irradiation_model: Optional[int] = None,
                           fwg_add_uhi: Optional[bool] = None,
                           fwg_epw_original_lcz: Optional[int] = None,
                           fwg_target_uhi_lcz: Optional[int] = None,
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
        """Sets default parameter values for all runs in the batch.

        This method is a convenient way to define parameters that are common
        to all runs in a parametric study, such as `fwg_jar_path` or a shared
        `output_filename_pattern`.

        Any parameter set here will be used for every row in the DataFrame
        unless a different value is specified for that parameter in the row
        itself. This follows a clear priority order:
        1. (Lowest) Hardcoded defaults from the workflow class.
        2. (Medium) Defaults set with this method.
        3. (Highest) Values specified directly in the runs DataFrame.

        The method has an explicit signature for all possible arguments,
        providing auto-completion and type hints in your editor. It also
        includes a validation check to warn the user if they provide an
        argument that is not applicable to the chosen workflow (e.g., providing
        `fwg_rcm_pairs` for a `MorphingWorkflowGlobal` instance, or
        `fwg_add_uhi` for a `MorphingWorkflowCordex` instance).

        Args:
            * (keyword-only): All arguments must be specified by name.
            (All arguments are optional and correspond to the parameters of the
            workflow's `configure_and_preview` method).
        """
        # Manually collect all arguments passed to this method into a dictionary.
        provided_args = {
            'final_output_dir': final_output_dir, 'output_filename_pattern': output_filename_pattern,
            'scenario_mapping': scenario_mapping, 'fwg_jar_path': fwg_jar_path,
            'run_incomplete_files': run_incomplete_files, 'delete_temp_files': delete_temp_files,
            'temp_base_dir': temp_base_dir, 'fwg_show_tool_output': fwg_show_tool_output,
            'fwg_params': fwg_params, 'fwg_gcms': fwg_gcms, 'fwg_rcm_pairs': fwg_rcm_pairs,
            'fwg_create_ensemble': fwg_create_ensemble, 'fwg_winter_sd_shift': fwg_winter_sd_shift,
            'fwg_summer_sd_shift': fwg_summer_sd_shift, 'fwg_month_transition_hours': fwg_month_transition_hours,
            'fwg_use_multithreading': fwg_use_multithreading, 'fwg_interpolation_method_id': fwg_interpolation_method_id,
            'fwg_limit_variables': fwg_limit_variables, 'fwg_solar_hour_adjustment': fwg_solar_hour_adjustment,
            'fwg_diffuse_irradiation_model': fwg_diffuse_irradiation_model, 'fwg_add_uhi': fwg_add_uhi,
            'fwg_epw_original_lcz': fwg_epw_original_lcz, 'fwg_target_uhi_lcz': fwg_target_uhi_lcz,
            'fwg_output_type': fwg_output_type, 'fwg_version': fwg_version,
            'fwg_scenarios': fwg_scenarios, 'fwg_timeframes': fwg_timeframes,
            'fwg_decomposition_method': fwg_decomposition_method, 'fwg_illuminance_method': fwg_illuminance_method,
            'fwg_infrared_method': fwg_infrared_method, 'fwg_morphing_method': fwg_morphing_method,
            'fwg_uncertainty_variant': fwg_uncertainty_variant, 'fwg_uncertainty_sigma': fwg_uncertainty_sigma,
            'fwg_output_profile': fwg_output_profile, 'fwg_model_unzipped_folder': fwg_model_unzipped_folder,
            'fwg_extra_args': fwg_extra_args
        }

        # Filter out any arguments that were not provided (are None).
        self.custom_defaults = {key: value for key, value in provided_args.items() if value is not None}

        # --- Validation and Warning Logic ---
        # Arguments that the workflow's configuration method does not accept
        # (e.g., 'fwg_rcm_pairs' for MorphingWorkflowGlobal) are ignored.
        accepted_args = inspect.signature(self.workflow_class.configure_and_preview).parameters
        for inapplicable_arg in [key for key in self.custom_defaults if key not in accepted_args]:
            logger.warning(
                f"Argument '{inapplicable_arg}' is not applicable for "
                f"{self.workflow_class.__name__} and will be ignored."
            )
            # Remove the inapplicable argument so it's not used later.
            self.custom_defaults.pop(inapplicable_arg)

        logger.info(f"Custom default values have been set for the iterator: {self.custom_defaults}")

    def get_template_dataframe(self) -> pd.DataFrame:
        """Generates an empty Pandas DataFrame with the correct parameter columns.

        This helper method provides a convenient, error-proof template for the
        user to define their parametric runs.

        It works by dynamically inspecting the signature of the `configure_and_preview`
        method of the workflow class that was passed to the iterator's
        constructor (e.g., `MorphingWorkflowGlobal`). This ensures that the
        DataFrame columns perfectly match the required and optional arguments
        of the specific workflow, preventing typos and errors.

        The template also includes the essential columns for the iterator:
        `epw_paths`, `input_filename_pattern`, and `keyword_mapping`.

        Returns:
            pd.DataFrame: An empty Pandas DataFrame with columns corresponding
            to all the configurable parameters for a batch run.
        """
        # --- 1. Inspect the Workflow's Configuration Method ---
        # Get the signature object of the target method. This object contains
        # rich metadata about all of its parameters.
        sig = inspect.signature(self.workflow_class.configure_and_preview)

        # --- 2. Extract Parameter Names ---
        # Iterate through the parameters in the signature.
        # We only want keyword-only arguments, excluding 'self' and the generic
        # '**kwargs' collector if it existed.
        param_names = [
            p.name for p in sig.parameters.values()
            if p.name not in ('self', 'kwargs') and p.kind == p.KEYWORD_ONLY
        ]

        # --- 3. Construct the Final Column List ---
        # The final DataFrame should have the iterator-specific columns first,
        # followed by all the parameters from the workflow's config method.
        final_columns = ['epw_paths', 'input_filename_pattern', 'keyword_mapping'] + param_names

        # --- 4. Create and Return the Template ---
        # Create an empty DataFrame using the constructed list of column names.
        return pd.DataFrame(columns=final_columns)

    def _apply_defaults(self, runs_df: pd.DataFrame) -> pd.DataFrame:
        """(Private) Fills missing values and adds missing columns with defaults.

        This helper method is the core of the configuration logic. It takes a
        user-provided DataFrame (which may be sparse) and creates a complete,
        fully populated DataFrame ready for planning and execution.

        It operates with a clear priority order:
        1. (Lowest) Hardcoded defaults from the workflow class signature.
        2. (Medium) Custom defaults set by the user via `set_default_values`.
        3. (Highest) Values specified directly in the input `runs_df`.

        The method handles two main cases for each parameter:
        - If a column for a parameter does not exist in the input DataFrame,
          it is created and filled entirely with the final default value.
        - If a column exists but contains missing (NaN) values, only those
          missing values are filled with the final default value.

        Args:
            runs_df (pd.DataFrame): The user's DataFrame of runs, potentially
                with missing values or columns.

        Returns:
            pd.DataFrame: A new, fully populated DataFrame with all defaults applied.
        """
        # --- 1. Determine the Final Set of Default Values ---

        # Get the hardcoded default values from the workflow's method signature.
        sig = inspect.signature(self.workflow_class.configure_and_preview)
        hardcoded_defaults = {
            p.name: p.default
            for p in sig.parameters.values()
            if p.default is not inspect.Parameter.empty
        }

        # Create the final defaults dictionary by merging the two sources.
        # The custom_defaults (from set_default_values) will override the
        # hardcoded_defaults, establishing the correct priority.
        final_defaults = {**hardcoded_defaults, **self.custom_defaults}

        # Create a copy of the user's DataFrame to avoid modifying the original.
        completed_df = runs_df.copy()

        # --- 2. Apply Defaults to the DataFrame ---

        # Iterate through all available default parameters.
        for col, default_val in final_defaults.items():
            if col not in completed_df.columns:
                if default_val is not None:
                    # We wrap the default value in a list of the same length as the DataFrame
                    # to ensure that list or dictionary defaults are assigned to each row
                    # correctly without causing length mismatch errors.
                    completed_df[col] = [default_val] * len(completed_df)
            # Case 2: The column exists, but may have missing values.
            else:
                # Only proceed if there is a default value to fill with.
                if default_val is not None:
                    # Use the robust .apply() method to fill only the NaN values.
                    # This is safer than .fillna() for DataFrames with mixed
                    # data types (like lists) and avoids FutureWarning. Cells with
                    # lists or dicts are never considered missing.
                    completed_df[col] = completed_df[col].apply(
                        lambda x: default_val if _is_missing(x) else x
                    )

        # Return the fully populated DataFrame.
        return completed_df

    def generate_morphing_workflows(self,
                                    runs_df: pd.DataFrame,
                                    input_filename_pattern: Optional[str] = None,
                                    keyword_mapping: Optional[Dict] = None,
                                    raise_on_overwrite: bool = True):
        """Generates a detailed execution plan and prepares all workflow instances.

        This method is the core of the planning phase. It orchestrates the
        entire setup for a batch run by performing several key tasks:

        1.  **Applies Defaults**: It takes the user's (potentially sparse)
            DataFrame of runs and creates a complete, fully populated version
            by applying all default values from the class and from the
            `set_default_values` method.
        2.  **Maps Categories**: It performs a "dry run" of the file mapping for
            each run to extract categories from the EPW filenames.
        3.  **Enriches the Plan**: It adds new columns (`cat_*`) to the plan
            DataFrame, showing the extracted categories for each run.
        4.  **Prepares Workflows**: It instantiates and fully configures a
            `MorphingWorkflow` object for each run in the plan.
        5.  **Validates for Filename Overwrites**: It performs two layers of
            validation to prevent data loss: first by checking for parameters
            that vary between runs but are not in their output filename
            pattern, and then by comparing the final paths of all the files
            that the prepared workflows will write (output folder and filename
            of each input file, scenario and year) to detect any direct
            collision.
        6.  **Stores the Plan**: The final, validated DataFrame is stored in
            `self.morphing_workflows_plan_df` for user inspection, and the
            ready-to-run workflow instances in `self.prepared_workflows`.

        Parameters that a run does not set (empty cells, and no value in
        `set_default_values`) are not passed to its workflow, so the values of
        its `fwg_params` or the defaults of the workflow apply.

        Args:
            runs_df (pd.DataFrame): The user's DataFrame of runs. Each row
                represents a unique configuration to be executed.
            input_filename_pattern (Optional[str], optional): A regex pattern for
                filename mapping, applied as a default to *every* run unless
                overridden in the DataFrame. Defaults to None.
            keyword_mapping (Optional[Dict], optional): A dictionary of keyword
                rules for filename mapping, applied as a default to *every* run
                unless overridden in the DataFrame.
            raise_on_overwrite (bool, optional): If True (default), raises a
                ValueError if a definitive filename overwrite is detected in
                Layer 2 validation, and no workflows are prepared. Layer 1
                validation will always only warn.

        Raises:
            ValueError: If `raise_on_overwrite` is True and a definitive file
                overwrite is detected.
        """
        logger.info("Generating detailed execution plan and preparing workflows...")

        # Discard the results of any previous call, so that a failed call does not
        # leave workflows ready to run.
        self.prepared_workflows = []
        self.morphing_workflows_plan_df = None

        # --- Part 1: Generate the Detailed DataFrame Plan ---

        # First, apply all default values to get a complete parameter set for each run.
        plan_df = self._apply_defaults(runs_df)

        # If the user provided a static mapping strategy, ensure the corresponding
        # columns exist in the plan DataFrame for completeness.
        if 'input_filename_pattern' not in plan_df.columns or plan_df['input_filename_pattern'].isnull().all():
            plan_df['input_filename_pattern'] = input_filename_pattern
        if 'keyword_mapping' not in plan_df.columns or plan_df['keyword_mapping'].isnull().all():
            # Pandas requires lists/dicts to be wrapped when assigning to a column.
            plan_df['keyword_mapping'] = [keyword_mapping] * len(plan_df)

        # This list will store the dictionary of mapped categories for each run.
        extracted_categories_per_run = []
        # This set will collect all unique category keys found across all runs.
        all_category_keys = set()

        # Perform a dry run of the mapping for each run in the plan.
        for index, row in plan_df.iterrows():
            epw_paths = row.get('epw_paths')
            epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths

            # Determine the mapping strategy for this specific run.
            run_input_pattern = row.get('input_filename_pattern') if not _is_missing(row.get('input_filename_pattern')) else input_filename_pattern
            run_keyword_map = row.get('keyword_mapping') if not _is_missing(row.get('keyword_mapping')) else keyword_mapping

            # Create a temporary workflow instance just for mapping.
            temp_workflow = self.workflow_class()
            temp_workflow.map_categories(
                epw_files=epw_files,
                input_filename_pattern=run_input_pattern,
                keyword_mapping=run_keyword_map
            )
            # Store the combined dictionary of all mapped categories for this run.
            run_categories = {**temp_workflow.epw_categories, **temp_workflow.incomplete_epw_categories}
            extracted_categories_per_run.append(run_categories)
            # Keep track of all unique category keys found.
            for cat_dict in run_categories.values():
                all_category_keys.update(cat_dict.keys())

        # Add new 'cat_*' columns to the plan DataFrame.
        sorted_cat_keys = sorted(list(all_category_keys))
        for key in sorted_cat_keys:
            plan_df[f'cat_{key}'] = [
                # For each run, compile a list of unique values found for this category.
                list({cat_dict.get(key) for cat_dict in run_cats.values() if cat_dict.get(key)})
                for run_cats in extracted_categories_per_run
            ]

        # Reorder columns to place the new 'cat_*' columns in an intuitive position.
        original_cols = list(plan_df.columns)
        cat_cols = [f'cat_{key}' for key in sorted_cat_keys]
        try:
            insert_pos = original_cols.index('keyword_mapping') + 1
        except ValueError:
            try:
                insert_pos = original_cols.index('input_filename_pattern') + 1
            except ValueError:
                insert_pos = 1  # After 'epw_paths'

        non_cat_cols = [c for c in original_cols if not c.startswith('cat_')]
        final_cols_order = non_cat_cols[:insert_pos] + cat_cols + non_cat_cols[insert_pos:]
        plan_df = plan_df.reindex(columns=final_cols_order)

        # --- Part 2: Validate for potential filename overwrites ---
        logger.info("Validating for potential filename overwrites...")

        # Initialize a flag to track if any overwrite issues were detected.
        # This ensures the final log message is accurate.
        overwrite_detected = False

        # Find the placeholders of the output pattern of each run (each run can have its own).
        if 'output_filename_pattern' in plan_df.columns:
            run_patterns = [pattern if isinstance(pattern, str) else '' for pattern in plan_df['output_filename_pattern']]
        else:
            run_patterns = [''] * len(plan_df)
        placeholders_per_run = [set(re.findall(r'{(.*?)}', pattern)) for pattern in run_patterns]

        # --- Validation Layer 1: Proactive check for varying parameters ---
        varying_columns = []
        # These columns are expected to be different per run but don't need to be in the filename pattern.
        # The selected scenarios and periods are already covered by the scenario and {year} placeholders.
        ignore_cols = ['epw_paths', 'final_output_dir', 'input_filename_pattern', 'keyword_mapping',
                       'output_filename_pattern', 'fwg_scenarios', 'fwg_timeframes', 'fwg_model_unzipped_folder']

        for col in plan_df.columns:
            if col in ignore_cols:
                continue

            try:
                # Lists are compared as tuples, and a missing value (i.e., the default of the
                # workflow) counts as one more value.
                unique_count = len({_comparable(value) for value in plan_df[col]})
            except TypeError:
                # Unhashable values (e.g., dictionaries) are not compared.
                continue

            if unique_count > 1:
                varying_columns.append(col)

        # Convert column names to placeholder names (e.g., 'cat_uhi' -> 'uhi').
        varying_placeholders = {col.replace('cat_', '') for col in varying_columns}

        # Check if any varying parameter or category is missing from the filename pattern of any run.
        missing_placeholders = sorted(
            placeholder for placeholder in varying_placeholders
            if any(placeholder not in run_placeholders for run_placeholders in placeholders_per_run)
        )
        if missing_placeholders:
            # Construct the message first.
            message = (
                f"Potential file overwrite detected! The following parameters or categories vary "
                f"between runs but are not included as placeholders in the 'output_filename_pattern': "
                f"{missing_placeholders}. Please add them to the pattern to ensure unique filenames."
            )
            # This layer ONLY warns, it never raises an error.
            logger.warning(message)
            overwrite_detected = True

        # --- Part 3: Prepare the workflows ---
        logger.info(f"Preparing {len(plan_df)} workflow instances...")
        prepared_runs = []

        for run_number, (index, row) in enumerate(plan_df.iterrows(), start=1):
            # Missing values are not passed, so the workflow uses the values of
            # 'fwg_params' or its own defaults for them.
            run_params = row.dropna().to_dict()

            # Extract parameters that are for the iterator, not the workflow config.
            epw_paths = run_params.pop('epw_paths')
            run_input_pattern = run_params.pop('input_filename_pattern', None) or input_filename_pattern
            run_keyword_map = run_params.pop('keyword_mapping', None) or keyword_mapping
            # Remove the informational 'cat_*' columns before passing to the config method.
            for col in list(run_params.keys()):
                if col.startswith('cat_'):
                    run_params.pop(col)

            epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths

            try:
                # Create and configure a workflow instance for this specific run.
                workflow = self.workflow_class()
                workflow.map_categories(
                    epw_files=epw_files,
                    input_filename_pattern=run_input_pattern,
                    keyword_mapping=run_keyword_map
                )
                workflow.configure_and_preview(**run_params)
                # Add the fully configured instance to the list for later execution.
                prepared_runs.append((run_number, workflow))
            except Exception as e:
                logger.error(f"Failed to prepare workflow for run {run_number}: {e}")

        # --- Validation Layer 2: Definitive check of the final paths of all files ---
        # The rename plan of each workflow contains the final path of every file that it
        # will write (one per input file, scenario and year), built with the output
        # folder, filename pattern, categories and parameters of its own run.
        destinations = {}
        for run_number, workflow in prepared_runs:
            for epw_path in workflow.epws_to_be_morphed:
                for final_path in workflow.rename_plan.get(epw_path, {}).values():
                    # The weather and .stat files share the path without extension. Paths are
                    # compared as absolute paths (case-insensitively on Windows).
                    base_path = os.path.abspath(os.path.splitext(final_path)[0])
                    entry = destinations.setdefault(os.path.normcase(base_path), {'path': base_path, 'writers': []})
                    entry['writers'].append(f"run {run_number} ({os.path.basename(epw_path)})")

        colliding_paths = sorted(
            (entry for entry in destinations.values() if len(entry['writers']) > 1), key=lambda entry: entry['path'])
        if colliding_paths:
            # Build a user-friendly error message listing ALL collisions.
            message = (
                    f"Definitive file overwrite(s) detected! The following {len(colliding_paths)} output file(s) "
                    f"(weather and .stat files, shown without extension) would be written more than once:\n"
                    + "\n".join(f"- {entry['path']}: {', '.join(entry['writers'])}" for entry in colliding_paths)
                    + "\n\nPlease review your `output_filename_pattern`, `final_output_dir` and `keyword_mapping` "
                      "to ensure unique filenames."
            )

            # For definitive collisions, we respect the raise_on_overwrite flag.
            if raise_on_overwrite:
                raise ValueError(message)
            else:
                logger.warning(message)
                logger.warning("Execution will continue, but output files will be overwritten.")
                overwrite_detected = True

        # Log the final result of the validation.
        if not overwrite_detected:
            logger.info("Filename validation passed. No overwrites detected.")
        else:
            logger.info("Filename validation complete. Potential overwrites were detected (see warnings above).")

        # --- Part 4: Store the plan and the prepared workflows ---
        self.morphing_workflows_plan_df = plan_df
        self.prepared_workflows = [workflow for _, workflow in prepared_runs]

        logger.info(f"Execution plan generated and {len(self.prepared_workflows)} workflows prepared.")

    def run_morphing_workflows(self, show_tool_output: Optional[bool] = None):
        """
        Executes the batch of prepared morphing workflows.

        This method is the final step in the iterator's workflow. It takes no
        arguments to define the scenarios, as it relies entirely on the list of
        workflow instances that were created and configured by the
        `generate_morphing_workflows` method.

        It iterates through the `self.prepared_workflows` list and calls the
        `execute_morphing` method on each one that was found to have a valid
        configuration during the preparation phase.

        Args:
            show_tool_output (Optional[bool], optional): A flag to globally
                override the console output setting for all workflows in this
                specific batch execution.

                - If `True` or `False`, it will force this behavior for all runs,
                  ignoring the `fwg_show_tool_output` value in the plan.
                - If `None` (the default), each run will use the
                  `fwg_show_tool_output` value that was defined for it in the
                  execution plan.

        Raises:
            RuntimeError: If `generate_morphing_workflows()` has not been run
                first, as there are no prepared workflows to execute.
        """
        # Guard clause: Ensure that the preparation step has been completed.
        if not self.prepared_workflows:
            raise RuntimeError("No workflows have been prepared. Please run generate_morphing_workflows() first.")

        logger.info(f"Starting execution of {len(self.prepared_workflows)} prepared runs...")

        # Iterate through the list of fully configured workflow instances.
        for i, workflow in enumerate(self.prepared_workflows):
            logger.info(f"--- Running Run {i + 1}/{len(self.prepared_workflows)} ---")
            try:
                # --- Override Logic for Tool Output ---
                # If the user provides a value for show_tool_output when calling
                # this method, it overrides the setting in the prepared workflow instance.
                # This provides a convenient way to force silent or verbose output for
                # the entire batch at execution time.
                if show_tool_output is not None:
                    workflow.inputs['show_tool_output'] = show_tool_output

                # Check the validity flag that was set during the preparation phase.
                if workflow.is_config_valid:
                    # If the configuration is valid, call the workflow's execution method.
                    workflow.execute_morphing()
                else:
                    # If the configuration was found to be invalid during preparation,
                    # log an error and skip this run.
                    logger.error(f"Run {i + 1} skipped due to invalid configuration detected during preparation.")

            except Exception as e:
                # If any unexpected error occurs during a single run, log it
                # and continue with the next run in the batch. This makes the
                # iterator robust to single-run failures.
                logger.error(f"An unexpected error occurred in run {i + 1}: {e}")
                logger.error("Moving to the next run.")
                continue

        logger.info("Batch run complete.")
