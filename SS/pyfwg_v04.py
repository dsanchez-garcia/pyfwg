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
    Manages the EPW morphing process in a controlled, step-by-step manner,
    encapsulating the configuration and state at each stage.
    """

    def __init__(self):
        """
        Initializes the workflow. All configuration is provided via methods.
        """
        self.inputs: Dict[str, Any] = {}
        self.epw_categories: Dict[str, Dict[str, str]] = {}
        self.rename_plan: Dict[str, Dict[str, str]] = {}

    def map_categories(self,
                       epw_files: List[str],
                       input_filename_pattern: str,
                       category_mapping: Optional[Dict[str, Dict[str, str]]] = None):
        """
        STEP 1: Parses input filenames to identify and map categories for each EPW file.
        This populates the `self.epw_categories` attribute.

        :param epw_files: List of paths to the input EPW files.
        :param input_filename_pattern: Regex pattern with named groups to parse filenames.
        :param category_mapping: Dictionary to normalize extracted category values.
        """
        logging.info("--- Step 1: Mapping categories from filenames ---")
        self.inputs['epw_files'] = epw_files
        self.inputs['input_filename_pattern'] = input_filename_pattern
        self.inputs['category_mapping'] = category_mapping or {}

        self.epw_categories = {}
        for epw_path in epw_files:
            if not os.path.exists(epw_path):
                logging.warning(f"EPW file not found, skipping: {epw_path}")
                continue

            epw_base_name = os.path.splitext(os.path.basename(epw_path))[0]
            match = re.search(input_filename_pattern, epw_base_name)
            if not match:
                logging.warning(f"Pattern did not match '{epw_base_name}'. Skipping.")
                continue

            parsed_data = match.groupdict()
            mapped_data = {
                cat: self.inputs['category_mapping'].get(cat, {}).get(val.lower(), val)
                for cat, val in parsed_data.items()
            }
            self.epw_categories[epw_path] = mapped_data
            logging.info(f"Mapped '{epw_path}': {mapped_data}")
        logging.info("Category mapping complete.")

    def preview_rename_plan(self,
                            final_output_dir: str,
                            output_filename_pattern: str,
                            scenarios: List[str],
                            years: List[int],
                            scenario_mapping: Optional[Dict[str, str]] = None):
        """
        STEP 2: Generates and displays a plan of how files will be renamed and moved.
        This populates the `self.rename_plan` attribute.

        :param final_output_dir: The directory where final files will be saved.
        :param output_filename_pattern: Template for the final filenames.
        :param scenarios: List of SSP scenarios to be generated (e.g., ['ssp245']).
        :param years: List of years to be generated (e.g., [2050]).
        :param scenario_mapping: Dictionary to map raw scenario names to full names.
        """
        if not self.epw_categories:
            raise RuntimeError("Please run map_categories() before creating a rename plan.")

        logging.info("--- Step 2: Generating rename and move plan ---")
        self.inputs['final_output_dir'] = final_output_dir
        self.inputs['output_filename_pattern'] = output_filename_pattern
        self.inputs['scenarios_to_generate'] = scenarios
        self.inputs['years_to_generate'] = years
        self.inputs['scenario_mapping'] = scenario_mapping or {}

        self.rename_plan = {}
        print("\n" + "=" * 60 + "\n          MORPHING AND RENAMING PREVIEW\n" + "=" * 60)
        print(f"\nFinal Output Directory: {os.path.abspath(final_output_dir)}")

        for epw_path, mapped_data in self.epw_categories.items():
            self.rename_plan[epw_path] = {}
            print(f"\n  For input file: {os.path.basename(epw_path)}")
            for year in years:
                for scenario in scenarios:
                    filename_data = {
                        **mapped_data,
                        'scenario': scenario,
                        'ssp_full_name': self.inputs['scenario_mapping'].get(scenario, scenario),
                        'year': year
                    }
                    new_base_name = output_filename_pattern.format(**filename_data)
                    final_epw_path = os.path.join(final_output_dir, new_base_name + ".epw")

                    # Key for lookup is the filename generated by FWG
                    generated_file_key = f"{scenario}_{year}.epw"
                    self.rename_plan[epw_path][generated_file_key] = final_epw_path

                    print(f"    -> Generated '{generated_file_key}' will be moved to: {os.path.abspath(final_epw_path)}")

        print("=" * 60 + "\nPreview complete. If this plan is correct, call execute_morphing().")

    def execute_morphing(self,
                         fwg_jar_path: str,
                         fwg_params: Optional[Dict[str, Any]] = None,
                         delete_temp_files: bool = True,
                         temp_base_dir: str = './morphing_temp_results',
                         **kwargs):
        """
        STEP 3: Executes the actual morphing process based on the approved plan.
        Individual keyword arguments for FWG will override those in `fwg_params`.
        """
        if not self.rename_plan:
            raise RuntimeError("Please run preview_rename_plan() to set up the output before executing.")

        logging.info("--- Step 3: Executing morphing workflow ---")
        # --- Handle FWG parameter merging and overriding ---
        base_params = fwg_params or {}
        base_params.update(kwargs)  # Individual kwargs override fwg_params

        self.inputs['fwg_jar_path'] = fwg_jar_path
        self.inputs['fwg_params'] = base_params
        self.inputs['delete_temp_files'] = delete_temp_files
        self.inputs['temp_base_dir'] = temp_base_dir

        os.makedirs(self.inputs['final_output_dir'], exist_ok=True)
        os.makedirs(temp_base_dir, exist_ok=True)

        for epw_path in self.epw_categories.keys():
            temp_epw_output_dir = os.path.join(temp_base_dir, os.path.splitext(os.path.basename(epw_path))[0])
            os.makedirs(temp_epw_output_dir, exist_ok=True)

            success = self._execute_single_morph(epw_path, temp_epw_output_dir)

            if success:
                self._process_generated_files(epw_path, temp_epw_output_dir)
                if delete_temp_files:
                    logging.info(f"Deleting temporary directory: {temp_epw_output_dir}")
                    shutil.rmtree(temp_epw_output_dir)

        logging.info("Morphing workflow finished.")

    def _execute_single_morph(self, epw_path: str, temp_output_dir: str) -> bool:
        """Private helper to call the Java tool for one file."""
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
        """Private helper to rename and move files for one morphing run."""
        logging.info(f"Processing generated files in: {temp_dir}")
        plan_for_this_epw = self.rename_plan.get(source_epw_path, {})

        for generated_file in os.listdir(temp_dir):
            destination_path = None
            if generated_file in plan_for_this_epw:
                destination_path = plan_for_this_epw[generated_file]
            # Also handle the .stat file
            elif generated_file.endswith(".stat") and generated_file.replace(".stat", ".epw") in plan_for_this_epw:
                epw_dest_path = plan_for_this_epw[generated_file.replace(".stat", ".epw")]
                destination_path = os.path.splitext(epw_dest_path)[0] + ".stat"

            if destination_path:
                source_path = os.path.join(temp_dir, generated_file)
                logging.info(f"Copying '{source_path}' to '{destination_path}'")
                shutil.copy2(source_path, destination_path)


## --- USAGE EXAMPLE ---
# if __name__ == '__main__':
    # --- STEP 0: Instantiate the workflow object ---
workflow = MorphingWorkflow()

jar_path = 'D:\\OneDrive - Universidad de Cádiz (uca.es)\\Programas\\FutureWeatherGenerator_v3.0.0.jar'
epw_files = ['epws/w_pattern/sevilla_uhi-tipo-1.epw', 'epws/w_pattern/MAD_uhi-tipo-2.epw']


## --- STEP 1: Map categories from source filenames ---
workflow.map_categories(
    epw_files=epw_files,
    # input_filename_pattern=r'(?P<city>.*?)_(?P<uhi_type>.*)',
    category_mapping={
        'city': {'sevilla': 'Seville', 'sev': 'Seville', 'madrid': 'Madrid', 'mad': 'Madrid'},
        'uhi_type': {'uhi-tipo-1': 'UHI-Type1', 'uhi-tipo-2': 'UHI-Type2'}
    }
)

## --- STEP 2: Define the output and preview the plan ---
workflow.preview_rename_plan(
    final_output_dir='./final_results_class_v2',
    output_filename_pattern='{city}_{ssp_full_name}_{year}_{uhi_type}',
    scenarios=['ssp245', 'ssp585'],
    years=[2050],
    scenario_mapping={
        'ssp126': 'SSP1-2.6', 'ssp245': 'SSP2-4.5',
        'ssp370': 'SSP3-7.0', 'ssp585': 'SSP5-8.5'
    }
)

## --- STEP 3: Execute the morphing process ---
# The user reviews the plan above and decides to proceed.
# Individual arguments here (like `create_ensemble=False`) would override fwg_params.
# Uncomment the following line to run the actual morphing:

workflow.execute_morphing(
    fwg_jar_path=jar_path,
    fwg_params={
        "gcms": ['CanESM5', 'MIROC6'],
        "create_ensemble": True # This will be used unless overridden below
    },
    # Example of overriding a parameter from the dictionary:
    # create_ensemble=False
)

logging.info("Script finished. Uncomment the final method call to execute the morphing.")