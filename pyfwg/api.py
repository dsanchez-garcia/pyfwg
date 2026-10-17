# pyfwg/api.py

import os
import shutil
import logging
import subprocess
import time
from typing import List, Union, Optional, Dict, Any

# Import the workflow classes to use them as an internal engine
from .workflow import (
    MorphingWorkflowGlobal, MorphingWorkflowEurope, MorphingWorkflowCordex,
    _generated_files_dir, _weather_file_extensions
)
# Import utility functions
from .utils import _robust_rmtree, check_lcz_availability

logger = logging.getLogger(__name__)


def _run_direct_morphing(workflow, output_dir: str) -> List[str]:
    """(Private) Runs a configured workflow and moves the generated files without renaming them.

    This is the shared engine of the simple API functions. For each EPW file,
    it validates the Local Climate Zones (if the UHI effect is enabled), runs
    the tool and moves the generated weather and .stat files of each future
    scenario to `output_dir` with the default filenames produced by the tool.

    Args:
        workflow: A workflow instance on which `configure_and_preview` has been run.
        output_dir (str): Directory where the generated files will be saved.

    Returns:
        List[str]: A list of absolute paths to the successfully created files.

    Raises:
        ValueError: If the configuration of the workflow is invalid.
    """
    # Block execution if the configuration was found to be invalid.
    if not workflow.is_config_valid:
        raise ValueError("FWG parameter validation failed. Please check the warnings in the log above "
                         "(if they are not shown, call pyfwg.enable_console_logging()).")

    # Create the final output directory if it doesn't exist.
    os.makedirs(output_dir, exist_ok=True)
    final_file_paths = []

    # Iterate through the definitive list of files to be processed.
    for epw_path in workflow.epws_to_be_morphed:
        # Create a unique temporary subdirectory for this specific EPW file.
        temp_epw_output_dir = os.path.join(workflow.inputs['temp_base_dir'], os.path.splitext(os.path.basename(epw_path))[0])
        os.makedirs(temp_epw_output_dir, exist_ok=True)

        # --- Pre-flight check for LCZ availability ---
        fwg_params = workflow.inputs['fwg_params']
        if fwg_params.get('add_uhi', False):
            logger.info(f"Validating LCZ availability for {os.path.basename(epw_path)}...")
            lcz_validation_result = check_lcz_availability(
                epw_path=epw_path,
                original_lcz=fwg_params.get('epw_original_lcz'),
                target_lcz=fwg_params.get('target_uhi_lcz'),
                fwg_jar_path=workflow.inputs['fwg_jar_path'],
                java_class_path_prefix=workflow.java_class_path_prefix,
                fwg_version=fwg_params.get('fwg_version')
            )
            # If validation fails, log the detailed error and skip this file.
            if lcz_validation_result is not True:
                logger.error(f"LCZ validation failed for '{os.path.basename(epw_path)}'. This file will be skipped.")
                if isinstance(lcz_validation_result, dict):
                    for error_message in lcz_validation_result.get("invalid_messages", []):
                        logger.error(error_message)
                    logger.error("The following LCZs are available for this location:")
                    for lcz in lcz_validation_result.get("available", []):
                        logger.error(f"- {lcz}")
                continue

        # Reuse the low-level execution method from the class.
        success = workflow._execute_single_morph(epw_path, temp_epw_output_dir)

        if success:
            # Implement simple file moving logic, as no custom renaming is needed.
            # FWG Engine distributions write the weather files to a 'weather' subfolder.
            generated_files_dir = _generated_files_dir(temp_epw_output_dir, workflow.inputs.get('fwg_cli_style'))
            extensions = _weather_file_extensions(fwg_params.get('output_type'))
            # Only the files of the planned scenarios and years (e.g., 'ssp245_2050') are
            # moved. Other weather files, such as the baseline processed by the FWG
            # Engine, remain in the temporary directory.
            scenario_keys = [os.path.splitext(key)[0] for key in workflow.rename_plan.get(epw_path, {})]
            for generated_file in os.listdir(generated_files_dir):
                # Skip the copy of the input EPW file made for the tool.
                if generated_file == os.path.basename(epw_path):
                    continue
                if scenario_keys and not any(key in generated_file for key in scenario_keys):
                    continue
                if generated_file.lower().endswith(extensions):
                    source_path = os.path.join(generated_files_dir, generated_file)
                    dest_path = os.path.join(output_dir, generated_file)
                    shutil.move(source_path, dest_path)
                    final_file_paths.append(os.path.abspath(dest_path))

            # Clean up the temporary directory if requested.
            if workflow.inputs['delete_temp_files']:
                _robust_rmtree(temp_epw_output_dir)

    return final_file_paths


