import os
import re
import shutil
import subprocess
import logging
from typing import List, Optional, Dict

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Default GCMs List ---
# This list is taken from the FutureWeatherGenerator documentation for convenience.
DEFAULT_GCMS = [
    'BCC_CSM2_MR', 'CanESM5', 'CanESM5_1', 'CanESM5_CanOE', 'CAS_ESM2_0',
    'CMCC_ESM2', 'CNRM_CM6_1', 'CNRM_CM6_1_HR', 'CNRM_ESM2_1', 'EC_Earth3',
    'EC_Earth3_Veg', 'EC_Earth3_Veg_LR', 'FGOALS_g3', 'GFDL_ESM4',
    'GISS_E2_1_G', 'GISS_E2_1_H', 'GISS_E2_2_G', 'IPSL_CM6A_LR',
    'MIROC_ES2H', 'MIROC_ES2L', 'MIROC6', 'MRI_ESM2_0', 'UKESM1_0_LL'
]


def generate_future_weather_positional(
        fwg_jar_path: str,
        epw_path: str,
        temp_output_dir: str,
        gcms: Optional[List[str]] = None,
        create_ensemble: bool = True,
        winter_sd_shift: float = 0.0,
        summer_sd_shift: float = 0.0,
        month_transition_hours: int = 72,
        use_multithreading: bool = True,
        interpolation_method_id: int = 0,
        limit_variables: bool = True,
        solar_hour_adjustment: int = 1,
        diffuse_irradiation_model: int = 1,
        uhi_options: str = "1:14:1"
):
    """
    Executes the morphing for a SINGLE EPW file using positional arguments.
    This function is called by the main workflow orchestrator.
    """
    gcm_string = ",".join(gcms if gcms is not None else DEFAULT_GCMS)

    # The documentation specifies the output path must end with a separator.
    output_folder_formatted = os.path.abspath(temp_output_dir) + os.sep

    command = [
        'java', '-cp', fwg_jar_path, 'futureweathergenerator.Morph',
        os.path.abspath(epw_path),
        gcm_string,
        '1' if create_ensemble else '0',
        f"{winter_sd_shift}:{summer_sd_shift}",
        str(month_transition_hours),
        output_folder_formatted,
        str(use_multithreading).lower(),
        str(interpolation_method_id),
        str(limit_variables).lower(),
        str(solar_hour_adjustment),
        str(diffuse_irradiation_model),
        uhi_options
    ]

    logging.info(f"Executing command for {os.path.basename(epw_path)}: {' '.join(command)}")
    try:
        subprocess.run(
            command, capture_output=True, text=True, check=True, timeout=600
        )
        logging.info(f"Successfully processed {os.path.basename(epw_path)}.")
        return True  # Indicate success
    except subprocess.CalledProcessError as e:
        logging.error(f"An error occurred while morphing {os.path.basename(epw_path)}.")
        logging.error(f"Exit Code: {e.returncode}\nStandard Output:\n{e.stdout}\nStandard Error:\n{e.stderr}")
        return False  # Indicate failure


