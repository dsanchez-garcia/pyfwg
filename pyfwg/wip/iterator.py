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
    """

    def __init__(self, workflow_class: Type[_MorphingWorkflowBase]):
        """Initializes the iterator with a specific workflow class.

        Args:
            workflow_class (Type[_MorphingWorkflowBase]): The workflow class to
                be used for the iterations (e.g., `MorphingWorkflowGlobal` or
                `MorphingWorkflowEurope`).
        """
        self.workflow_class = workflow_class
        self.custom_defaults: Dict[str, Any] = {}
        logging.info(f"MorphingIterator initialized for {workflow_class.__name__}.")

    def set_default_values(self, **kwargs):
        """Sets default parameter values for all scenarios in the batch run."""
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
        """Fills missing values in a scenario DataFrame with the defined defaults."""
        logging.info("Applying default values to the scenario DataFrame...")

        sig = inspect.signature(self.workflow_class.configure_and_preview)
        hardcoded_defaults = {
            p.name: p.default
            for p in sig.parameters.values()
            if p.default is not inspect.Parameter.empty
        }

        final_defaults = hardcoded_defaults.copy()
        final_defaults.update(self.custom_defaults)

        completed_df = scenarios_df.copy()

        for col, default_val in final_defaults.items():
            if col in completed_df.columns and default_val is not None:
                completed_df[col] = completed_df[col].apply(
                    lambda x: default_val if pd.isnull(x) else x
                )

        logging.info("Default values applied successfully.")
        return completed_df

    def run_from_dataframe(self, scenarios_df: pd.DataFrame):
        """Executes a batch of morphing runs based on a scenario DataFrame.

        This method iterates through each row of the provided DataFrame. For each
        row, it validates that all mandatory parameters are present, configures
        the workflow, and executes it.

        Mandatory parameters that must be defined either in the DataFrame row
        or in `set_default_values` are:
        - `epw_paths`
        - `output_filename_pattern`
        - `fwg_jar_path`
        - `fwg_gcms` (for MorphingWorkflowGlobal) or `fwg_rcm_pairs` (for MorphingWorkflowEurope)

        Args:
            scenarios_df (pd.DataFrame): A DataFrame where each row defines a
                unique morphing scenario.
        """
        logging.info(f"Starting batch run of {len(scenarios_df)} scenarios...")

        # Get the dynamic model argument name from the workflow class.
        model_arg_name = self.workflow_class.model_arg_name

        # Define the list of parameters that are mandatory for every run.
        mandatory_params = [
            'epw_paths',
            'output_filename_pattern',
            'fwg_jar_path',
            model_arg_name
        ]

        for index, row in scenarios_df.iterrows():
            logging.info(f"--- Running Scenario {index + 1}/{len(scenarios_df)} ---")

            # --- 1. Combine parameters and validate ---
            # Start with the custom defaults set for the iterator.
            run_params = self.custom_defaults.copy()
            # Get the specific values from the current row, dropping any NaNs.
            row_params = row.dropna().to_dict()
            # Update the defaults with the row-specific values, which take highest priority.
            run_params.update(row_params)

            # Check if all mandatory parameters are present in the combined set.
            missing_params = [
                p for p in mandatory_params
                if p not in run_params or pd.isnull(run_params.get(p))
            ]

            if missing_params:
                logging.error(f"Scenario {index + 1} skipped: The following mandatory parameters are missing: {missing_params}")
                continue  # Skip to the next scenario.

            # --- 2. Extract parameters and execute ---
            epw_paths = run_params.pop('epw_paths')
            input_pattern = run_params.pop('input_filename_pattern', None)
            keyword_map = run_params.pop('keyword_mapping', None)

            # Normalize epw_paths to always be a list.
            epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths

            try:
                # Instantiate a fresh workflow for this run.
                workflow = self.workflow_class()

                # Map categories using the parameters from the row.
                workflow.map_categories(
                    epw_files=epw_files,
                    input_filename_pattern=input_pattern,
                    keyword_mapping=keyword_map
                )

                # Configure and preview using the remaining parameters from the row.
                # The hardcoded defaults are handled automatically by the method signature.
                workflow.configure_and_preview(**run_params)

                # Execute if the configuration is valid.
                if workflow.is_config_valid:
                    workflow.execute_morphing()
                else:
                    logging.error(f"Scenario {index + 1} skipped due to invalid configuration.")

            except Exception as e:
                logging.error(f"An unexpected error occurred in scenario {index + 1}: {e}")
                logging.error("Moving to the next scenario.")
                continue

        logging.info("Batch run complete.")