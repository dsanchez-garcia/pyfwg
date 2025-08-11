import os
import subprocess
import logging
from typing import List, Optional

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Default GCM list from the documentation for convenience
DEFAULT_GCMS = [
    'BCC_CSM2_MR', 'CanESM5', 'CanESM5_1', 'CanESM5_CanOE', 'CAS_ESM2_0',
    'CMCC_ESM2', 'CNRM_CM6_1', 'CNRM_CM6_1_HR', 'CNRM_ESM2_1', 'EC_Earth3',
    'EC_Earth3_Veg', 'EC_Earth3_Veg_LR', 'FGOALS_g3', 'GFDL_ESM4',
    'GISS_E2_1_G', 'GISS_E2_1_H', 'GISS_E2_2_G', 'IPSL_CM6A_LR',
    'MIROC_ES2H', 'MIROC_ES2L', 'MIROC6', 'MRI_ESM2_0', 'UKESM1_0_LL'
]


def generate_future_weather_positional(
        fwg_jar_path: str,
        epw_files: List[str],
        base_output_directory: str,
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
        uhi_options: Optional[str] = None  # e.g., "1:14:1"
):
    """
    Performs morphing of EPW files using the FutureWeatherGenerator tool
    with positional command-line arguments as per the official documentation.

    :param fwg_jar_path: Full path to the FutureWeatherGenerator .jar file.
    :param epw_files: A list of paths to the .epw files to be processed.
    :param base_output_directory: The main directory where the results will be saved.
    :param gcms: List of GCMs. If None, a default list from the docs is used.
    :param create_ensemble: If True, creates an ensemble (1). If False (0).
    :param winter_sd_shift: Standard deviation shift for winter peak month (-2 to 2).
    :param summer_sd_shift: Standard deviation shift for summer peak month (-2 to 2).
    :param month_transition_hours: Hours to smooth the transition between months (0-336).
    :param use_multithreading: Use multithread computation ('true' or 'false').
    :param interpolation_method_id: Grid method: 0 (inv dist), 1 (avg 4), 2 (nearest).
    :param limit_variables: Bound variables to physical limits ('true' or 'false').
    :param solar_hour_adjustment: 0 (None), 1 (ByMonth), 2 (ByDay).
    :param diffuse_irradiation_model: 0 (Ridley), 1 (Engerer), 2 (Paulescu).
    :param uhi_options: String for UHI settings, e.g., "1:14:1". If None, this argument is omitted.
    """
    if not os.path.exists(fwg_jar_path):
        logging.error(f"FutureWeatherGenerator .jar file not found at: {fwg_jar_path}")
        return

    os.makedirs(base_output_directory, exist_ok=True)

    # Use the default GCM list if none is provided
    if gcms is None:
        gcm_string = ",".join(DEFAULT_GCMS)
    else:
        gcm_string = ",".join(gcms)

    for epw_path in epw_files:
        if not os.path.exists(epw_path):
            logging.warning(f"EPW file not found, skipping: {epw_path}")
            continue

        epw_base_name = os.path.splitext(os.path.basename(epw_path))[0]
        epw_output_directory = os.path.join(base_output_directory, epw_base_name)
        os.makedirs(epw_output_directory, exist_ok=True)

        # The documentation specifies the output path must end with a separator.
        output_folder_formatted = os.path.abspath(epw_output_directory) + os.sep

        logging.info(f"Processing file: {epw_path}")
        logging.info(f"Results will be saved in: {epw_output_directory}")

        # --- Command Construction (Positional) ---
        # This now follows the documentation's java -cp structure exactly.
        command = [
            'java',
            '-cp',  # <--- CHANGED
            fwg_jar_path,
            'futureweathergenerator.Morph',  # <--- CHANGED

            # %epw_path%
            os.path.abspath(epw_path),
            # %gcm_model%
            gcm_string,
            # %ensemble% (0 or 1)
            '1' if create_ensemble else '0',
            # %winter_sd_shift%:%summer_sd_shift%
            f"{winter_sd_shift}:{summer_sd_shift}",
            # %month_transition_hours%
            str(month_transition_hours),
            # %output_folder%
            output_folder_formatted,
            # %do_multithred_computation% (true or false)
            str(use_multithreading).lower(),
            # %interpolation_method_id% (0, 1, or 2)
            str(interpolation_method_id),
            # %do_limit_variables% (true or false)
            str(limit_variables).lower(),
            # %solar_hour_adjustment_option%
            str(solar_hour_adjustment),
            # %diffuse_irradiation_model_option%
            str(diffuse_irradiation_model)
        ]

        # Add UHI options only if specified
        if uhi_options:
            command.append(uhi_options)

        # --- Process Execution ---
        logging.info(f"Executing command: {' '.join(command)}")
        try:
            # Use shell=True on Windows if you encounter issues with long commands,
            # but a list of args is generally safer.
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=600  # 10-minute timeout for the morphing process
            )
            logging.info(f"Process output for {epw_base_name}:\n{result.stdout}")
            logging.info(f"Successfully processed {epw_base_name}.")

        except FileNotFoundError:
            logging.error("Error: 'java' not found. Ensure Java is installed and in the system's PATH.")
            break
        except subprocess.TimeoutExpired as e:
            logging.error(f"Timeout expired for {epw_base_name}. Process took too long.")
            logging.error(f"STDOUT: {e.stdout}")
            logging.error(f"STDERR: {e.stderr}")
        except subprocess.CalledProcessError as e:
            logging.error(f"An error occurred while morphing {epw_base_name}.")
            logging.error(f"Exit Code: {e.returncode}")
            logging.error(f"Standard Output:\n{e.stdout}")
            logging.error(f"Standard Error:\n{e.stderr}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")


# --- Example of Use ---
if __name__ == '__main__':
    # --- CONFIGURATION PARAMETERS ---
    # 1. Path to the FutureWeatherGenerator .jar file (use your actual path)
    jar_path = 'D:\\OneDrive - Universidad de Cádiz (uca.es)\\Programas\\FutureWeatherGenerator_v3.0.0.jar'

    # 2. List of EPW files to process
    epw_files_to_process = [
        'Seville_Present.epw',
    ]

    # 3. Directory where all results will be saved
    results_directory = './morphing_results'

    # --- FUNCTION CALL ---
    # Now we call the new function that uses positional arguments
    generate_future_weather_positional(
        fwg_jar_path=jar_path,
        epw_files=epw_files_to_process,
        base_output_directory=results_directory,
        # The following parameters use the defaults from the documentation's batch script example
        # You can override any of them here if you need to.
        gcms=None,  # Use the default list
        create_ensemble=True,
        winter_sd_shift=0.0,
        summer_sd_shift=0.0,
        month_transition_hours=72,
        use_multithreading=True,
        interpolation_method_id=0,
        limit_variables=True,
        solar_hour_adjustment=1,
        diffuse_irradiation_model=1,
        uhi_options=None  # Set to "1:14:1" for example, if you need UHI
    )