# pyfwg/iterator.py

import pandas as pd
import inspect
import logging
from typing import Type, List, Dict, Any, Union, Optional

# Import the base class to use its type hint
from .workflow import _MorphingWorkflowBase


class MorphingIterator:
    """Automates running multiple morphing scenarios from a structured input."""

    def __init__(self, workflow_class: Type[_MorphingWorkflowBase]):
        """Initializes the iterator with a specific workflow class."""
        self.workflow_class = workflow_class
        self.custom_defaults: Dict[str, Any] = {}
        self.prepared_workflows: List[_MorphingWorkflowBase] = []
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
        """Sets default parameter values for all scenarios in the batch run."""
        # --- BUG FIX IS HERE ---
        # Manually collect all arguments passed to this method into a dictionary.
        # This is safer than using locals() as it avoids capturing internal variables.
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

        for col, default_val in final_defaults.items():
            if col not in completed_df.columns:
                if default_val is not None:
                    completed_df[col] = default_val
            else:
                if default_val is not None:
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

        original_cols = list(plan_df.columns)
        cat_cols = [f'cat_{key}' for key in sorted_cat_keys]
        try:
            insert_pos = original_cols.index('keyword_mapping') + 1
        except ValueError:
            try:
                insert_pos = original_cols.index('input_filename_pattern') + 1
            except ValueError:
                insert_pos = 1

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