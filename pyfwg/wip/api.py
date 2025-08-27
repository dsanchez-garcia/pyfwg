# pyfwg/api.py

import os
import shutil
import logging
import subprocess
import time
from typing import List, Union, Optional, Dict, Any

# Import the workflow classes to use them as an internal engine
from .workflow import MorphingWorkflowGlobal, MorphingWorkflowEurope
# Import utility functions
from .utils import _robust_rmtree, check_lcz_availability


def morph_epw_global(*,
                     epw_paths: Union[str, List[str]],
                     fwg_jar_path: str,
                     output_dir: str = './morphed_epws',
                     delete_temp_files: bool = True,
                     temp_base_dir: str = './morphing_temp_results',
                     fwg_show_tool_output: bool = False,
                     fwg_params: Optional[Dict[str, Any]] = None,
                     **kwargs):
    """Performs a direct, one-shot morphing using the GLOBAL FutureWeatherGenerator tool.

    This function provides a simple interface to the morphing process while
    still allowing full customization of the FutureWeatherGenerator tool. It
    internally uses the `MorphingWorkflowGlobal` class to validate all
    parameters before execution and runs the entire workflow in a single call.

    The generated .epw and .stat files are saved directly to the output
    directory using the default filenames produced by the FWG tool.

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
            FWG parameters. Any explicit `fwg_` argument will override this.
            Defaults to None.
        **kwargs: All other explicit `fwg_` arguments from the
            `MorphingWorkflowGlobal.set_morphing_config` method are accepted
            here (e.g., `fwg_gcms`, `fwg_interpolation_method_id`).

    Returns:
        List[str]: A list of absolute paths to the successfully created .epw
                   and .stat files.

    Raises:
        ValueError: If the provided FWG parameters fail validation.
    """
    logging.info("--- Starting Direct Global Morphing Process ---")

    # Instantiate the corresponding workflow class to use as an engine.
    workflow = MorphingWorkflowGlobal()

    # Normalize the input to always be a list for consistent processing.
    epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths

    # Perform a simple pass-through mapping. This populates the workflow's
    # internal list of files, which is required by the set_morphing_config step.
    workflow.map_categories(
        epw_files=epw_files,
        keyword_mapping={'basename': {os.path.splitext(os.path.basename(p))[0]: p for p in epw_files}}
    )

    # Combine all keyword arguments into a single dictionary for configuration.
    config_kwargs = {
        **kwargs,
        'fwg_params': fwg_params,
        'fwg_show_tool_output': fwg_show_tool_output,
        'temp_base_dir': temp_base_dir,
        'delete_temp_files': delete_temp_files,
        'run_incomplete_files': True,  # In the simple API, we always attempt to run all provided files.
        'fwg_jar_path': fwg_jar_path
    }

    # Reuse the class's set_morphing_config method to validate all parameters and set up the state.
    workflow.set_morphing_config(**config_kwargs)

    # Block execution if the configuration was found to be invalid.
    if not workflow.is_config_valid:
        raise ValueError("FWG parameter validation failed. Please check the warnings in the log above.")

    # Manually set the final output directory and create it, as the preview step is skipped.
    workflow.inputs['final_output_dir'] = output_dir
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
            logging.info(f"Validating LCZ availability for {os.path.basename(epw_path)}...")
            lcz_validation_result = check_lcz_availability(
                epw_path=epw_path,
                original_lcz=fwg_params.get('epw_original_lcz'),
                target_lcz=fwg_params.get('target_uhi_lcz'),
                fwg_jar_path=workflow.inputs['fwg_jar_path']
            )
            # If validation fails, log the error and skip this file.
            if lcz_validation_result is not True:
                logging.error(f"LCZ validation failed for '{os.path.basename(epw_path)}'. This file will be skipped.")
                if isinstance(lcz_validation_result, list):
                    logging.error("The following LCZs are available for this location:")
                    for lcz in lcz_validation_result: logging.error(f"- {lcz}")
                continue

        # Reuse the low-level execution method from the class.
        success = workflow._execute_single_morph(epw_path, temp_epw_output_dir)

        if success:
            # Implement simple file moving logic, as no renaming is needed.
            for generated_file in os.listdir(temp_epw_output_dir):
                if generated_file.endswith((".epw", ".stat")):
                    source_path = os.path.join(temp_epw_output_dir, generated_file)
                    dest_path = os.path.join(output_dir, generated_file)
                    shutil.move(source_path, dest_path)
                    final_file_paths.append(os.path.abspath(dest_path))

            # Clean up the temporary directory if requested.
            if workflow.inputs['delete_temp_files']:
                _robust_rmtree(temp_epw_output_dir)

    logging.info(f"Direct global morphing complete. {len(final_file_paths)} files created in {os.path.abspath(output_dir)}")
    return final_file_paths


