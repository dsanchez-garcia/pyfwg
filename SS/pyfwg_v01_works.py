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
        # --- CRITICAL CHANGE HERE ---
        # The UHI argument is no longer optional. It has a default value.
        uhi_options: str = "1:14:1"
):
    """
    Performs morphing of EPW files using the FutureWeatherGenerator tool
    with positional command-line arguments as per the official documentation.

    (Docstring updated to reflect the change in uhi_options)
    :param uhi_options: String for UHI settings, e.g., "1:14:1". This argument is
                        required by the tool. Defaults to the value from the
                        documentation's example batch script.
    """
    if not os.path.exists(fwg_jar_path):
        logging.error(f"FutureWeatherGenerator .jar file not found at: {fwg_jar_path}")
        return

    os.makedirs(base_output_directory, exist_ok=True)

    gcm_string = ",".join(gcms if gcms is not None else DEFAULT_GCMS)

    for epw_path in epw_files:
        if not os.path.exists(epw_path):
            logging.warning(f"EPW file not found, skipping: {epw_path}")
            continue

        epw_base_name = os.path.splitext(os.path.basename(epw_path))[0]
        epw_output_directory = os.path.join(base_output_directory, epw_base_name)
        os.makedirs(epw_output_directory, exist_ok=True)

        output_folder_formatted = os.path.abspath(epw_output_directory) + os.sep

        logging.info(f"Processing file: {epw_path}")
        logging.info(f"Results will be saved in: {epw_output_directory}")

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
            # --- CRITICAL CHANGE HERE ---
            # The UHI argument is now always appended.
            uhi_options
        ]

        logging.info(f"Executing command: {' '.join(command)}")
        try:
            result = subprocess.run(
                command,
                capture_output=True, text=True, check=True, timeout=600
            )
            logging.info(f"Process output for {epw_base_name}:\n{result.stdout}")
            logging.info(f"Successfully processed {epw_base_name}.")

        except FileNotFoundError:
            logging.error("Error: 'java' not found. Ensure Java is installed and in the system's PATH.")
            break
        except subprocess.TimeoutExpired as e:
            logging.error(f"Timeout expired for {epw_base_name}. Process took too long.")
            logging.error(f"STDOUT: {e.stdout}\nSTDERR: {e.stderr}")
        except subprocess.CalledProcessError as e:
            logging.error(f"An error occurred while morphing {epw_base_name}.")
            logging.error(f"Exit Code: {e.returncode}\nStandard Output:\n{e.stdout}\nStandard Error:\n{e.stderr}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")


# --- Example of Use ---
if __name__ == '__main__':
    jar_path = 'D:\\OneDrive - Universidad de Cádiz (uca.es)\\Programas\\FutureWeatherGenerator_v3.0.0.jar'
    epw_files_to_process = ['Seville_Present.epw']
    results_directory = './morphing_results'

    generate_future_weather_positional(
        fwg_jar_path=jar_path,
        epw_files=epw_files_to_process,
        base_output_directory=results_directory,
        # Default values, including the new default for uhi_options, will be used.
        # You can still override any of them here if needed, for example:
        # uhi_options="0:0:0"
    )