# def morph_epw_global(*,
#                      epw_paths: Union[str, List[str]],
#                      fwg_jar_path: str,
#                      output_dir: str = './morphed_epws',
#                      delete_temp_files: bool = True,
#                      temp_base_dir: str = './morphing_temp_results',
#                      fwg_show_tool_output: bool = False,
#                      fwg_params: Optional[Dict[str, Any]] = None,
#                      # --- Explicit Future Weather Generator Arguments ---
#                      fwg_gcms: Optional[List[str]] = None,
#                      fwg_create_ensemble: bool = True,
#                      fwg_winter_sd_shift: float = 0.0,
#                      fwg_summer_sd_shift: float = 0.0,
#                      fwg_month_transition_hours: int = 72,
#                      fwg_use_multithreading: bool = True,
#                      fwg_interpolation_method_id: int = 0,
#                      fwg_limit_variables: bool = True,
#                      fwg_solar_hour_adjustment: int = 1,
#                      fwg_diffuse_irradiation_model: int = 1,
#                      fwg_add_uhi: bool = True,
#                      fwg_epw_original_lcz: int = 14,
#                      fwg_target_uhi_lcz: int = 1):
#     """Performs a direct, one-shot morphing using the GLOBAL Future Weather Generator tool.
#
#     This function provides a simple interface to the morphing process while
#     still allowing full customization of the Future Weather Generator tool. It
#     internally uses the `MorphingWorkflowGlobal` class to validate all
#     parameters before execution and runs the entire workflow in a single call.
#
#     The generated .epw and .stat files are saved directly to the output
#     directory using the default filenames produced by the FWG tool.
#
#     Args:
#         epw_paths (Union[str, List[str]]): A single path or a list of paths
#             to the EPW files to be processed.
#         fwg_jar_path (str): Path to the `FutureWeatherGenerator.jar` file.
#         output_dir (str, optional): Directory where the final morphed files
#             will be saved. Defaults to './morphed_epws'.
#         delete_temp_files (bool, optional): If True, temporary folders are
#             deleted after processing. Defaults to True.
#         temp_base_dir (str, optional): Base directory for temporary files.
#             Defaults to './morphing_temp_results'.
#         fwg_show_tool_output (bool, optional): If True, prints the FWG tool's
#             console output in real-time. Defaults to False.
#         fwg_params (Optional[Dict[str, Any]], optional): A dictionary for base
#             FWG parameters. Any explicit `fwg_` argument will override this.
#             Defaults to None.
#         fwg_gcms (Optional[List[str]], optional): List of GCMs to use.
#             If None, the tool's default list is used.
#         fwg_create_ensemble (bool, optional): If True, creates an ensemble.
#         fwg_winter_sd_shift (float, optional): Winter standard deviation shift.
#         fwg_summer_sd_shift (float, optional): Summer standard deviation shift.
#         fwg_month_transition_hours (int, optional): Hours for month transition.
#         fwg_use_multithreading (bool, optional): Use multithreading.
#         fwg_interpolation_method_id (int, optional): Interpolation method ID.
#         fwg_limit_variables (bool, optional): Limit variables to physical bounds.
#         fwg_solar_hour_adjustment (int, optional): Solar hour adjustment option.
#         fwg_diffuse_irradiation_model (int, optional): Diffuse irradiation model option.
#         fwg_add_uhi (bool, optional): Add UHI effect.
#         fwg_epw_original_lcz (int, optional): Original EPW LCZ.
#         fwg_target_uhi_lcz (int, optional): Target UHI LCZ.
#
#     Returns:
#         List[str]: A list of absolute paths to the successfully created .epw
#                    and .stat files.
#
#     Raises:
#         ValueError: If the provided FWG parameters fail validation.
#     """
#     logging.info("--- Starting Direct Global Morphing Process ---")
#
#     # Instantiate the corresponding workflow class to use as an engine.
#     workflow = MorphingWorkflowGlobal()
#
#     # Normalize the input to always be a list for consistent processing.
#     epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths
#
#     # Perform a simple pass-through mapping. This populates the workflow's
#     # internal list of files, which is required by the set_morphing_config step.
#     workflow.map_categories(
#         epw_files=epw_files,
#         keyword_mapping={'basename': {os.path.splitext(os.path.basename(p))[0]: p for p in epw_files}}
#     )
#
#     # Reuse the class's set_morphing_config method to validate all parameters
#     # and set up the internal state of the workflow instance.
#     workflow.set_morphing_config(
#         fwg_jar_path=fwg_jar_path,
#         run_incomplete_files=True,  # In the simple API, we always attempt to run all provided files.
#         delete_temp_files=delete_temp_files,
#         temp_base_dir=temp_base_dir,
#         fwg_show_tool_output=fwg_show_tool_output,
#         fwg_params=fwg_params,
#         fwg_gcms=fwg_gcms,
#         fwg_create_ensemble=fwg_create_ensemble,
#         fwg_winter_sd_shift=fwg_winter_sd_shift,
#         fwg_summer_sd_shift=fwg_summer_sd_shift,
#         fwg_month_transition_hours=fwg_month_transition_hours,
#         fwg_use_multithreading=fwg_use_multithreading,
#         fwg_interpolation_method_id=fwg_interpolation_method_id,
#         fwg_limit_variables=fwg_limit_variables,
#         fwg_solar_hour_adjustment=fwg_solar_hour_adjustment,
#         fwg_diffuse_irradiation_model=fwg_diffuse_irradiation_model,
#         fwg_add_uhi=fwg_add_uhi,
#         fwg_epw_original_lcz=fwg_epw_original_lcz,
#         fwg_target_uhi_lcz=fwg_target_uhi_lcz
#     )
#
#     # Block execution if the configuration was found to be invalid.
#     if not workflow.is_config_valid:
#         raise ValueError("FWG parameter validation failed. Please check the warnings in the log above.")
#
#     # Create the final output directory if it doesn't exist.
#     os.makedirs(output_dir, exist_ok=True)
#     final_file_paths = []
#
#     # Iterate through the definitive list of files to be processed.
#     for epw_path in workflow.epws_to_be_morphed:
#         # --- Pre-flight check for LCZ availability ---
#         fwg_params = workflow.inputs['fwg_params']
#         if fwg_params.get('add_uhi', False):
#             logging.info(f"Validating LCZ availability for {os.path.basename(epw_path)}...")
#             lcz_validation_result = check_lcz_availability(
#                 epw_path=epw_path,
#                 original_lcz=fwg_params.get('epw_original_lcz'),
#                 target_lcz=fwg_params.get('target_uhi_lcz'),
#                 fwg_jar_path=workflow.inputs['fwg_jar_path'],
#                 java_class_path_prefix='futureweathergenerator'
#             )
#             # If validation fails, log the detailed error and skip this file.
#             if lcz_validation_result is not True:
#                 logging.error(f"LCZ validation failed for '{os.path.basename(epw_path)}'. This file will be skipped.")
#                 if isinstance(lcz_validation_result, dict):
#                     for error_message in lcz_validation_result.get("invalid_messages", []):
#                         logging.error(error_message)
#                     logging.error("The following LCZs are available for this location:")
#                     for lcz in lcz_validation_result.get("available", []):
#                         logging.error(f"- {lcz}")
#                 continue
#
#         # Create a unique temporary subdirectory for this specific EPW file.
#         temp_epw_output_dir = os.path.join(workflow.inputs['temp_base_dir'], os.path.splitext(os.path.basename(epw_path))[0])
#         os.makedirs(temp_epw_output_dir, exist_ok=True)
#
#         # Reuse the low-level execution method from the class.
#         success = workflow._execute_single_morph(epw_path, temp_epw_output_dir)
#
#         if success:
#             # Implement simple file moving logic, as no renaming is needed.
#             for generated_file in os.listdir(temp_epw_output_dir):
#                 if generated_file.endswith((".epw", ".stat")):
#                     source_path = os.path.join(temp_epw_output_dir, generated_file)
#                     dest_path = os.path.join(output_dir, generated_file)
#                     shutil.move(source_path, dest_path)
#                     final_file_paths.append(os.path.abspath(dest_path))
#
#             # Clean up the temporary directory if requested.
#             if workflow.inputs['delete_temp_files']:
#                 _robust_rmtree(temp_epw_output_dir)
#
#     logging.info(f"Direct global morphing complete. {len(final_file_paths)} files created in {os.path.abspath(output_dir)}")
#     return final_file_paths