def morph_epw_europe(*,
                     epw_paths: Union[str, List[str]],
                     fwg_jar_path: str,
                     output_dir: str = './morphed_epws_europe',
                     delete_temp_files: bool = True,
                     temp_base_dir: str = './morphing_temp_results_europe',
                     fwg_show_tool_output: bool = False,
                     fwg_params: Optional[Dict[str, Any]] = None,
                     **kwargs):
    """Performs a direct, one-shot morphing using the EUROPE-specific FutureWeatherGenerator tool.

    This function provides a simple interface to the morphing process while
    still allowing full customization of the Europe-specific FWG tool. It
    internally uses the `MorphingWorkflowEurope` class to validate all
    parameters before execution and runs the entire workflow in a single call.

    The generated .epw and .stat files are saved directly to the output
    directory using the default filenames produced by the FWG tool.

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
            FWG parameters. Any explicit `fwg_` argument will override this.
            Defaults to None.
        **kwargs: All other explicit `fwg_` arguments from the
            `MorphingWorkflowEurope.set_morphing_config` method are accepted
            here (e.g., `fwg_rcm_pairs`, `fwg_interpolation_method_id`).

    Returns:
        List[str]: A list of absolute paths to the successfully created .epw
                   and .stat files.

    Raises:
        ValueError: If the provided FWG parameters fail validation.
    """
    logging.info("--- Starting Europe-Specific Direct Morphing Process ---")

    # Instantiate the corresponding workflow class to use as an engine.
    workflow = MorphingWorkflowEurope()

    # Normalize the input to always be a list for consistent processing.
    epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths

    # Perform a simple pass-through mapping.
    workflow.map_categories(
        epw_files=epw_files,
        keyword_mapping={'basename': {os.path.splitext(os.path.basename(p))[0]: p for p in epw_files}}
    )

    # Combine all keyword arguments into a single dictionary for configuration.
    config_kwargs = {
        **kwargs,
        'fwg_params': fwg_params,
        'fwg_show_tool_output': fwg_show_tool_output,
        'temp_base_dir': temp_base_dir,
        'delete_temp_files': delete_temp_files,
        'run_incomplete_files': True,
        'fwg_jar_path': fwg_jar_path
    }

    # Reuse the class's set_morphing_config method to validate all parameters.
    workflow.set_morphing_config(**config_kwargs)

    # Block execution if the configuration was found to be invalid.
    if not workflow.is_config_valid:
        raise ValueError("FWG parameter validation failed. Please check the warnings in the log above.")

    # Manually set the final output directory and create it.
    workflow.inputs['final_output_dir'] = output_dir
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
            logging.info(f"Validating LCZ availability for {os.path.basename(epw_path)}...")
            lcz_validation_result = check_lcz_availability(
                epw_path=epw_path,
                original_lcz=fwg_params.get('epw_original_lcz'),
                target_lcz=fwg_params.get('target_uhi_lcz'),
                fwg_jar_path=workflow.inputs['fwg_jar_path']
            )
            # If validation fails, log the error and skip this file.
            if lcz_validation_result is not True:
                logging.error(f"LCZ validation failed for '{os.path.basename(epw_path)}'. This file will be skipped.")
                if isinstance(lcz_validation_result, list):
                    logging.error("The following LCZs are available for this location:")
                    for lcz in lcz_validation_result: logging.error(f"- {lcz}")
                continue

        # Reuse the low-level execution method from the class.
        success = workflow._execute_single_morph(epw_path, temp_epw_output_dir)

        if success:
            # Implement simple file moving logic.
            for generated_file in os.listdir(temp_epw_output_dir):
                if generated_file.endswith((".epw", ".stat")):
                    source_path = os.path.join(temp_epw_output_dir, generated_file)
                    dest_path = os.path.join(output_dir, generated_file)
                    shutil.move(source_path, dest_path)
                    final_file_paths.append(os.path.abspath(dest_path))

            # Clean up the temporary directory if requested.
            if workflow.inputs['delete_temp_files']:
                _robust_rmtree(temp_epw_output_dir)

    logging.info(f"Europe morphing complete. {len(final_file_paths)} files created in {os.path.abspath(output_dir)}")
    return final_file_paths