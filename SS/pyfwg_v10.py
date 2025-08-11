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

        - If `input_filename_pattern` is provided, it's used to extract raw values,
          which are then normalized using `keyword_mapping` if available.
        - If only `keyword_mapping` is provided, it searches the entire filename for
          keywords to assign categories.
        """
        logging.info("--- Step 1: Mapping categories from filenames ---")

        if not input_filename_pattern and not keyword_mapping:
            raise ValueError("You must provide at least one mapping method: 'input_filename_pattern' or 'keyword_mapping'.")

        self.inputs['epw_files'] = epw_files
        self.epw_categories, self.incomplete_epw_categories = {}, {}

        for epw_path in epw_files:
            if not os.path.exists(epw_path):
                logging.warning(f"EPW file not found, skipping: {epw_path}");
                continue

            file_categories = {}
            epw_base_name = os.path.splitext(os.path.basename(epw_path))[0]

            if input_filename_pattern:
                # --- Mode 1: Pattern Extraction followed by Normalization ---
                match = re.search(input_filename_pattern, epw_base_name)
                if not match:
                    logging.warning(f"Pattern did not match '{epw_base_name}'. Skipping.");
                    continue

                raw_values = match.groupdict()
                normalized_values = {}

                for category, raw_value in raw_values.items():
                    if raw_value is None: continue  # Skip optional, non-matching groups

                    final_value = raw_value  # Default to the raw value
                    # If mapping is provided, try to normalize the raw value
                    if keyword_mapping and category in keyword_mapping:
                        for mapped_val, keywords in keyword_mapping[category].items():
                            if raw_value.lower() in [k.lower() for k in keywords]:
                                final_value = mapped_val
                                break
                    normalized_values[category] = final_value
                file_categories = normalized_values

            elif keyword_mapping:
                # --- Mode 2: Keyword-only search (no pattern) ---
                epw_name_lower = os.path.basename(epw_path).lower()
                for category, rules in keyword_mapping.items():
                    for final_value, keywords in rules.items():
                        if any(keyword.lower() in epw_name_lower for keyword in keywords):
                            file_categories[category] = final_value
                            break

            if file_categories:
                logging.info(f"Mapped '{epw_path}': {file_categories}")
                # Completeness check is most relevant for keyword-only mode
                if keyword_mapping and not input_filename_pattern:
                    all_defined_categories = set(keyword_mapping.keys())
                    found_categories = set(file_categories.keys())
                    if len(found_categories) < len(all_defined_categories):
                        missing = all_defined_categories - found_categories
                        logging.warning(f"File '{os.path.basename(epw_path)}' is missing categories: {list(missing)}.")
                        self.incomplete_epw_categories[epw_path] = file_categories
                    else:
                        self.epw_categories[epw_path] = file_categories
                else:
                    self.epw_categories[epw_path] = file_categories
            else:
                logging.warning(f"Could not map any categories for '{epw_path}'. Skipping.")

        logging.info("Category mapping complete.")

    def preview_rename_plan(self,
                            final_output_dir: str,
                            output_filename_pattern: str,
                            scenario_mapping: Optional[Dict[str, str]] = None):
        # This method remains correct and does not need changes.
        if not self.epw_categories and not self.incomplete_epw_categories: raise RuntimeError("Please run map_categories() first. No files were successfully mapped.")
        logging.info("--- Step 2: Generating rename and move plan ---")
        self.inputs.update({'final_output_dir': final_output_dir, 'output_filename_pattern': output_filename_pattern, 'scenario_mapping': scenario_mapping or {}})
        self.rename_plan = {}
        all_mapped_files = {**self.epw_categories, **self.incomplete_epw_categories}
        required_placeholders = set(re.findall(r'{(.*?)}', output_filename_pattern))
        auto_placeholders = {'scenario', 'ssp_full_name', 'year'}
        required_from_mapping = required_placeholders - auto_placeholders
        print("\n" + "=" * 60 + "\n          MORPHING AND RENAMING PREVIEW\n" + "=" * 60)
        print(f"\nFinal Output Directory: {os.path.abspath(final_output_dir)}")
        for epw_path, mapped_data in all_mapped_files.items():
            is_incomplete = epw_path in self.incomplete_epw_categories
            status_flag = " [INCOMPLETE MAPPING]" if is_incomplete else ""
            print(f"\n  For input file: {os.path.basename(epw_path)}{status_flag}")
            missing_keys = required_from_mapping - set(mapped_data.keys())
            if missing_keys: print(f"    -> ERROR: This file is missing required categories for the output pattern: {list(missing_keys)}. Renaming will fail."); continue
            self.rename_plan[epw_path] = {}
            for year in ALL_POSSIBLE_YEARS:
                for scenario in ALL_POSSIBLE_SCENARIOS:
                    filename_data = {**mapped_data, 'scenario': scenario, 'ssp_full_name': self.inputs['scenario_mapping'].get(scenario, scenario), 'year': year}
                    new_base_name = output_filename_pattern.format(**filename_data)
                    final_epw_path = os.path.join(final_output_dir, new_base_name + ".epw")
                    generated_file_key = f"{scenario}_{year}.epw"
                    self.rename_plan[epw_path][generated_file_key] = final_epw_path
                    print(f"    -> Generated '{generated_file_key}' will be moved to: {os.path.abspath(final_epw_path)}")
        print("=" * 60 + "\nPreview complete. If this plan is correct, call execute_morphing().")

    def execute_morphing(self, *,
                         fwg_jar_path: str,
                         run_incomplete_files: bool = False,
                         delete_temp_files: bool = True,
                         temp_base_dir: str = './morphing_temp_results',
                         fwg_params: Optional[Dict[str, Any]] = None,
                         # --- Explicit FutureWeatherGenerator Arguments (Overrides fwg_params) ---
                         fwg_gcms: Optional[List[str]] = None, fwg_create_ensemble: bool = True,
                         fwg_winter_sd_shift: float = 0.0, fwg_summer_sd_shift: float = 0.0,
                         fwg_month_transition_hours: int = 72, fwg_use_multithreading: bool = True,
                         fwg_interpolation_method_id: int = 0, fwg_limit_variables: bool = True,
                         fwg_solar_hour_adjustment: int = 1, fwg_diffuse_irradiation_model: int = 1,
                         fwg_uhi_options: str = "1:14:1"):
        # This method remains correct and does not need changes.
        if not self.rename_plan: raise RuntimeError("Please run preview_rename_plan() to set up the output before executing.")
        logging.info("--- Step 3: Executing morphing workflow ---")
        final_fwg_params = fwg_params.copy() if fwg_params else {}
        overrides = {'gcms': fwg_gcms, 'create_ensemble': fwg_create_ensemble, 'winter_sd_shift': fwg_winter_sd_shift, 'summer_sd_shift': fwg_summer_sd_shift,
                     'month_transition_hours': fwg_month_transition_hours, 'use_multithreading': fwg_use_multithreading, 'interpolation_method_id': fwg_interpolation_method_id,
                     'limit_variables': fwg_limit_variables, 'solar_hour_adjustment': fwg_solar_hour_adjustment, 'diffuse_irradiation_model': fwg_diffuse_irradiation_model,
                     'uhi_options': fwg_uhi_options}
        final_fwg_params.update(overrides)
        self.inputs.update({'fwg_jar_path': fwg_jar_path, 'fwg_params': final_fwg_params, 'delete_temp_files': delete_temp_files, 'temp_base_dir': temp_base_dir})
        files_to_process = list(self.epw_categories.keys())
        if run_incomplete_files:
            logging.info("Processing both complete and incomplete files."); files_to_process.extend(self.incomplete_epw_categories.keys())
        else:
            logging.info("Processing only completely mapped files. Incomplete files will be skipped.")
        os.makedirs(self.inputs['final_output_dir'], exist_ok=True)
        os.makedirs(temp_base_dir, exist_ok=True)
        for epw_path in files_to_process:
            if epw_path not in self.rename_plan: logging.warning(f"Skipping '{os.path.basename(epw_path)}' as it had errors during the preview stage."); continue
            temp_epw_output_dir = os.path.join(temp_base_dir, os.path.splitext(os.path.basename(epw_path))[0])
            os.makedirs(temp_epw_output_dir, exist_ok=True)
            success = self._execute_single_morph(epw_path, temp_epw_output_dir)
            if success:
                self._process_generated_files(epw_path, temp_epw_output_dir)
                if delete_temp_files: shutil.rmtree(temp_epw_output_dir)
        logging.info("Morphing workflow finished.")

    def _execute_single_morph(self, epw_path: str, temp_output_dir: str) -> bool:
        # This private method remains correct and does not need changes.
        params = self.inputs['fwg_params']
        command = ['java', '-cp', self.inputs['fwg_jar_path'], 'futureweathergenerator.Morph', os.path.abspath(epw_path), ",".join(params.get('gcms') or DEFAULT_GCMS),
                   '1' if params.get('create_ensemble') else '0', f"{params.get('winter_sd_shift')}:{params.get('summer_sd_shift')}", str(params.get('month_transition_hours')),
                   os.path.abspath(temp_output_dir) + os.sep, str(params.get('use_multithreading')).lower(), str(params.get('interpolation_method_id')), str(params.get('limit_variables')).lower(),
                   str(params.get('solar_hour_adjustment')), str(params.get('diffuse_irradiation_model')), params.get('uhi_options')]
        logging.info(f"Executing command for {os.path.basename(epw_path)}")
        try:
            subprocess.run(command, capture_output=True, text=True, check=True, timeout=600)
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error morphing {os.path.basename(epw_path)}: {e.stderr}")
            return False

    def _process_generated_files(self, source_epw_path: str, temp_dir: str):
        # This private method remains correct and does not need changes.
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


