# pyfwg/iterator.py

import pandas as pd
import inspect
import logging
from typing import Type, List, Dict, Any, Union

# Import the base class to use its type hint
from .workflow import _MorphingWorkflowBase


class MorphingIterator:
    """Automates running multiple morphing scenarios from a structured input."""

    def __init__(self, workflow_class: Type[_MorphingWorkflowBase]):
        """Initializes the iterator with a specific workflow class."""
        self.workflow_class = workflow_class
        logging.info(f"MorphingIterator initialized for {workflow_class.__name__}.")

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
        """Fills missing values in a scenario DataFrame with the workflow's defaults.

        This method takes a user-provided DataFrame, which may have empty (NaN)
        cells, and fills them with the default values defined in the
        workflow's `configure_and_preview` method.

        It uses a robust `.apply()` method to fill values, which avoids
        FutureWarnings related to downcasting in Pandas.

        Args:
            scenarios_df (pd.DataFrame): The user's DataFrame of scenarios,
                potentially with missing values.

        Returns:
            pd.DataFrame: A new DataFrame with all default values applied.
        """
        logging.info("Applying default values to the scenario DataFrame...")

        # Get the signature of the target configuration method.
        sig = inspect.signature(self.workflow_class.configure_and_preview)

        # Create a dictionary of {parameter_name: default_value} for all
        # parameters that have a default.
        default_values = {
            p.name: p.default
            for p in sig.parameters.values()
            if p.default is not inspect.Parameter.empty
        }

        # Create a copy of the DataFrame to avoid modifying the original.
        completed_df = scenarios_df.copy()

        # Iterate through the parameters that have default values.
        for col, default_val in default_values.items():
            # Only attempt to fill the column if a default value actually exists (is not None).
            if col in completed_df.columns and default_val is not None:
                # --- FUTUREWARNING FIX IS HERE ---
                # Use the .apply() method for all columns. This is a robust,
                # future-proof way to fill missing values without triggering
                # Pandas' downcasting FutureWarning, which occurs with .fillna().
                # It checks each cell individually: if the cell is null
                # (NaN or None), it's replaced with the default value.
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

            run_params = row.dropna().to_dict()

            epw_paths = run_params.pop('epw_paths', None)
            input_pattern = run_params.pop('input_filename_pattern', None)
            keyword_map = run_params.pop('keyword_mapping', None)

            if not epw_paths:
                logging.error(f"Scenario {index + 1} skipped: 'epw_paths' column is missing or empty.")
                continue

            epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths

            try:
                workflow = self.workflow_class()
                workflow.map_categories(
                    epw_files=epw_files,
                    input_filename_pattern=input_pattern,
                    keyword_mapping=keyword_map
                )
                workflow.configure_and_preview(**run_params)
                if workflow.is_config_valid:
                    workflow.execute_morphing()
                else:
                    logging.error(f"Scenario {index + 1} skipped due to invalid configuration. Please check warnings above.")

            except Exception as e:
                logging.error(f"An unexpected error occurred in scenario {index + 1}: {e}")
                logging.error("Moving to the next scenario.")
                continue

        logging.info("Batch run complete.")