def run_morphing_workflow(
        fwg_jar_path: str,
        epw_files: List[str],
        fwg_params: dict,
        input_filename_pattern: str,
        final_output_dir: str,
        output_filename_pattern: str,
        category_mapping: Optional[Dict[str, Dict[str, str]]] = None,
        scenario_mapping: Optional[Dict[str, str]] = None,
        delete_temp_files: bool = True,
        temp_base_dir: str = './morphing_temp_results'
):
    """
    Orchestrates the entire morphing workflow:
    1. Parses input filenames to extract metadata.
    2. Normalizes the metadata using a category map.
    3. Executes the morphing for each file into a temporary directory.
    4. Renames and copies the resulting files to the final directory.
    5. Optionally, cleans up the temporary files.

    :param fwg_jar_path: Path to the FutureWeatherGenerator .jar file.
    :param epw_files: List of paths to the input EPW files.
    :param fwg_params: Dictionary containing the parameters for the `generate_future_weather_positional` function.
    :param input_filename_pattern: Regular Expression (regex) pattern to parse the input filenames.
                                   It must use named capture groups (e.g., '(?P<city>.*?)_').
    :param final_output_dir: The directory where the final, renamed files will be saved.
    :param output_filename_pattern: A template string for the output filename.
                                     It uses braces for placeholders (e.g., '{city}_{ssp_full_name}_{year}.epw').
    :param category_mapping: A dictionary to normalize the categories extracted from the filenames.
    :param scenario_mapping: A dictionary to map raw scenario names (e.g., 'ssp126')
                             to descriptive names (e.g., 'SSP1-2.6').
    :param delete_temp_files: If True, deletes the temporary directories after processing.
    :param temp_base_dir: The base directory to store the temporary morphing results.
    """
    if not os.path.exists(fwg_jar_path):
        logging.error(f"FWG .jar file not found at: {fwg_jar_path}")
        return

    os.makedirs(final_output_dir, exist_ok=True)
    os.makedirs(temp_base_dir, exist_ok=True)

    # Initialize mapping dictionaries if they are None to prevent errors
    category_mapping = category_mapping or {}
    scenario_mapping = scenario_mapping or {}

    for epw_path in epw_files:
        if not os.path.exists(epw_path):
            logging.warning(f"EPW file not found, skipping: {epw_path}")
            continue

        epw_name = os.path.basename(epw_path)
        epw_base_name = os.path.splitext(epw_name)[0]

        # 1. Parse the input filename
        match = re.search(input_filename_pattern, epw_base_name)
        if not match:
            logging.warning(f"Pattern did not match '{epw_name}'. Skipping this file.")
            continue

        parsed_data = match.groupdict()
        logging.info(f"Data parsed from '{epw_name}': {parsed_data}")

        # 2. Normalize categories using the map
        mapped_data = {
            category: category_mapping.get(category, {}).get(value.lower(), value)
            for category, value in parsed_data.items()
        }
        logging.info(f"Mapped data: {mapped_data}")

        # 3. Execute the morphing in a temporary directory
        temp_epw_output_dir = os.path.join(temp_base_dir, epw_base_name)
        os.makedirs(temp_epw_output_dir, exist_ok=True)

        success = generate_future_weather_positional(
            fwg_jar_path=fwg_jar_path,
            epw_path=epw_path,
            temp_output_dir=temp_epw_output_dir,
            **fwg_params
        )

        if not success:
            logging.error(f"Morphing failed for {epw_name}. Output files will not be processed.")
            continue

        # 4. Rename and move the generated files
        logging.info(f"Processing generated files in: {temp_epw_output_dir}")
        for generated_file in os.listdir(temp_epw_output_dir):
            # Extract scenario and year from the generated file (e.g., 'ssp245_2050.epw')
            scenario_match = re.search(r'(ssp\d{3})_(\d{4})', generated_file)
            if not scenario_match:
                continue

            file_extension = ".epw" if generated_file.endswith(".epw") else ".stat" if generated_file.endswith(".stat") else None
            if file_extension is None:
                continue

            # Extract raw data
            raw_scenario = scenario_match.group(1)
            year = scenario_match.group(2)

            # Map the scenario name to the desired format
            mapped_scenario_name = scenario_mapping.get(raw_scenario, raw_scenario)

            # Combine all available data for the new filename
            filename_data = mapped_data.copy()
            filename_data['scenario'] = raw_scenario
            filename_data['ssp_full_name'] = mapped_scenario_name
            filename_data['year'] = year

            # Create the new filename using the template
            new_filename = output_filename_pattern.format(**filename_data) + file_extension

            source_path = os.path.join(temp_epw_output_dir, generated_file)
            destination_path = os.path.join(final_output_dir, new_filename)

            logging.info(f"Copying '{source_path}' to '{destination_path}'")
            shutil.copy2(source_path, destination_path)

        # 5. Clean up temporary files
        if delete_temp_files:
            logging.info(f"Deleting temporary directory: {temp_epw_output_dir}")
            shutil.rmtree(temp_epw_output_dir)


# --- USAGE EXAMPLE ---
if __name__ == '__main__':
    # --- CONFIGURATION PARAMETERS ---

    # 1. Path to the FutureWeatherGenerator .jar file
    jar_path = 'D:\\Path\\To\\Your\\FutureWeatherGenerator_v3.0.0.jar'

    # 2. List of EPW files to process
    epw_files_to_process = [
        'sevilla_uhi-tipo-1.epw',
        'madrid_uhi-tipo-1.epw',
        'SEV_uhi-tipo-2.epw',
        'MAD_uhi-tipo-2.epw'
    ]
    # (Ensure these files exist in the script's directory for testing)

    # 3. Pattern to parse the input filenames
    # Use named capture groups: (?P<category_name>...)
    input_pattern = r'(?P<city>.*?)_(?P<uhi_type>.*)'

    # 4. Map to normalize the extracted categories
    # The outer key is the category name from the pattern.
    # The inner search is case-insensitive.
    normalization_map = {
        'city': {
            'sevilla': 'Seville',
            'sev': 'Seville',
            'madrid': 'Madrid',
            'mad': 'Madrid'
        },
        'uhi_type': {
            'uhi-tipo-1': 'UHI-Type1',
            'uhi-tipo-2': 'UHI-Type2'
        }
    }

    # 5. Map for the scenario names
    # This defines how to translate file names to descriptive names.
    scenario_map = {
        'ssp126': 'SSP1-2.6',
        'ssp245': 'SSP2-4.5',
        'ssp370': 'SSP3-7.0',
        'ssp585': 'SSP5-8.5'
    }

    # 6. Final directory for the processed files
    final_directory = './final_results'

    # 7. Pattern for the output filenames
    # You can now use {ssp_full_name} and {year}.
    output_pattern = '{city}_{ssp_full_name}_{year}_{uhi_type}'

    # 8. Parameters for the FutureWeatherGenerator tool
    # Grouped into a dictionary for clarity
    fwg_tool_params = {
        "gcms": ['CanESM5', 'MIROC6'],  # Using a shorter list for faster tests
        "create_ensemble": True,
        "month_transition_hours": 72,
        "interpolation_method_id": 0,
        # ... you can add any other FWG parameters here
    }

    # --- CALL THE WORKFLOW FUNCTION ---
    run_morphing_workflow(
        fwg_jar_path=jar_path,
        epw_files=epw_files_to_process,
        fwg_params=fwg_tool_params,
        input_filename_pattern=input_pattern,
        final_output_dir=final_directory,
        output_filename_pattern=output_pattern,
        category_mapping=normalization_map,
        scenario_mapping=scenario_map,
        delete_temp_files=True
    )