def morph_epw_global(*,
                     epw_paths: Union[str, List[str]],
                     fwg_jar_path: str,
                     output_dir: str = './morphed_epws',
                     delete_temp_files: bool = True,
                     temp_base_dir: str = './morphing_temp_results',
                     fwg_show_tool_output: bool = False,
                     fwg_params: Optional[Dict[str, Any]] = None,
                     # --- Explicit Future Weather Generator Arguments ---
                     fwg_gcms: Optional[List[str]] = None,
                     fwg_create_ensemble: Optional[bool] = None,
                     fwg_winter_sd_shift: Optional[float] = None,
                     fwg_summer_sd_shift: Optional[float] = None,
                     fwg_month_transition_hours: Optional[int] = None,
                     fwg_use_multithreading: Optional[bool] = None,
                     fwg_interpolation_method_id: Optional[Union[int, str]] = None,
                     fwg_limit_variables: Optional[bool] = None,
                     fwg_solar_hour_adjustment: Optional[Union[int, str]] = None,
                     fwg_diffuse_irradiation_model: Optional[Union[int, str]] = None,
                     fwg_add_uhi: Optional[bool] = None,
                     fwg_epw_original_lcz: Optional[int] = None,
                     fwg_target_uhi_lcz: Optional[int] = None,
                     fwg_output_type: Optional[str] = None,
                     fwg_version: Optional[Union[str, int]] = None,
                     # --- FWG Engine Arguments (Global v5+) ---
                     fwg_scenarios: Optional[List[str]] = None,
                     fwg_timeframes: Optional[List[Union[int, str]]] = None,
                     fwg_decomposition_method: Optional[str] = None,
                     fwg_illuminance_method: Optional[str] = None,
                     fwg_infrared_method: Optional[str] = None,
                     fwg_morphing_method: Optional[str] = None,
                     fwg_uncertainty_variant: Optional[str] = None,
                     fwg_uncertainty_sigma: Optional[float] = None,
                     fwg_output_profile: Optional[str] = None,
                     fwg_model_unzipped_folder: Optional[str] = None,
                     fwg_extra_args: Optional[Dict[str, Any]] = None):
    """Performs a direct, one-shot morphing using the GLOBAL Future Weather Generator tool.

    This function provides a simple interface to the morphing process while
    still allowing full customization of the Future Weather Generator tool. It
    internally uses the `MorphingWorkflowGlobal` class to validate all
    parameters before execution and runs the entire workflow in a single call.
    It supports Global v3.x, v4.x and v5+ (FWG Engine).

    The generated weather (.epw, .met or .csv) and .stat files of each future
    scenario are saved directly to the output directory using the default
    filenames produced by the FWG tool. This function does not perform custom
    renaming. Other files produced by the tool (e.g., the baseline processed by
    the FWG Engine, reports or logs) remain in the temporary directory.

    Args:
        epw_paths (Union[str, List[str]]): A single path or a list of paths
            to the EPW files to be processed.
        fwg_jar_path (str): Path to the `FutureWeatherGenerator.jar` file.
        output_dir (str, optional): Directory where the final morphed files
            will be saved. Defaults to './morphed_epws'.
        delete_temp_files (bool, optional): If True, temporary folders are
            deleted after processing. Defaults to True.
        temp_base_dir (str, optional): Base directory for temporary files.
            Defaults to './morphing_temp_results'.
        fwg_show_tool_output (bool, optional): If True, prints the FWG tool's
            console output in real-time. Defaults to False.
        fwg_params (Optional[Dict[str, Any]], optional): A dictionary for base
            FWG parameters, with keys without the `fwg_` prefix. Any explicit
            `fwg_` argument that is passed will override this. The explicit
            `fwg_` arguments default to None, which uses the value of
            `fwg_params` or, if it is not set there, the default of pyfwg.
            Defaults to None.
        fwg_gcms (Optional[List[str]], optional): List of GCMs to use.
        (All other `fwg_` arguments are passed directly to the tool and are
        explained in the `MorphingWorkflowGlobal.configure_and_preview` docstring).

    Returns:
        List[str]: A list of absolute paths to the successfully created weather
                   and .stat files.

    Raises:
        ValueError: If the provided FWG parameters fail validation.
    """
    logger.info("--- Starting Direct Global Morphing Process ---")

    # Instantiate the corresponding workflow class to use as an internal engine.
    workflow = MorphingWorkflowGlobal()

    # Normalize the input to always be a list for consistent processing.
    epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths

    # Perform a simple pass-through mapping. This populates the workflow's
    # internal list of files, which is required by the configuration step.
    # workflow.map_categories(
    #     epw_files=epw_files,
    #     keyword_mapping={'basename': {os.path.splitext(os.path.basename(p))[0]: p for p in epw_files}}
    # )

    # Directly populate the epw_categories attribute.
    workflow.epw_categories = {
        os.path.abspath(path): {} for path in epw_files if os.path.exists(path)
    }

    # Call the correct, renamed method: configure_and_preview.
    # This reuses all the validation and parameter-building logic from the class.
    workflow.configure_and_preview(
        final_output_dir=output_dir,
        # For this simple API, the output pattern is not used for complex renaming,
        # but it must be provided with the correct placeholders to pass validation.
        output_filename_pattern='{ssp}_{year}',
        fwg_jar_path=fwg_jar_path,
        run_incomplete_files=True,  # In the simple API, we always attempt to run all provided files.
        delete_temp_files=delete_temp_files,
        temp_base_dir=temp_base_dir,
        fwg_show_tool_output=fwg_show_tool_output,
        fwg_params=fwg_params,
        fwg_gcms=fwg_gcms,
        fwg_create_ensemble=fwg_create_ensemble,
        fwg_winter_sd_shift=fwg_winter_sd_shift,
        fwg_summer_sd_shift=fwg_summer_sd_shift,
        fwg_month_transition_hours=fwg_month_transition_hours,
        fwg_use_multithreading=fwg_use_multithreading,
        fwg_interpolation_method_id=fwg_interpolation_method_id,
        fwg_limit_variables=fwg_limit_variables,
        fwg_solar_hour_adjustment=fwg_solar_hour_adjustment,
        fwg_diffuse_irradiation_model=fwg_diffuse_irradiation_model,
        fwg_add_uhi=fwg_add_uhi,
        fwg_epw_original_lcz=fwg_epw_original_lcz,
        fwg_target_uhi_lcz=fwg_target_uhi_lcz,
        fwg_output_type=fwg_output_type,
        fwg_version=fwg_version,
        fwg_scenarios=fwg_scenarios,
        fwg_timeframes=fwg_timeframes,
        fwg_decomposition_method=fwg_decomposition_method,
        fwg_illuminance_method=fwg_illuminance_method,
        fwg_infrared_method=fwg_infrared_method,
        fwg_morphing_method=fwg_morphing_method,
        fwg_uncertainty_variant=fwg_uncertainty_variant,
        fwg_uncertainty_sigma=fwg_uncertainty_sigma,
        fwg_output_profile=fwg_output_profile,
        fwg_model_unzipped_folder=fwg_model_unzipped_folder,
        fwg_extra_args=fwg_extra_args
    )

    # Run the workflow and move the generated files without renaming them.
    final_file_paths = _run_direct_morphing(workflow, output_dir)

    logger.info(f"Direct global morphing complete. {len(final_file_paths)} files created in {os.path.abspath(output_dir)}")
    return final_file_paths


