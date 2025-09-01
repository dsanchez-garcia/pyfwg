# pyfwg/iterator.py

import pandas as pd
import inspect
import logging
from typing import Type, List, Dict, Any, Union, Optional

# Import the base class to use its type hint
from .workflow import _MorphingWorkflowBase


class MorphingIterator:
    """Automates running multiple morphing scenarios from a structured input.

    This class is designed to perform parametric analysis by iterating over
    different sets of parameters for a given morphing workflow. It uses a
    Pandas DataFrame to define the scenarios.
    """

    def __init__(self, workflow_class: Type[_MorphingWorkflowBase]):
        """Initializes the iterator with a specific workflow class."""
        self.workflow_class = workflow_class
        self.custom_defaults: Dict[str, Any] = {}
        self.prepared_workflows: List[_MorphingWorkflowBase] = []
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

    def _apply_defaults(self, scenarios_df: pd.DataFrame) -> pd.DataFrame:
        """(Private) Fills missing values and adds missing columns with defaults."""
        sig = inspect.signature(self.workflow_class.configure_and_preview)
        hardcoded_defaults = {p.name: p.default for p in sig.parameters.values() if p.default is not inspect.Parameter.empty}
        final_defaults = {**hardcoded_defaults, **self.custom_defaults}

        completed_df = scenarios_df.copy()

        # Iterate through all available default parameters.
        for col, default_val in final_defaults.items():
            # If the column does not exist in the user's DataFrame, create it
            # and fill it entirely with the default value.
            if col not in completed_df.columns:
                if default_val is not None:
                    completed_df[col] = default_val
            # If the column exists, fill only the missing (NaN) values.
            else:
                if default_val is not None:
                    # Use the robust .apply() method to fill.
                    completed_df[col] = completed_df[col].apply(
                        lambda x: default_val if pd.isnull(x) else x
                    )
        return completed_df

    def generate_execution_plan(self,
                                scenarios_df: pd.DataFrame,
                                input_filename_pattern: Optional[str] = None,
                                keyword_mapping: Optional[Dict] = None) -> pd.DataFrame:
        """Generates a detailed execution plan and prepares all workflow instances."""
        logging.info("Generating detailed execution plan and preparing workflows...")

        plan_df = self._apply_defaults(scenarios_df)

        if 'input_filename_pattern' not in plan_df.columns or plan_df['input_filename_pattern'].isnull().all():
            plan_df['input_filename_pattern'] = input_filename_pattern
        if 'keyword_mapping' not in plan_df.columns or plan_df['keyword_mapping'].isnull().all():
            plan_df['keyword_mapping'] = [keyword_mapping] * len(plan_df)

        extracted_categories = []
        all_category_keys = set()

        for index, row in plan_df.iterrows():
            epw_paths = row.get('epw_paths')
            epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths
            row_input_pattern = row.get('input_filename_pattern') if pd.notnull(row.get('input_filename_pattern')) else input_filename_pattern
            row_keyword_map = row.get('keyword_mapping') if pd.notnull(row.get('keyword_mapping')) else keyword_mapping
            temp_workflow = self.workflow_class()
            temp_workflow.map_categories(
                epw_files=epw_files,
                input_filename_pattern=row_input_pattern,
                keyword_mapping=row_keyword_map
            )
            run_categories = {**temp_workflow.epw_categories, **temp_workflow.incomplete_epw_categories}
            extracted_categories.append(run_categories)
            for cat_dict in run_categories.values():
                all_category_keys.update(cat_dict.keys())

        sorted_cat_keys = sorted(list(all_category_keys))
        for key in sorted_cat_keys:
            plan_df[f'cat_{key}'] = [
                list({cat_dict.get(key) for cat_dict in run_cats.values() if cat_dict.get(key)})
                for run_cats in extracted_categories
            ]

        # Reorder columns to place categories correctly.
        original_cols = list(plan_df.columns)
        cat_cols = [f'cat_{key}' for key in sorted_cat_keys]
        # Find the insertion point.
        try:
            insert_pos = original_cols.index('keyword_mapping') + 1
        except ValueError:
            try:
                insert_pos = original_cols.index('input_filename_pattern') + 1
            except ValueError:
                insert_pos = 1  # After 'epw_paths'

        # Rebuild the list of all columns in the desired order.
        # We need to filter out the cat_cols from the original list first.
        non_cat_cols = [c for c in original_cols if not c.startswith('cat_')]
        final_cols_order = non_cat_cols[:insert_pos] + cat_cols + non_cat_cols[insert_pos:]
        plan_df = plan_df.reindex(columns=final_cols_order)

        logging.info(f"Preparing {len(plan_df)} workflow instances...")
        self.prepared_workflows = []

        for index, row in plan_df.iterrows():
            run_params = row.dropna().to_dict()
            epw_paths = run_params.pop('epw_paths')
            row_input_pattern = run_params.pop('input_filename_pattern', None) or input_filename_pattern
            row_keyword_map = run_params.pop('keyword_mapping', None) or keyword_mapping
            for col in list(run_params.keys()):
                if col.startswith('cat_'):
                    run_params.pop(col)
            epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths
            try:
                workflow = self.workflow_class()
                workflow.map_categories(
                    epw_files=epw_files,
                    input_filename_pattern=row_input_pattern,
                    keyword_mapping=row_keyword_map
                )
                workflow.configure_and_preview(**run_params)
                self.prepared_workflows.append(workflow)
            except Exception as e:
                logging.error(f"Failed to prepare workflow for scenario {index + 1}: {e}")

        logging.info(f"Execution plan generated and {len(self.prepared_workflows)} workflows prepared.")
        return plan_df

    def execute_workflows(self):
        """Executes the batch of prepared morphing workflows."""
        if not self.prepared_workflows:
            raise RuntimeError("No workflows have been prepared. Please run generate_execution_plan() first.")
        logging.info(f"Starting execution of {len(self.prepared_workflows)} prepared scenarios...")
        for i, workflow in enumerate(self.prepared_workflows):
            logging.info(f"--- Running Scenario {i + 1}/{len(self.prepared_workflows)} ---")
            try:
                if workflow.is_config_valid:
                    workflow.execute_morphing()
                else:
                    logging.error(f"Scenario {i + 1} skipped due to invalid configuration detected during preparation.")
            except Exception as e:
                logging.error(f"An unexpected error occurred in scenario {i + 1}: {e}")
                logging.error("Moving to the next scenario.")
                continue
        logging.info("Batch run complete.")