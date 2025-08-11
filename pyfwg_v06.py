import os
import re
import shutil
import subprocess
import logging
from typing import List, Optional, Dict, Any

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Constants for FWG Output ---
ALL_POSSIBLE_SCENARIOS = ['ssp126', 'ssp245', 'ssp370', 'ssp585']
ALL_POSSIBLE_YEARS = [2050, 2080]

# --- Default GCMs List ---
DEFAULT_GCMS = [
    'BCC_CSM2_MR', 'CanESM5', 'CanESM5_1', 'CanESM5_CanOE', 'CAS_ESM2_0',
    'CMCC_ESM2', 'CNRM_CM6_1', 'CNRM_CM6_1_HR', 'CNRM_ESM2_1', 'EC_Earth3',
    'EC_Earth3_Veg', 'EC_Earth3_Veg_LR', 'FGOALS_g3', 'GFDL_ESM4',
    'GISS_E2_1_G', 'GISS_E2_1_H', 'GISS_E2_2_G', 'IPSL_CM6A_LR',
    'MIROC_ES2H', 'MIROC_ES2L', 'MIROC6', 'MRI_ESM2_0', 'UKESM1_0_LL'
]


class MorphingWorkflow:
    """
    Manages the EPW morphing process in a controlled, step-by-step manner.
    """

    def __init__(self):
        """
        Initializes the workflow. All configuration is provided via methods.
        - self.epw_categories: Stores files that were fully categorized.
        - self.incomplete_epw_categories: Stores files that were only partially categorized.
        """
        self.inputs: Dict[str, Any] = {}
        self.epw_categories: Dict[str, Dict[str, str]] = {}
        self.incomplete_epw_categories: Dict[str, Dict[str, str]] = {}
        self.rename_plan: Dict[str, Dict[str, str]] = {}

    def map_categories(self,
                       epw_files: List[str],
                       input_filename_pattern: Optional[str] = None,
                       keyword_mapping: Optional[Dict[str, Dict[str, List[str]]]] = None):
        """
        STEP 1: Identifies and maps categories for each EPW file.
        In keyword mode, it also detects and warns about partially mapped files.
        """
        logging.info("--- Step 1: Mapping categories from filenames ---")

        if input_filename_pattern and keyword_mapping:
            raise ValueError("Please provide either 'input_filename_pattern' or 'keyword_mapping', not both.")
        if not input_filename_pattern and not keyword_mapping:
            raise ValueError("You must provide one mapping method: 'input_filename_pattern' or 'keyword_mapping'.")

        self.inputs['epw_files'] = epw_files
        self.epw_categories = {}
        self.incomplete_epw_categories = {}

        all_defined_categories = set(keyword_mapping.keys()) if keyword_mapping else set()

        for epw_path in epw_files:
            if not os.path.exists(epw_path):
                logging.warning(f"EPW file not found, skipping: {epw_path}")
                continue

            epw_name_lower = os.path.basename(epw_path).lower()
            file_categories = {}

            if input_filename_pattern:
                epw_base_name = os.path.splitext(os.path.basename(epw_path))[0]
                match = re.search(input_filename_pattern, epw_base_name)
                if match:
                    file_categories = match.groupdict()
                else:
                    logging.warning(f"Pattern did not match '{epw_base_name}'. Skipping.")
                    continue

            elif keyword_mapping:
                for category, rules in keyword_mapping.items():
                    for final_value, keywords in rules.items():
                        if any(keyword.lower() in epw_name_lower for keyword in keywords):
                            file_categories[category] = final_value
                            break

            if file_categories:
                logging.info(f"Mapped '{epw_path}': {file_categories}")
                # Check for completeness only in keyword mode
                if keyword_mapping:
                    found_categories = set(file_categories.keys())
                    if len(found_categories) < len(all_defined_categories):
                        missing = all_defined_categories - found_categories
                        logging.warning(f"File '{os.path.basename(epw_path)}' is missing categories: {list(missing)}. It will be processed but may cause renaming errors.")
                        self.incomplete_epw_categories[epw_path] = file_categories
                    else:
                        self.epw_categories[epw_path] = file_categories
                else:  # Pattern mode always assumes completeness
                    self.epw_categories[epw_path] = file_categories
            else:
                logging.warning(f"Could not map any categories for '{epw_path}'. Skipping.")

        logging.info("Category mapping complete.")

    def preview_rename_plan(self,
                            final_output_dir: str,
                            output_filename_pattern: str,
                            scenario_mapping: Optional[Dict[str, str]] = None):
        """
        STEP 2: Generates a plan for all mapped files (both complete and incomplete).
        """
        if not self.epw_categories and not self.incomplete_epw_categories:
            raise RuntimeError("Please run map_categories() first. No files were successfully mapped.")

        logging.info("--- Step 2: Generating rename and move plan ---")
        self.inputs.update({
            'final_output_dir': final_output_dir,
            'output_filename_pattern': output_filename_pattern,
            'scenario_mapping': scenario_mapping or {}
        })

        self.rename_plan = {}
        all_mapped_files = {**self.epw_categories, **self.incomplete_epw_categories}

        print("\n" + "=" * 60 + "\n          MORPHING AND RENAMING PREVIEW\n" + "=" * 60)
        print(f"\nFinal Output Directory: {os.path.abspath(final_output_dir)}")

        for epw_path, mapped_data in all_mapped_files.items():
            self.rename_plan[epw_path] = {}
            is_incomplete = epw_path in self.incomplete_epw_categories
            status_flag = " [INCOMPLETE MAPPING]" if is_incomplete else ""
            print(f"\n  For input file: {os.path.basename(epw_path)}{status_flag}")

            for year in ALL_POSSIBLE_YEARS:
                for scenario in ALL_POSSIBLE_SCENARIOS:
                    filename_data = {**mapped_data, 'scenario': scenario, 'ssp_full_name': self.inputs['scenario_mapping'].get(scenario, scenario), 'year': year}
                    try:
                        new_base_name = output_filename_pattern.format(**filename_data)
                        final_epw_path = os.path.join(final_output_dir, new_base_name + ".epw")
                        generated_file_key = f"{scenario}_{year}.epw"
                        self.rename_plan[epw_path][generated_file_key] = final_epw_path
                        print(f"    -> Generated '{generated_file_key}' will be moved to: {os.path.abspath(final_epw_path)}")
                    except KeyError as e:
                        print(f"    -> ERROR: Placeholder {e} in output pattern was not found in this file's mapped categories. Renaming will fail for this file.")
                        break

        print("=" * 60 + "\nPreview complete. If this plan is correct, call execute_morphing().")

    def execute_morphing(self,
                         fwg_jar_path: str,
                         fwg_params: Optional[Dict[str, Any]] = None,
                         delete_temp_files: bool = True,
                         temp_base_dir: str = './morphing_temp_results',
                         **kwargs):
        """
        STEP 3: Executes the morphing process for all mapped files.
        """
        if not self.rename_plan:
            raise RuntimeError("Please run preview_rename_plan() to set up the output before executing.")

        logging.info("--- Step 3: Executing morphing workflow ---")
        base_params = fwg_params or {}
        base_params.update(kwargs)

        self.inputs.update({
            'fwg_jar_path': fwg_jar_path,
            'fwg_params': base_params,
            'delete_temp_files': delete_temp_files,
            'temp_base_dir': temp_base_dir
        })

        os.makedirs(self.inputs['final_output_dir'], exist_ok=True)
        os.makedirs(temp_base_dir, exist_ok=True)

        all_files_to_process = list(self.epw_categories.keys()) + list(self.incomplete_epw_categories.keys())

        for epw_path in all_files_to_process:
            temp_epw_output_dir = os.path.join(temp_base_dir, os.path.splitext(os.path.basename(epw_path))[0])
            os.makedirs(temp_epw_output_dir, exist_ok=True)
            success = self._execute_single_morph(epw_path, temp_epw_output_dir)
            if success:
                self._process_generated_files(epw_path, temp_epw_output_dir)
                if delete_temp_files:
                    shutil.rmtree(temp_epw_output_dir)

        logging.info("Morphing workflow finished.")

    def _execute_single_morph(self, epw_path: str, temp_output_dir: str) -> bool:
        # This private method remains unchanged
        params = self.inputs['fwg_params']
        command = [
            'java', '-cp', self.inputs['fwg_jar_path'], 'futureweathergenerator.Morph',
            os.path.abspath(epw_path),
            ",".join(params.get('gcms', DEFAULT_GCMS)),
            '1' if params.get('create_ensemble', True) else '0',
            f"{params.get('winter_sd_shift', 0.0)}:{params.get('summer_sd_shift', 0.0)}",
            str(params.get('month_transition_hours', 72)),
            os.path.abspath(temp_output_dir) + os.sep,
            str(params.get('use_multithreading', True)).lower(),
            str(params.get('interpolation_method_id', 0)),
            str(params.get('limit_variables', True)).lower(),
            str(params.get('solar_hour_adjustment', 1)),
            str(params.get('diffuse_irradiation_model', 1)),
            params.get('uhi_options', "1:14:1")
        ]
        logging.info(f"Executing command for {os.path.basename(epw_path)}")
        try:
            subprocess.run(command, capture_output=True, text=True, check=True, timeout=600)
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error morphing {os.path.basename(epw_path)}: {e.stderr}")
            return False

    def _process_generated_files(self, source_epw_path: str, temp_dir: str):
        # This private method remains unchanged
        logging.info(f"Processing generated files in: {temp_dir}")
        plan_for_this_epw = self.rename_plan.get(source_epw_path, {})
        for generated_file in os.listdir(temp_dir):
            destination_path = None
            if generated_file in plan_for_this_epw:
                destination_path = plan_for_this_epw[generated_file]
            elif generated_file.endswith(".stat") and generated_file.replace(".stat", ".epw") in plan_for_this_epw:
                epw_dest_path = plan_for_this_epw[generated_file.replace(".stat", ".epw")]
                destination_path = os.path.splitext(epw_dest_path)[0] + ".stat"
            if destination_path:
                source_path = os.path.join(temp_dir, generated_file)
                logging.info(f"Copying '{source_path}' to '{destination_path}'")
                shutil.copy2(source_path, destination_path)