# def morph_epw_europe(*,
#                      epw_paths: Union[str, List[str]],
#                      fwg_jar_path: str,
#                      output_dir: str = './morphed_epws_europe',
#                      delete_temp_files: bool = True,
#                      temp_base_dir: str = './morphing_temp_results_europe',
#                      fwg_show_tool_output: bool = False,
#                      fwg_params: Optional[Dict[str, Any]] = None,
#                      # --- Explicit Future Weather Generator Arguments ---
#                      fwg_rcm_pairs: Optional[List[str]] = None,
#                      fwg_create_ensemble: bool = True,
#                      fwg_winter_sd_shift: float = 0.0,
#                      fwg_summer_sd_shift: float = 0.0,
#                      fwg_month_transition_hours: int = 72,
#                      fwg_use_multithreading: bool = True,
#                      fwg_interpolation_method_id: int = 0,
#                      fwg_limit_variables: bool = True,
#                      fwg_solar_hour_adjustment: int = 1,
#                      fwg_diffuse_irradiation_model: int = 1,
#                      fwg_add_uhi: bool = True,
#                      fwg_epw_original_lcz: int = 14,
#                      fwg_target_uhi_lcz: int = 1):
#     """Performs a direct, one-shot morphing using the EUROPE-specific Future Weather Generator tool.
#
#     This function provides a simple interface to the morphing process while
#     still allowing full customization of the Europe-specific FWG tool. It
#     internally uses the `MorphingWorkflowEurope` class to validate all
#     parameters before execution and runs the entire workflow in a single call.
#
#     The generated .epw and .stat files are saved directly to the output
#     directory using the default filenames produced by the FWG tool.
#
#     Args:
#         epw_paths (Union[str, List[str]]): A single path or a list of paths
#             to the EPW files to be processed.
#         fwg_jar_path (str): Path to the `FutureWeatherGenerator_Europe.jar` file.
#         output_dir (str, optional): Directory where the final morphed files
#             will be saved. Defaults to './morphed_epws_europe'.
#         delete_temp_files (bool, optional): If True, temporary folders are
#             deleted after processing. Defaults to True.
#         temp_base_dir (str, optional): Base directory for temporary files.
#             Defaults to './morphing_temp_results_europe'.
#         fwg_show_tool_output (bool, optional): If True, prints the FWG tool's
#             console output in real-time. Defaults to False.
#         fwg_params (Optional[Dict[str, Any]], optional): A dictionary for base
#             FWG parameters. Any explicit `fwg_` argument will override this.
#             Defaults to None.
#         fwg_rcm_pairs (Optional[List[str]], optional): List of GCM-RCM pairs
#             to use. If None, the tool's default list is used.
#         (All other `fwg_` arguments are analogous to the `morph_epw_global`
#         function and are explained in the `MorphingWorkflowEurope.set_morphing_config`
#         docstring).
#
#     Returns:
#         List[str]: A list of absolute paths to the successfully created .epw
#                    and .stat files.
#
#     Raises:
#         ValueError: If the provided FWG parameters fail validation.
#     """
#     logging.info("--- Starting Europe-Specific Direct Morphing Process ---")
#
#     # Instantiate the corresponding workflow class to use as an engine.
#     workflow = MorphingWorkflowEurope()
#
#     # Normalize the input to always be a list for consistent processing.
#     epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths
#
#     # Perform a simple pass-through mapping to populate the internal file list.
#     workflow.map_categories(
#         epw_files=epw_files,
#         keyword_mapping={'basename': {os.path.splitext(os.path.basename(p))[0]: p for p in epw_files}}
#     )
#
#     # Reuse the class's set_morphing_config method to validate all parameters
#     # and set up the internal state of the workflow instance.
#     workflow.set_morphing_config(
#         fwg_jar_path=fwg_jar_path,
#         run_incomplete_files=True,  # In the simple API, we always attempt to run all provided files.
#         delete_temp_files=delete_temp_files,
#         temp_base_dir=temp_base_dir,
#         fwg_show_tool_output=fwg_show_tool_output,
#         fwg_params=fwg_params,
#         fwg_rcm_pairs=fwg_rcm_pairs,
#         fwg_create_ensemble=fwg_create_ensemble,
#         fwg_winter_sd_shift=fwg_winter_sd_shift,
#         fwg_summer_sd_shift=fwg_summer_sd_shift,
#         fwg_month_transition_hours=fwg_month_transition_hours,
#         fwg_use_multithreading=fwg_use_multithreading,
#         fwg_interpolation_method_id=fwg_interpolation_method_id,
#         fwg_limit_variables=fwg_limit_variables,
#         fwg_solar_hour_adjustment=fwg_solar_hour_adjustment,
#         fwg_diffuse_irradiation_model=fwg_diffuse_irradiation_model,
#         fwg_add_uhi=fwg_add_uhi,
#         fwg_epw_original_lcz=fwg_epw_original_lcz,
#         fwg_target_uhi_lcz=fwg_target_uhi_lcz
#     )
#
#     # Block execution if the configuration was found to be invalid.
#     if not workflow.is_config_valid:
#         raise ValueError("FWG parameter validation failed. Please check the warnings in the log above.")
#
#     # Manually set the final output directory and create it.
#     os.makedirs(output_dir, exist_ok=True)
#     workflow.inputs['final_output_dir'] = output_dir
#
#     final_file_paths = []
#
#     # Iterate through the definitive list of files to be processed.
#     for epw_path in workflow.epws_to_be_morphed:
#         # --- Pre-flight check for LCZ availability ---
#         fwg_params = workflow.inputs['fwg_params']
#         if fwg_params.get('add_uhi', False):
#             logging.info(f"Validating LCZ availability for {os.path.basename(epw_path)}...")
#             lcz_validation_result = check_lcz_availability(
#                 epw_path=epw_path,
#                 original_lcz=fwg_params.get('epw_original_lcz'),
#                 target_lcz=fwg_params.get('target_uhi_lcz'),
#                 fwg_jar_path=workflow.inputs['fwg_jar_path'],
#                 java_class_path_prefix='futureweathergenerator_europe'
#
#             )
#             # If validation fails, log the detailed error and skip this file.
#             if lcz_validation_result is not True:
#                 logging.error(f"LCZ validation failed for '{os.path.basename(epw_path)}'. This file will be skipped.")
#                 if isinstance(lcz_validation_result, dict):
#                     for error_message in lcz_validation_result.get("invalid_messages", []):
#                         logging.error(error_message)
#                     logging.error("The following LCZs are available for this location:")
#                     for lcz in lcz_validation_result.get("available", []):
#                         logging.error(f"- {lcz}")
#                 continue
#
#         # Create a unique temporary subdirectory for this specific EPW file.
#         temp_epw_output_dir = os.path.join(workflow.inputs['temp_base_dir'], os.path.splitext(os.path.basename(epw_path))[0])
#         os.makedirs(temp_epw_output_dir, exist_ok=True)
#
#         # Reuse the low-level execution method from the class.
#         success = workflow._execute_single_morph(epw_path, temp_epw_output_dir)
#
#         if success:
#             # Implement simple file moving logic.
#             for generated_file in os.listdir(temp_epw_output_dir):
#                 if generated_file.endswith((".epw", ".stat")):
#                     source_path = os.path.join(temp_epw_output_dir, generated_file)
#                     dest_path = os.path.join(output_dir, generated_file)
#                     shutil.move(source_path, dest_path)
#                     final_file_paths.append(os.path.abspath(dest_path))
#
#             # Clean up the temporary directory if requested.
#             if workflow.inputs['delete_temp_files']:
#                 _robust_rmtree(temp_epw_output_dir)
#
#     logging.info(f"Europe morphing complete. {len(final_file_paths)} files created in {os.path.abspath(output_dir)}")
#     return final_file_paths

