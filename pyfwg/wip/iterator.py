# pyfwg/iterator.py

import pandas as pd
import inspect
import logging
from typing import Type, List, Dict, Any, Union

# Import the base class to use its type hint
from .workflow import _MorphingWorkflowBase


class MorphingIterator:
    """Automates running multiple morphing scenarios from a structured input.

    This class is designed to perform parametric analysis by iterating over
    different sets of parameters for a given morphing workflow. It takes a
    Pandas DataFrame as input, where each row represents a unique morphing
    run and each column corresponds to a parameter of the workflow.

    The typical usage is:
    1. Instantiate the iterator with the desired workflow class.
    2. (Optional) Use `set_default_values()` to define common parameters for all runs.
    3. Use `get_template_dataframe()` to get a blank DataFrame.
    4. Populate the DataFrame with the parameters that change between scenarios.
    5. (Optional) Call `apply_defaults()` to get a complete view of the final execution plan.
    6. Call `run_from_dataframe()` to execute all the runs.
    """

    def __init__(self, workflow_class: Type[_MorphingWorkflowBase]):
        """Initializes the iterator with a specific workflow class.

        Args:
            workflow_class (Type[_MorphingWorkflowBase]): The workflow class to
                be used for the iterations (e.g., `MorphingWorkflowGlobal` or
                `MorphingWorkflowEurope`).
        """
        self.workflow_class = workflow_class
        # This dictionary will store the user-defined defaults for the batch run.
        self.custom_defaults: Dict[str, Any] = {}
        logging.info(f"MorphingIterator initialized for {workflow_class.__name__}.")

    def set_default_values(self, **kwargs):
        """Sets default parameter values for all scenarios in the batch run.

        Any parameter set here will be used for every row in the DataFrame
        unless a different value is specified in the row itself. This is useful
        for defining common parameters like `fwg_jar_path`.

        The priority of parameters is:
        1. (Lowest) Hardcoded defaults from the workflow class.
        2. (Medium) Defaults set with this method.
        3. (Highest) Values specified in the scenario DataFrame.

        Args:
            **kwargs: Keyword arguments corresponding to the parameters of the
                workflow's `configure_and_preview` method.
        """
        self.custom_defaults = kwargs
        logging.info(f"Custom default values have been set for the iterator: {kwargs}")

    def get_template_dataframe(self) -> pd.DataFrame:
        """Generates an empty Pandas DataFrame with the correct parameter columns."""
        sig = inspect.signature(self.workflow_class.configure_and_preview)
        param_names = [
            p.name for p in sig.parameters.values()
            if p.name not in ('self', 'kwargs') and p.kind == p.KEYWORD_ONLY
        ]
        final_columns = ['epw_paths', 'input_filename_pattern', 'keyword_mapping'] + param_names
        return pd.DataFrame(columns=final_columns)

    def apply_defaults(self, scenarios_df: pd.DataFrame) -> pd.DataFrame:
        """Fills missing values in a scenario DataFrame with the defined defaults.

        This method applies defaults in the correct priority order: first the
        custom defaults set via `set_default_values`, and then the hardcoded
        defaults from the workflow class for any remaining empty cells.

        Args:
            scenarios_df (pd.DataFrame): The user's DataFrame of scenarios.

        Returns:
            pd.DataFrame: A new DataFrame with all default values applied.
        """
        logging.info("Applying default values to the scenario DataFrame...")

        sig = inspect.signature(self.workflow_class.configure_and_preview)
        hardcoded_defaults = {
            p.name: p.default
            for p in sig.parameters.values()
            if p.default is not inspect.Parameter.empty
        }

        # --- Priority Logic ---
        # 1. Start with the lowest priority defaults (hardcoded in the class).
        final_defaults = hardcoded_defaults.copy()
        # 2. Update with the medium priority defaults (set by the user for the iterator).
        final_defaults.update(self.custom_defaults)

        completed_df = scenarios_df.copy()

        for col, default_val in final_defaults.items():
            if col in completed_df.columns and default_val is not None:
                # Use the robust .apply() method to fill missing values.
                completed_df[col] = completed_df[col].apply(
                    lambda x: default_val if pd.isnull(x) else x
                )

        logging.info("Default values applied successfully.")
        return completed_df

    def run_from_dataframe(self, scenarios_df: pd.DataFrame):
        """Executes a batch of morphing runs based on a scenario DataFrame."""
        logging.info(f"Starting batch run of {len(scenarios_df)} scenarios...")

        for index, row in scenarios_df.iterrows():
            logging.info(f"--- Running Scenario {index + 1}/{len(scenarios_df)} ---")

            # --- Priority Logic for Execution ---
            # 1. Start with the custom defaults set for the iterator.
            run_params = self.custom_defaults.copy()
            # 2. Get the specific values from the current row, dropping any NaNs.
            row_params = row.dropna().to_dict()
            # 3. Update the defaults with the row-specific values, which take highest priority.
            run_params.update(row_params)

            epw_paths = run_params.pop('epw_paths', None)
            input_pattern = run_params.pop('input_filename_pattern', None)
            keyword_map = run_params.pop('keyword_mapping', None)

            if not epw_paths:
                logging.error(f"Scenario {index + 1} skipped: 'epw_paths' is missing.")
                continue

            epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths

            try:
                workflow = self.workflow_class()
                workflow.map_categories(
                    epw_files=epw_files,
                    input_filename_pattern=input_pattern,
                    keyword_mapping=keyword_map
                )
                # The hardcoded defaults are handled automatically by the method signature.
                workflow.configure_and_preview(**run_params)

                if workflow.is_config_valid:
                    workflow.execute_morphing()
                else:
                    logging.error(f"Scenario {index + 1} skipped due to invalid configuration.")

            except Exception as e:
                logging.error(f"An unexpected error occurred in scenario {index + 1}: {e}")
                logging.error("Moving to the next scenario.")
                continue

        logging.info("Batch run complete.")