# # --- USAGE EXAMPLE ---
# if __name__ == '__main__':
#     print("--- EXAMPLE: Using Keyword Mapping with an Incomplete File ---")
#     workflow_keywords = MorphingWorkflow()
#
#     keyword_rules = {
#         'city': {
#             'seville': ['sevilla', 'svq'],
#             'madrid': ['madrid', 'mad']
#         },
#         'uhi': {
#             'type_1': ['tipo-1'],
#             'type_2': ['tipo-2']
#         }
#     }
#
#     workflow_keywords.map_categories(
#         epw_files=[
#             'sevilla_uhi_tipo-1.epw',  # Complete
#             'este_epw_es_de_sevilla.epw',  # Incomplete (missing uhi)
#             'unrelated_file.epw'  # Unmappable
#         ],
#         keyword_mapping=keyword_rules
#     )
#
#     # You can inspect the attributes after mapping:
#     print("\n--- Inspection after mapping ---")
#     print(f"Complete files mapped: {list(workflow_keywords.epw_categories.keys())}")
#     print(f"Incomplete files mapped: {list(workflow_keywords.incomplete_epw_categories.keys())}")
#
#     # The preview will show both complete and incomplete files
#     workflow_keywords.preview_rename_plan(
#         final_output_dir='./final_results_keywords',
#         output_filename_pattern='{city}_{uhi}_{ssp_full_name}_{year}',
#         scenario_mapping={'ssp585': 'SSP5-8.5'}
#     )
#
#     # When previewing the incomplete file, you will see an error because the
#     # placeholder '{uhi}' is missing from its mapped data. This is the
#     # desired behavior, as it alerts the user to the problem.