def morph_epw_europe(*,
                     epw_paths: Union[str, List[str]],
                     fwg_jar_path: str,
                     output_dir: str = './morphed_epws_europe',
                     delete_temp_files: bool = True,
                     temp_base_dir: str = './morphing_temp_results_europe',
                     fwg_show_tool_output: bool = False,
                     fwg_params: Optional[Dict[str, Any]] = None,
                     # --- Explicit Future Weather Generator Arguments ---
                     fwg_rcm_pairs: Optional[List[str]] = None,
                     fwg_create_ensemble: Optional[bool] = None,
                     fwg_winter_sd_shift: Optional[float] = None,
                     fwg_summer_sd_shift: Optional[float] = None,
                     fwg_month_transition_hours: Optional[int] = None,
                     fwg_use_multithreading: Optional[bool] = None,
                     fwg_interpolation_method_id: Optional[Union[int, str]] = None,
                     fwg_limit_variables: Optional[bool] = None,
                     fwg_solar_hour_adjustment: Optional[Union[int, str]] = None,
                     fwg_diffuse_irradiation_model: Optional[Union[int, str]] = None,
                     fwg_add_uhi: Optional[bool] = None,
                     fwg_epw_original_lcz: Optional[int] = None,
                     fwg_target_uhi_lcz: Optional[int] = None,
                     fwg_output_type: Optional[str] = None,
                     fwg_version: Optional[Union[str, int]] = None,
                     # --- FWG Engine Arguments (Europe v3+) ---
                     fwg_scenarios: Optional[List[str]] = None,
                     fwg_timeframes: Optional[List[Union[int, str]]] = None,
                     fwg_decomposition_method: Optional[str] = None,
                     fwg_illuminance_method: Optional[str] = None,
                     fwg_infrared_method: Optional[str] = None,
                     fwg_morphing_method: Optional[str] = None,
                     fwg_uncertainty_variant: Optional[str] = None,
                     fwg_uncertainty_sigma: Optional[float] = None,
                     fwg_output_profile: Optional[str] = None,
                     fwg_model_unzipped_folder: Optional[str] = None,
                     fwg_extra_args: Optional[Dict[str, Any]] = None):
    """Performs a direct, one-shot morphing using the EUROPE-specific Future Weather Generator tool.

    This function provides a simple interface to the morphing process while
    still allowing full customization of the Europe-specific FWG tool. It
    internally uses the `MorphingWorkflowEurope` class to validate all
    parameters before execution and runs the entire workflow in a single call.
    It supports Europe v1.x, v2.x and v3+ (FWG Engine).

    The generated weather (.epw, .met or .csv) and .stat files of each future
    scenario are saved directly to the output directory using the default
    filenames produced by the FWG tool. This function does not perform custom
    renaming. Other files produced by the tool (e.g., the baseline processed by
    the FWG Engine, reports or logs) remain in the temporary directory.

    Args:
        epw_paths (Union[str, List[str]]): A single path or a list of paths
            to the EPW files to be processed.
        fwg_jar_path (str): Path to the `FutureWeatherGenerator_Europe.jar` file.
        output_dir (str, optional): Directory where the final morphed files
            will be saved. Defaults to './morphed_epws_europe'.
        delete_temp_files (bool, optional): If True, temporary folders are
            deleted after processing. Defaults to True.
        temp_base_dir (str, optional): Base directory for temporary files.
            Defaults to './morphing_temp_results_europe'.
        fwg_show_tool_output (bool, optional): If True, prints the FWG tool's
            console output in real-time. Defaults to False.
        fwg_params (Optional[Dict[str, Any]], optional): A dictionary for base
            FWG parameters, with keys without the `fwg_` prefix. Any explicit
            `fwg_` argument that is passed will override this. The explicit
            `fwg_` arguments default to None, which uses the value of
            `fwg_params` or, if it is not set there, the default of pyfwg.
            Defaults to None.
        fwg_rcm_pairs (Optional[List[str]], optional): List of GCM-RCM pairs
            to use. If None, the tool's default list is used.
        (All other `fwg_` arguments are analogous to the `morph_epw_global`
        function and are explained in the `MorphingWorkflowEurope.configure_and_preview`
        docstring).

    Returns:
        List[str]: A list of absolute paths to the successfully created weather
                   and .stat files.

    Raises:
        ValueError: If the provided FWG parameters fail validation.
    """
    logger.info("--- Starting Europe-Specific Direct Morphing Process ---")

    # Instantiate the corresponding workflow class to use as an internal engine.
    workflow = MorphingWorkflowEurope()

    # Normalize the input to always be a list for consistent processing.
    epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths

    # Perform a simple pass-through mapping to populate the internal file list.
    # workflow.map_categories(
    #     epw_files=epw_files,
    #     keyword_mapping={'basename': {os.path.splitext(os.path.basename(p))[0]: p for p in epw_files}}
    # )

    # Directly populate the epw_categories attribute.
    workflow.epw_categories = {
        os.path.abspath(path): {} for path in epw_files if os.path.exists(path)
    }

    # Call the correct configuration method for the workflow class.
    # This reuses all the validation and parameter-building logic.
    workflow.configure_and_preview(
        final_output_dir=output_dir,
        # For this simple API, the output pattern is not used for complex renaming,
        # but it must be provided with the correct placeholders to pass validation.
        output_filename_pattern='{rcp}_{year}',
        fwg_jar_path=fwg_jar_path,
        run_incomplete_files=True,  # In the simple API, we always attempt to run all provided files.
        delete_temp_files=delete_temp_files,
        temp_base_dir=temp_base_dir,
        fwg_show_tool_output=fwg_show_tool_output,
        fwg_params=fwg_params,
        fwg_rcm_pairs=fwg_rcm_pairs,
        fwg_create_ensemble=fwg_create_ensemble,
        fwg_winter_sd_shift=fwg_winter_sd_shift,
        fwg_summer_sd_shift=fwg_summer_sd_shift,
        fwg_month_transition_hours=fwg_month_transition_hours,
        fwg_use_multithreading=fwg_use_multithreading,
        fwg_interpolation_method_id=fwg_interpolation_method_id,
        fwg_limit_variables=fwg_limit_variables,
        fwg_solar_hour_adjustment=fwg_solar_hour_adjustment,
        fwg_diffuse_irradiation_model=fwg_diffuse_irradiation_model,
        fwg_add_uhi=fwg_add_uhi,
        fwg_epw_original_lcz=fwg_epw_original_lcz,
        fwg_target_uhi_lcz=fwg_target_uhi_lcz,
        fwg_output_type=fwg_output_type,
        fwg_version=fwg_version,
        fwg_scenarios=fwg_scenarios,
        fwg_timeframes=fwg_timeframes,
        fwg_decomposition_method=fwg_decomposition_method,
        fwg_illuminance_method=fwg_illuminance_method,
        fwg_infrared_method=fwg_infrared_method,
        fwg_morphing_method=fwg_morphing_method,
        fwg_uncertainty_variant=fwg_uncertainty_variant,
        fwg_uncertainty_sigma=fwg_uncertainty_sigma,
        fwg_output_profile=fwg_output_profile,
        fwg_model_unzipped_folder=fwg_model_unzipped_folder,
        fwg_extra_args=fwg_extra_args
    )

    # Run the workflow and move the generated files without renaming them.
    final_file_paths = _run_direct_morphing(workflow, output_dir)

    logger.info(f"Europe morphing complete. {len(final_file_paths)} files created in {os.path.abspath(output_dir)}")
    return final_file_paths


