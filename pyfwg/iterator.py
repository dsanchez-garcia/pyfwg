# pyfwg/iterator.py
import re

import pandas as pd
import inspect
import logging
from typing import Type, List, Dict, Any, Union, Optional

# Import the base class to use its type hint
from .workflow import _MorphingWorkflowBase
from .constants import ALL_POSSIBLE_YEARS

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
            runs_df.loc = {'epw_paths': 'file1.epw', 'fwg_gcms': ['CanESM5']}
            runs_df.loc = {'epw_paths': 'file2.epw', 'fwg_gcms': ['MIROC6']}
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
        logging.info(f"MorphingIterator initialized for {workflow_class.__name__}.")

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
                           fwg_target_uhi_lcz: Optional[int] = None):
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
        includes a validation check to warn the user if they provide a
        model-specific argument that is not applicable to the chosen workflow
        (e.g., providing `fwg_rcm_pairs` for a `MorphingWorkflowGlobal` instance).

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
            'fwg_epw_original_lcz': fwg_epw_original_lcz, 'fwg_target_uhi_lcz': fwg_target_uhi_lcz
        }

        # Filter out any arguments that were not provided (are None).
        self.custom_defaults = {key: value for key, value in provided_args.items() if value is not None}

        # --- Validation and Warning Logic ---
        correct_model_arg = f"fwg_{self.workflow_class.model_arg_name}"
        incorrect_model_arg = 'fwg_rcm_pairs' if correct_model_arg == 'fwg_gcms' else 'fwg_gcms'

        if incorrect_model_arg in self.custom_defaults:
            logging.warning(
                f"Argument '{incorrect_model_arg}' is not applicable for "
                f"{self.workflow_class.__name__} and will be ignored."
            )
            # Remove the inapplicable argument so it's not used later.
            self.custom_defaults.pop(incorrect_model_arg)

        logging.info(f"Custom default values have been set for the iterator: {self.custom_defaults}")

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
            # Case 1: The column does not exist in the user's DataFrame.
            if col not in completed_df.columns:
                # If a default value exists, create the column and fill all
                # rows with this default.
                if default_val is not None:
                    completed_df[col] = default_val
            # Case 2: The column exists, but may have missing values.
            else:
                # Only proceed if there is a default value to fill with.
                if default_val is not None:
                    # Use the robust .apply() method to fill only the NaN values.
                    # This is safer than .fillna() for DataFrames with mixed
                    # data types (like lists) and avoids FutureWarning.
                    completed_df[col] = completed_df[col].apply(
                        lambda x: default_val if pd.isnull(x) else x
                    )

        # Return the fully populated DataFrame.
        return completed_df

    def generate_morphing_workflows(self,
                                    runs_df: pd.DataFrame,
                                    input_filename_pattern: Optional[str] = None,
                                    keyword_mapping: Optional[Dict] = None):
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
        4.  **Validates for Filename Overwrites**: It identifies all parameters
            AND categories that vary between runs and ensures they are included
            as placeholders in the `output_filename_pattern` to prevent data loss.
        5.  **Stores the Plan**: The final, validated DataFrame is stored in
            `self.morphing_workflows_plan_df` for user inspection.
        6.  **Prepares Workflows**: It instantiates and fully configures a
            `MorphingWorkflow` object for each run in the plan. These
            ready-to-run instances are stored in `self.prepared_workflows`.

        Args:
            runs_df (pd.DataFrame): The user's DataFrame of runs. Each row
                represents a unique configuration to be executed.
            input_filename_pattern (Optional[str], optional): A regex pattern for
                filename mapping, applied as a default to *every* run unless
                overridden in the DataFrame. Defaults to None.
            keyword_mapping (Optional[Dict], optional): A dictionary of keyword
                rules for filename mapping, applied as a default to *every* run
                unless overridden in the DataFrame.

        Raises:
            ValueError: If a parameter or category varies between runs but is not included
                as a placeholder in the `output_filename_pattern`.
        """
        logging.info("Generating detailed execution plan and preparing workflows...")

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
            run_input_pattern = row.get('input_filename_pattern') if pd.notnull(row.get('input_filename_pattern')) else input_filename_pattern
            run_keyword_map = row.get('keyword_mapping') if pd.notnull(row.get('keyword_mapping')) else keyword_mapping

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
        logging.info("Validating for potential filename overwrites...")

        # Get the output pattern from the plan (it should be the same for all runs).
        output_pattern = plan_df['output_filename_pattern'].iloc[0]

        # Find all placeholders the user has included in their pattern.
        pattern_placeholders = set(re.findall(r'{(.*?)}', output_pattern))

        # Find all parameters AND categories that actually vary across the different runs.
        varying_columns = []
        # These columns are expected to be different per run but don't need to be in the filename pattern.
        ignore_cols = ['epw_paths', 'final_output_dir', 'input_filename_pattern', 'keyword_mapping']

        for col in plan_df.columns:
            if col in ignore_cols:
                continue

            try:
                # Use a robust method to check for uniqueness, handling lists.
                if isinstance(plan_df[col].dropna().iloc[0], list):
                    unique_count = plan_df[col].dropna().apply(lambda x: tuple(x) if isinstance(x, list) else x).nunique()
                else:
                    unique_count = plan_df[col].nunique()

                if unique_count > 1:
                    varying_columns.append(col)
            except (TypeError, IndexError):
                # This can happen with mixed types or empty columns, which we can ignore.
                continue

        # Convert column names to placeholder names (e.g., 'cat_uhi' -> 'uhi').
        varying_placeholders = {col.replace('cat_', '') for col in varying_columns}

        # Check if any varying parameter or category is missing from the filename pattern.
        missing_placeholders = varying_placeholders - pattern_placeholders
        if missing_placeholders:
            raise ValueError(
                f"Potential file overwrite detected! The following parameters or categories vary between runs but are not "
                f"included as placeholders in the 'output_filename_pattern': {list(missing_placeholders)}. "
                f"Please add them to the pattern to ensure unique filenames."
            )

        logging.info("Filename validation passed. No overwrites detected.")

        # --- Part 3: Store the plan and prepare workflows ---
        self.morphing_workflows_plan_df = plan_df

        logging.info(f"Preparing {len(plan_df)} workflow instances...")
        self.prepared_workflows = []

        # Iterate through the now-validated plan DataFrame.
        for index, row in plan_df.iterrows():
            # The row now contains all defaults, so dropna is safe.
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
                self.prepared_workflows.append(workflow)
            except Exception as e:
                logging.error(f"Failed to prepare workflow for run {index + 1}: {e}")

        logging.info(f"Execution plan generated and {len(self.prepared_workflows)} workflows prepared.")

    def run_morphing_workflows(self, show_tool_output: Optional[bool] = None):
        """Executes the batch of prepared morphing workflows.

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

        logging.info(f"Starting execution of {len(self.prepared_workflows)} prepared runs...")

        # Iterate through the list of fully configured workflow instances.
        for i, workflow in enumerate(self.prepared_workflows):
            logging.info(f"--- Running Run {i + 1}/{len(self.prepared_workflows)} ---")
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
                    logging.error(f"Run {i + 1} skipped due to invalid configuration detected during preparation.")

            except Exception as e:
                # If any unexpected error occurs during a single run, log it
                # and continue with the next run in the batch. This makes the
                # iterator robust to single-run failures.
                logging.error(f"An unexpected error occurred in run {i + 1}: {e}")
                logging.error("Moving to the next run.")
                continue

        logging.info("Batch run complete.")
