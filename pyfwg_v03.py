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
    Manages the entire EPW morphing process in a step-by-step manner.

    This class allows for analyzing filenames, previewing the results,
    and then executing the heavy computation, giving the user full control
    and visibility before any changes are made.
    """

    def __init__(self,
                 fwg_jar_path: str,
                 epw_files: List[str],
                 fwg_params: Dict[str, Any],
                 input_filename_pattern: str,
                 category_mapping: Optional[Dict[str, Dict[str, str]]] = None,
                 scenario_mapping: Optional[Dict[str, str]] = None,
                 delete_temp_files: bool = True,
                 temp_base_dir: str = './morphing_temp_results'):
        """
        Initializes the workflow with all necessary configuration.
        """
        if not os.path.exists(fwg_jar_path):
            raise FileNotFoundError(f"FWG .jar file not found at: {fwg_jar_path}")

        self.fwg_jar_path = fwg_jar_path
        self.epw_files = epw_files
        self.fwg_params = fwg_params
        self.input_filename_pattern = input_filename_pattern
        self.category_mapping = category_mapping or {}
        self.scenario_mapping = scenario_mapping or {}
        self.delete_temp_files = delete_temp_files
        self.temp_base_dir = temp_base_dir

        # --- State attributes to be populated by the workflow steps ---
        self._parsed_files: List[Dict[str, Any]] = []
        self._rename_plan: Dict[str, List[str]] = {}
        self.final_output_dir: Optional[str] = None
        self.output_filename_pattern: Optional[str] = None

    def analyze_files(self):
        """
        STEP 1: Parses the input filenames based on the provided pattern
        and normalizes the data using the mapping dictionaries.
        """
        logging.info("--- Step 1: Analyzing input filenames ---")
        self._parsed_files = []
        for epw_path in self.epw_files:
            if not os.path.exists(epw_path):
                logging.warning(f"EPW file not found, skipping: {epw_path}")
                continue

            epw_name = os.path.basename(epw_path)
            epw_base_name = os.path.splitext(epw_name)[0]

            match = re.search(self.input_filename_pattern, epw_base_name)
            if not match:
                logging.warning(f"Pattern did not match '{epw_name}'. Skipping this file.")
                continue

            parsed_data = match.groupdict()
            mapped_data = {
                cat: self.category_mapping.get(cat, {}).get(val.lower(), val)
                for cat, val in parsed_data.items()
            }

            self._parsed_files.append({
                "source_path": epw_path,
                "base_name": epw_base_name,
                "mapped_data": mapped_data
            })
            logging.info(f"Successfully parsed '{epw_name}': {mapped_data}")
        logging.info("File analysis complete.")

    def preview_rename_plan(self, final_output_dir: str, output_filename_pattern: str):
        """
        STEP 2: Generates and displays a plan of how files will be renamed
        and where they will be moved, without executing the morphing.
        """
        if not self._parsed_files:
            raise RuntimeError("Please run analyze_files() before creating a rename plan.")

        logging.info("--- Step 2: Generating rename and move plan ---")
        self.final_output_dir = final_output_dir
        self.output_filename_pattern = output_filename_pattern
        self._rename_plan = {}

        print("\n" + "=" * 50)
        print("          MORPHING AND RENAMING PREVIEW")
        print("=" * 50)
        print(f"\nFinal Output Directory: {os.path.abspath(self.final_output_dir)}")

        scenarios_to_generate = self.fwg_params.get('scenarios', ['ssp126', 'ssp245', 'ssp370', 'ssp585'])
        years_to_generate = self.fwg_params.get('years', [2050, 2080])

        for file_info in self._parsed_files:
            source_name = os.path.basename(file_info['source_path'])
            self._rename_plan[source_name] = []
            print(f"\n  For input file: {source_name}")

            for year in years_to_generate:
                for scenario in scenarios_to_generate:
                    filename_data = file_info['mapped_data'].copy()
                    filename_data['scenario'] = scenario
                    filename_data['ssp_full_name'] = self.scenario_mapping.get(scenario, scenario)
                    filename_data['year'] = year

                    new_base_name = self.output_filename_pattern.format(**filename_data)
                    final_epw_path = os.path.join(self.final_output_dir, new_base_name + ".epw")
                    self._rename_plan[source_name].append(final_epw_path)

                    print(f"    -> Will be renamed and moved to: {os.path.abspath(final_epw_path)}")

        print("=" * 50)
        print("Preview complete. If this plan is correct, call execute_morphing().")

    def execute_morphing(self):
        """
        STEP 3: Executes the actual morphing process based on the approved plan.
        This is the long-running, computational step.
        """
        if not self._rename_plan:
            raise RuntimeError("Please run preview_rename_plan() to set up the output before executing.")

        logging.info("--- Step 3: Executing morphing workflow ---")
        os.makedirs(self.final_output_dir, exist_ok=True)
        os.makedirs(self.temp_base_dir, exist_ok=True)

        for file_info in self._parsed_files:
            temp_epw_output_dir = os.path.join(self.temp_base_dir, file_info['base_name'])
            os.makedirs(temp_epw_output_dir, exist_ok=True)

            success = self._execute_single_morph(
                epw_path=file_info['source_path'],
                temp_output_dir=temp_epw_output_dir
            )

            if not success:
                logging.error(f"Morphing failed for {file_info['base_name']}. Skipping file processing.")
                continue

            self._process_generated_files(temp_epw_output_dir, file_info['mapped_data'])

            if self.delete_temp_files:
                logging.info(f"Deleting temporary directory: {temp_epw_output_dir}")
                shutil.rmtree(temp_epw_output_dir)

        logging.info("Morphing workflow finished.")

    def _execute_single_morph(self, epw_path: str, temp_output_dir: str) -> bool:
        """Private helper to call the Java tool for one file."""
        gcm_string = ",".join(self.fwg_params.get('gcms', DEFAULT_GCMS))
        output_folder_formatted = os.path.abspath(temp_output_dir) + os.sep

        command = [
            'java', '-cp', self.fwg_jar_path, 'futureweathergenerator.Morph',
            os.path.abspath(epw_path), gcm_string,
            '1' if self.fwg_params.get('create_ensemble', True) else '0',
            f"{self.fwg_params.get('winter_sd_shift', 0.0)}:{self.fwg_params.get('summer_sd_shift', 0.0)}",
            str(self.fwg_params.get('month_transition_hours', 72)),
            output_folder_formatted,
            str(self.fwg_params.get('use_multithreading', True)).lower(),
            str(self.fwg_params.get('interpolation_method_id', 0)),
            str(self.fwg_params.get('limit_variables', True)).lower(),
            str(self.fwg_params.get('solar_hour_adjustment', 1)),
            str(self.fwg_params.get('diffuse_irradiation_model', 1)),
            self.fwg_params.get('uhi_options', "1:14:1")
        ]

        logging.info(f"Executing command for {os.path.basename(epw_path)}")
        try:
            subprocess.run(command, capture_output=True, text=True, check=True, timeout=600)
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"An error occurred while morphing {os.path.basename(epw_path)}.")
            logging.error(f"Exit Code: {e.returncode}\nStandard Output:\n{e.stdout}\nStandard Error:\n{e.stderr}")
            return False

    def _process_generated_files(self, temp_dir: str, mapped_data: Dict[str, str]):
        """Private helper to rename and move files for one morphing run."""
        logging.info(f"Processing generated files in: {temp_dir}")
        for generated_file in os.listdir(temp_dir):
            scenario_match = re.search(r'(ssp\d{3})_(\d{4})', generated_file)
            if not scenario_match: continue

            file_ext = ".epw" if generated_file.endswith(".epw") else ".stat" if generated_file.endswith(".stat") else None
            if file_ext is None: continue

            raw_scenario, year = scenario_match.groups()
            mapped_scenario = self.scenario_mapping.get(raw_scenario, raw_scenario)

            filename_data = {**mapped_data, 'scenario': raw_scenario, 'ssp_full_name': mapped_scenario, 'year': year}
            new_filename = self.output_filename_pattern.format(**filename_data) + file_ext

            source_path = os.path.join(temp_dir, generated_file)
            destination_path = os.path.join(self.final_output_dir, new_filename)

            logging.info(f"Copying '{source_path}' to '{destination_path}'")
            shutil.copy2(source_path, destination_path)


## --- USAGE EXAMPLE ---
# if __name__ == '__main__':
    # --- CONFIGURATION PARAMETERS ---
jar_path = 'D:\\OneDrive - Universidad de Cádiz (uca.es)\\Programas\\FutureWeatherGenerator_v3.0.0.jar'
epw_files = ['epws/w_pattern/sevilla_uhi-tipo-1.epw', 'epws/w_pattern/MAD_uhi-tipo-2.epw']

fwg_parameters = {
    # "scenarios": ['ssp245', 'ssp585'],
    # "years": [2050],
    "gcms": ['CanESM5', 'MIROC6'],
    "create_ensemble": True,
}

## --- STEP 0: Instantiate the workflow ---
workflow = MorphingWorkflow(
    fwg_jar_path=jar_path,
    epw_files=epw_files,
    fwg_params=fwg_parameters,
    input_filename_pattern=r'(?P<city>.*?)_(?P<uhi_type>.*)',
    category_mapping={
        'city': {'sevilla': 'Seville', 'sev': 'Seville', 'madrid': 'Madrid', 'mad': 'Madrid'},
        'uhi_type': {'uhi-tipo-1': 'UHI-Type1', 'uhi-tipo-2': 'UHI-Type2'}
    },
    scenario_mapping={
        'ssp126': 'SSP1-2.6', 'ssp245': 'SSP2-4.5',
        'ssp370': 'SSP3-7.0', 'ssp585': 'SSP5-8.5'
    }
)

## --- STEP 1: Analyze the source filenames ---
workflow.analyze_files()

# --- STEP 2: Define the output and preview the plan ---
# The user defines the final destination and filename format here.
workflow.preview_rename_plan(
    final_output_dir='./final_results_from_class',
    output_filename_pattern='{city}_{ssp_full_name}_{year}_{uhi_type}'
)

# At this point, the script pauses. The user reviews the printed plan.
# If the plan is correct, they can trigger the final step.
# In a real application, this could be an input() prompt.

# --- STEP 3: Execute the morphing process ---
# This is only called after the user is satisfied with the preview.
# Uncomment the following line to run the actual morphing:
# workflow.execute_morphing()

logging.info("Script finished. Uncomment the final line to execute the morphing.")