def morph_epw_cordex(*,
                     epw_paths: Union[str, List[str]],
                     fwg_jar_path: str,
                     output_dir: str = './morphed_epws_cordex',
                     delete_temp_files: bool = True,
                     temp_base_dir: str = './morphing_temp_results_cordex',
                     fwg_show_tool_output: bool = False,
                     fwg_params: Optional[Dict[str, Any]] = None,
                     # --- Explicit Future Weather Generator Arguments ---
                     fwg_rcm_pairs: Optional[List[str]] = None,
                     fwg_create_ensemble: Optional[bool] = None,
                     fwg_winter_sd_shift: Optional[float] = None,
                     fwg_summer_sd_shift: Optional[float] = None,
                     fwg_month_transition_hours: Optional[int] = None,
                     fwg_use_multithreading: Optional[bool] = None,
                     fwg_interpolation_method_id: Optional[Union[int, str]] = None,
                     fwg_limit_variables: Optional[bool] = None,
                     fwg_output_type: Optional[str] = None,
                     fwg_version: Optional[Union[str, int]] = None,
                     fwg_scenarios: Optional[List[str]] = None,
                     fwg_timeframes: Optional[List[Union[int, str]]] = None,
                     fwg_decomposition_method: Optional[str] = None,
                     fwg_illuminance_method: Optional[str] = None,
                     fwg_infrared_method: Optional[str] = None,
                     fwg_morphing_method: Optional[str] = None,
                     fwg_uncertainty_variant: Optional[str] = None,
                     fwg_uncertainty_sigma: Optional[float] = None,
                     fwg_output_profile: Optional[str] = None,
                     fwg_model_unzipped_folder: Optional[str] = None,
                     fwg_extra_args: Optional[Dict[str, Any]] = None):
    """Performs a direct, one-shot morphing using a CORDEX regional Future Weather Generator tool.

    This function provides a simple interface to the regional distributions of
    the FWG Engine (e.g., North America NAM-44 or Africa AFR-22). It internally
    uses the `MorphingWorkflowCordex` class, which identifies the region of the
    JAR and validates the scenarios and GCM-RCM pairs against it.

    The generated weather (.epw, .met or .csv) and .stat files of each future
    scenario are saved directly to the output directory using the default
    filenames produced by the FWG tool. This function does not perform custom
    renaming. Other files produced by the tool (e.g., the baseline processed by
    the FWG Engine, reports or logs) remain in the temporary directory.

    Args:
        epw_paths (Union[str, List[str]]): A single path or a list of paths
            to the EPW files to be processed.
        fwg_jar_path (str): Path to the regional JAR file (e.g.,
            'FutureWeatherGenerator-CORDEX-CMIP5-North-America-NAM-44-v1.2.0.jar').
        output_dir (str, optional): Directory where the final morphed files
            will be saved. Defaults to './morphed_epws_cordex'.
        delete_temp_files (bool, optional): If True, temporary folders are
            deleted after processing. Defaults to True.
        temp_base_dir (str, optional): Base directory for temporary files.
            Defaults to './morphing_temp_results_cordex'.
        fwg_show_tool_output (bool, optional): If True, prints the FWG tool's
            console output in real-time. Defaults to False.
        fwg_params (Optional[Dict[str, Any]], optional): A dictionary for base
            FWG parameters, with keys without the `fwg_` prefix. Any explicit
            `fwg_` argument that is passed will override this. The explicit
            `fwg_` arguments default to None, which uses the value of
            `fwg_params` or, if it is not set there, the default of pyfwg.
            Defaults to None.
        fwg_rcm_pairs (Optional[List[str]], optional): List of GCM-RCM pairs
            of the region. If None, the tool uses all of them.
        (All other `fwg_` arguments are explained in the
        `MorphingWorkflowCordex.configure_and_preview` docstring).

    Returns:
        List[str]: A list of absolute paths to the successfully created weather
                   and .stat files.

    Raises:
        ValueError: If the provided FWG parameters fail validation.
    """
    logger.info("--- Starting CORDEX Regional Direct Morphing Process ---")

    # Instantiate the corresponding workflow class to use as an internal engine.
    workflow = MorphingWorkflowCordex()

    # Normalize the input to always be a list for consistent processing.
    epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths

    # Directly populate the epw_categories attribute.
    workflow.epw_categories = {
        os.path.abspath(path): {} for path in epw_files if os.path.exists(path)
    }

    # Reuse all the validation and parameter-building logic of the workflow class.
    workflow.configure_and_preview(
        final_output_dir=output_dir,
        # For this simple API, the output pattern is not used for complex renaming,
        # but it must be provided with the correct placeholders to pass validation.
        output_filename_pattern='{rcp}_{year}',
        fwg_jar_path=fwg_jar_path,
        run_incomplete_files=True,  # In the simple API, we always attempt to run all provided files.
        delete_temp_files=delete_temp_files,
        temp_base_dir=temp_base_dir,
        fwg_show_tool_output=fwg_show_tool_output,
        fwg_params=fwg_params,
        fwg_rcm_pairs=fwg_rcm_pairs,
        fwg_create_ensemble=fwg_create_ensemble,
        fwg_winter_sd_shift=fwg_winter_sd_shift,
        fwg_summer_sd_shift=fwg_summer_sd_shift,
        fwg_month_transition_hours=fwg_month_transition_hours,
        fwg_use_multithreading=fwg_use_multithreading,
        fwg_interpolation_method_id=fwg_interpolation_method_id,
        fwg_limit_variables=fwg_limit_variables,
        fwg_output_type=fwg_output_type,
        fwg_version=fwg_version,
        fwg_scenarios=fwg_scenarios,
        fwg_timeframes=fwg_timeframes,
        fwg_decomposition_method=fwg_decomposition_method,
        fwg_illuminance_method=fwg_illuminance_method,
        fwg_infrared_method=fwg_infrared_method,
        fwg_morphing_method=fwg_morphing_method,
        fwg_uncertainty_variant=fwg_uncertainty_variant,
        fwg_uncertainty_sigma=fwg_uncertainty_sigma,
        fwg_output_profile=fwg_output_profile,
        fwg_model_unzipped_folder=fwg_model_unzipped_folder,
        fwg_extra_args=fwg_extra_args
    )

    # Run the workflow and move the generated files without renaming them.
    final_file_paths = _run_direct_morphing(workflow, output_dir)

    logger.info(f"CORDEX regional morphing complete. {len(final_file_paths)} files created in {os.path.abspath(output_dir)}")
    return final_file_paths
