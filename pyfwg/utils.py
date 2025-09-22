# pyfwg/utils.py

import os
import shutil
import logging
import subprocess
import tempfile
import time
import re
from typing import List, Union, Dict
import ast
import pandas as pd

# Import the modern way to access package data (Python 3.9+)
try:
    from importlib import resources
except ImportError:
    # Fallback for older Python versions
    import importlib_resources as resources

def copy_tutorials(dest_dir: str = './pyfwg_tutorials'):
    """Copies the example Jupyter notebooks and their required data files to a local directory.

    This function provides a convenient way for users to access the tutorial
    files that are bundled with the installed package. It finds all content
    (notebooks, data folders, etc.) within the package's `tutorials`
    subfolder and copies it to a user-specified location, making the examples
    fully functional and ready to run.

    It intelligently copies both individual files and entire subdirectories,
    while automatically excluding Python-specific files like `__init__.py` and
    `__pycache__` directories from all levels of the copy.

    If the destination directory does not exist, it will be created.

    Args:
        dest_dir (str, optional): The path to the destination folder where
            the tutorials and data will be copied. Defaults to './pyfwg_tutorials'
            in the current working directory.
    """
    # Define the source sub-package containing the tutorials.
    source_package = 'pyfwg.tutorials'

    try:
        # Use `importlib.resources.files` to get a traversable object
        # representing the source package. This is the modern and robust
        # way to access package data.
        source_path_obj = resources.files(source_package)
    except (ModuleNotFoundError, AttributeError):
        logging.error(f"Could not find the tutorials sub-package '{source_package}'. The package might be corrupted.")
        return

    # Create the destination directory if it doesn't already exist.
    os.makedirs(dest_dir, exist_ok=True)

    logging.info(f"Copying tutorials to '{os.path.abspath(dest_dir)}'...")

    # --- Define patterns to ignore during the copy process ---
    # This uses a helper from shutil to create an ignore function that
    # will be passed to copytree. It excludes these files/dirs at all levels.
    ignore_patterns = shutil.ignore_patterns('__init__.py', '__pycache__')

    # Iterate through all items (files and directories) within the source package.
    for source_item in source_path_obj.iterdir():
        item_name = source_item.name

        # --- Top-level Exclusion Filter ---
        # This is a redundant but safe check for the top-level items.
        if item_name in ("__init__.py", "__pycache__"):
            continue

        # Construct the full destination path for the item.
        dest_path = os.path.join(dest_dir, item_name)

        # Use `importlib.resources.as_file` to get a temporary, real filesystem
        # path for the source item, whether it's in a zip or a regular directory.
        with resources.as_file(source_item) as source_item_path:
            # --- Logic to handle both files and directories ---
            if os.path.isdir(source_item_path):
                # If the item is a directory, copy the entire directory tree,
                # applying the ignore patterns recursively.
                # `dirs_exist_ok=True` allows the function to be re-run without errors.
                shutil.copytree(
                    source_item_path,
                    dest_path,
                    dirs_exist_ok=True,
                    ignore=ignore_patterns
                )
                logging.info(f"  - Copied directory: {item_name}")
            else:
                # If the item is a file, copy it directly.
                shutil.copy2(source_item_path, dest_path)
                logging.info(f"  - Copied file: {item_name}")

    logging.info("Tutorials copied successfully.")

def _robust_rmtree(path: str, max_retries: int = 5, delay: float = 0.5):
    """(Private) A robust version of shutil.rmtree that retries on PermissionError.

    This is particularly useful for handling filesystem race conditions on
    Windows, where a process might not release a file lock immediately after
    terminating.

    Args:
        path (str): The directory path to be removed.
        max_retries (int, optional): The maximum number of deletion attempts.
            Defaults to 5.
        delay (float, optional): The delay in seconds between retries.
            Defaults to 0.5.
    """
    # Attempt to delete the directory up to max_retries times.
    for i in range(max_retries):
        try:
            shutil.rmtree(path)
            # If successful, exit the function.
            return
        except PermissionError:
            # If a PermissionError occurs, log a warning and wait before retrying.
            logging.warning(f"PermissionError deleting {path}. Retrying in {delay}s... (Attempt {i + 1}/{max_retries})")
            time.sleep(delay)
    # If all retries fail, log a final error.
    logging.error(f"Failed to delete directory {path} after {max_retries} retries.")

# PREVIOUS VERSION OF uhi_morph

# def uhi_morph(*,
#               fwg_epw_path: str,
#               fwg_jar_path: str,
#               fwg_output_dir: str,
#               fwg_original_lcz: int,
#               fwg_target_lcz: int,
#               java_class_path_prefix: str,
#               fwg_limit_variables: bool = True,
#               show_tool_output: bool = False):
#     """Applies only the Urban Heat Island (UHI) effect to an EPW file.
#
#     This function is a direct wrapper for the `UHI_Morph` class. It is
#     designed to "fail fast" by raising an exception if the external tool
#     encounters any error, allowing the calling function to handle the error.
#     """
#     logging.info(f"--- Applying UHI effect to {os.path.basename(fwg_epw_path)} ---")
#
#     os.makedirs(fwg_output_dir, exist_ok=True)
#     lcz_options = f"{fwg_original_lcz}:{fwg_target_lcz}"
#     class_path = f"{java_class_path_prefix}.UHI_Morph"
#     command = ['java', '-cp', fwg_jar_path, class_path, os.path.abspath(fwg_epw_path), os.path.abspath(fwg_output_dir) + '/', str(fwg_limit_variables).lower(), lcz_options]
#
#     printable_command = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in command)
#     logging.info(f"Executing command: {printable_command}")
#
#     stdout_dest = None if show_tool_output else subprocess.PIPE
#     stderr_dest = None if show_tool_output else subprocess.PIPE
#
#     try:
#         subprocess.run(command, text=True, check=True, timeout=300, stdout=stdout_dest, stderr=stderr_dest)
#         logging.info("UHI effect applied successfully.")
#     except (FileNotFoundError, subprocess.CalledProcessError, Exception):
#         # --- BUG FIX IS HERE ---
#         # This function's only job is to run the command and report failure.
#         # It should NOT log the details of the error itself. The calling
#         # function (like check_lcz_availability or a user's script) is
#         # responsible for catching the exception and deciding how to log it.
#         # By simply re-raising, we pass the error up the call stack.
#         raise

def uhi_morph(*,
              fwg_epw_path: str,
              fwg_jar_path: str,
              fwg_output_dir: str,
              fwg_original_lcz: int,
              fwg_target_lcz: int,
              java_class_path_prefix: str,
              fwg_limit_variables: bool = True,
              show_tool_output: bool = False,
              raise_on_error: bool = True):
    """Applies only the Urban Heat Island (UHI) effect to an EPW file.

    This function is a direct wrapper for the `UHI_Morph` class within the
    FutureWeatherGenerator tool. It modifies an EPW file to reflect the
    climate of a different Local Climate Zone (LCZ) without applying future
    climate change scenarios.

    By default, this function is designed to "fail fast" by raising an
    exception if the external tool encounters any error. This behavior can be
    controlled with the `raise_on_error` flag, which is useful when this
    function is called internally by other utility functions (like
    `check_lcz_availability`) that need to handle the error gracefully.

    Args:
        fwg_epw_path (str): Path to the source EPW file.
        fwg_jar_path (str): Path to the `FutureWeatherGenerator.jar` file.
        fwg_output_dir (str): Directory where the final UHI-morphed file will be saved.
        fwg_original_lcz (int): The LCZ of the original EPW file.
        fwg_target_lcz (int): The target LCZ for which to calculate the UHI effect.
        java_class_path_prefix (str): The Java package prefix for the tool
            (e.g., 'futureweathergenerator' or 'futureweathergenerator_europe').
        fwg_limit_variables (bool, optional): If True, bounds variables to their
            physical limits. Defaults to True.
        show_tool_output (bool, optional): If True, prints the tool's console
            output in real-time. Defaults to False.
        raise_on_error (bool, optional): If True, the function will raise an
            exception if the external tool fails. If False, it will log the
            error but not stop the program, allowing the calling function to
            handle the failure. Defaults to True.

    Raises:
        FileNotFoundError: If the 'java' command is not found and `raise_on_error` is True.
        subprocess.CalledProcessError: If the FWG tool returns a non-zero exit code
            and `raise_on_error` is True.
    """
    logging.info(f"--- Applying UHI effect to {os.path.basename(fwg_epw_path)} ---")

    # Ensure the output directory exists before running the tool.
    os.makedirs(fwg_output_dir, exist_ok=True)

    # --- 1. Command Construction ---
    # Create the composite LCZ argument string (e.g., "14:2").
    lcz_options = f"{fwg_original_lcz}:{fwg_target_lcz}"

    # Dynamically build the full Java class path using the provided prefix.
    class_path = f"{java_class_path_prefix}.UHI_Morph"

    # Build the command as a list of strings for robust execution by subprocess.
    command = [
        'java', '-cp', fwg_jar_path, class_path,
        os.path.abspath(fwg_epw_path),
        os.path.abspath(fwg_output_dir) + '/',
        str(fwg_limit_variables).lower(),
        lcz_options
    ]

    # Create a user-friendly, copy-pasteable version of the command for logging.
    printable_command = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in command)
    logging.info(f"Executing command: {printable_command}")

    # --- 2. Subprocess Execution ---
    # Determine whether to show the tool's output live or capture it.
    stdout_dest = None if show_tool_output else subprocess.PIPE
    stderr_dest = None if show_tool_output else subprocess.PIPE

    try:
        # Run the command. The `check=True` flag will cause it to raise
        # CalledProcessError if the Java program returns a non-zero exit code.
        subprocess.run(command, text=True, check=True, timeout=300, stdout=stdout_dest, stderr=stderr_dest)
        logging.info("UHI effect applied successfully.")

    except (FileNotFoundError, subprocess.CalledProcessError, Exception) as e:
        raise e
        # # --- 3. Error Handling ---
        # # Only raise the exception if the caller wants the program to stop.
        # # This allows functions like check_lcz_availability to handle the error gracefully.
        # if raise_on_error:
        #     # Provide specific logging for different types of errors.
        #     if isinstance(e, FileNotFoundError):
        #         logging.error("Error: 'java' command not found. Please ensure Java is installed and in the system's PATH.")
        #     elif isinstance(e, subprocess.CalledProcessError):
        #         logging.error("The UHI_Morph tool returned an error.")
        #         # If output was captured, log it now.
        #         if e.stdout: logging.error(f"STDOUT:\n{e.stdout}")
        #         if e.stderr: logging.error(f"STDERR:\n{e.stderr}")
        #     else:
        #         logging.error(f"An unexpected error occurred: {e}")
        #
        #     # Re-raise the original exception to halt execution.
        #     raise e


def check_lcz_availability(*,
                           epw_path: str,
                           original_lcz: int,
                           target_lcz: int,
                           fwg_jar_path: str,
                           java_class_path_prefix: str,
                           show_tool_output: bool = False) -> Union[bool, Dict[str, List]]:
    """Checks if the specified original and target LCZs are available for a given EPW file.

    This utility function internally calls `uhi_morph` in a temporary directory
    to validate the LCZ pair. It is designed to be used as a pre-flight check
    before running a full morphing workflow.

    The function operates by intentionally letting `uhi_morph` fail if an LCZ
    is invalid. It then catches the `subprocess.CalledProcessError`, silently
    parses the tool's error output to find the list of valid LCZs, and
    diagnoses which of the user's inputs was incorrect.

    Args:
        epw_path (str): Path to the source EPW file to check.
        original_lcz (int): The original LCZ number you want to validate.
        target_lcz (int): The target LCZ number you want to validate.
        fwg_jar_path (str): Path to the `FutureWeatherGenerator.jar` file.
        java_class_path_prefix (str): The Java package prefix for the tool.
        show_tool_output (bool, optional): If True, prints the underlying
            FWG tool's console output in real-time. This is useful for
            debugging the check itself. Defaults to False.

    Returns:
        Union[bool, Dict[str, List]]:
        - `True` if both LCZs are available.
        - A dictionary with keys 'invalid_messages' (listing specific errors)
          and 'available' (listing valid LCZ descriptions) if validation fails
          due to unavailable LCZs.
        - `False` if an unexpected error occurs (e.g., Java not found).
    """
    logging.info(f"Checking LCZ pair (Original: {original_lcz}, Target: {target_lcz}) availability for {os.path.basename(epw_path)}...")

    # Use a temporary directory that is automatically created and cleaned up,
    # preventing leftover files from the check.
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Call uhi_morph. It is expected to raise a CalledProcessError if
            # the LCZs are invalid, which we will catch and handle.
            uhi_morph(
                fwg_epw_path=epw_path,
                fwg_jar_path=fwg_jar_path,
                fwg_output_dir=temp_dir,
                fwg_original_lcz=original_lcz,
                fwg_target_lcz=target_lcz,
                java_class_path_prefix=java_class_path_prefix,
                show_tool_output=show_tool_output,
                raise_on_error=True  # Ensure it raises an exception on failure
            )
            # If no exception was raised, the LCZ pair is valid.
            logging.info(f"LCZ pair (Original: {original_lcz}, Target: {target_lcz}) is available.")
            return True

        except subprocess.CalledProcessError as e:
            # This block is the expected outcome if an LCZ is invalid.
            # It now has exclusive control over handling the error.

            # Combine stdout and stderr to ensure we capture the full error message.
            output = e.stdout + e.stderr
            available_lczs_full_text = []
            available_lcz_numbers = set()
            start_parsing = False

            # Iterate through the captured output line by line.
            for line in output.splitlines():
                # The line "The LCZs available are:" is our trigger to start parsing.
                if 'The LCZs available are:' in line:
                    start_parsing = True
                    continue

                # Once triggered, look for lines containing LCZ information.
                if start_parsing:
                    # Use regex to safely extract the LCZ number from the line.
                    match = re.search(r'LCZ (\d+)', line)
                    if match:
                        # Store the number for logical checks and the full text for display.
                        available_lcz_numbers.add(int(match.group(1)))
                        available_lczs_full_text.append(line.strip())

            # If we successfully parsed the list of available LCZs, diagnose the problem.
            if available_lczs_full_text:
                invalid_lczs_messages = []

                # Check which of the user's inputs are not in the valid set.
                if original_lcz not in available_lcz_numbers:
                    invalid_lczs_messages.append(f"The original LCZ '{original_lcz}' is not available.")

                # Check the target LCZ only if it's different from the original.
                if target_lcz not in available_lcz_numbers and original_lcz != target_lcz:
                    invalid_lczs_messages.append(f"The target LCZ '{target_lcz}' is not available.")

                # If both are the same and invalid, provide a simpler message.
                if original_lcz == target_lcz and original_lcz not in available_lcz_numbers:
                    invalid_lczs_messages = [f"The specified LCZ '{original_lcz}' is not available."]

                # Return a structured dictionary with the diagnosis.
                return {"invalid_messages": invalid_lczs_messages, "available": available_lczs_full_text}
            else:
                # If the error was for a different, unexpected reason, report it.
                logging.error("An unexpected error occurred during LCZ check. Could not parse available LCZs.")
                logging.error(f"STDERR:\n{e.stderr}")
                return False

        except Exception:
            # Catch any other exceptions (e.g., Java not found, invalid user input).
            return False

# def get_available_lczs(*,
#                        epw_paths: Union[str, List[str]],
#                        fwg_jar_path: str,
#                        java_class_path_prefix: str = 'futureweathergenerator',
#                        show_tool_output: bool = False) -> Dict[str, List[int]]:
#     """Gets the available Local Climate Zones (LCZs) for one or more EPW files.
#
#     This utility function iterates through a list of EPW files and runs a
#     check to determine which LCZs are available for morphing at each location.
#     It reuses the `check_lcz_availability` function by intentionally probing
#     with an invalid LCZ to trigger the error that lists all available zones.
#
#     After processing each file, it logs an INFO message summarizing the
#     available LCZs found.
#
#     Args:
#         epw_paths (Union[str, List[str]]): A single path or a list of paths
#             to the EPW files to be checked.
#         fwg_jar_path (str): Path to the `FutureWeatherGenerator.jar` file.
#         java_class_path_prefix (str, optional): The Java package prefix for the
#             tool. Defaults to 'futureweathergenerator' for the global tool.
#             Use 'futureweathergenerator_europe' for the Europe-specific tool.
#         show_tool_output (bool, optional): If True, prints the underlying
#             FWG tool's console output in real-time. Defaults to False.
#
#     Returns:
#         Dict[str, List[int]]: A dictionary where keys are the EPW filenames
#         and values are sorted lists of the available LCZ numbers (as integers).
#         If a file cannot be processed, its value will be an empty list.
#     """
#     # Determine the number of files for the initial log message.
#     num_files = len(epw_paths) if isinstance(epw_paths, list) else 1
#     logging.info(f"--- Fetching available LCZs for {num_files} EPW file(s) ---")
#
#     # Normalize the input to always be a list for consistent processing.
#     epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths
#
#     # This dictionary will store the final results.
#     results = {}
#
#     # Iterate through each provided EPW file path.
#     for epw_path in epw_files:
#         filename = os.path.basename(epw_path)
#
#         # Call the check function with an invalid LCZ (0) to force it to
#         # return the list of available zones.
#         validation_result = check_lcz_availability(
#             epw_path=epw_path,
#             original_lcz=0,  # Use an invalid LCZ to trigger the listing.
#             target_lcz=0,
#             fwg_jar_path=fwg_jar_path,
#             java_class_path_prefix=java_class_path_prefix,
#             show_tool_output=show_tool_output
#         )
#
#         # If the result is a dictionary, it contains the data we need.
#         if isinstance(validation_result, dict):
#             available_lczs_text = validation_result.get("available", [])
#             lcz_numbers = []
#             # Parse the full text lines to extract just the numbers.
#             for line in available_lczs_text:
#                 match = re.search(r'LCZ (\d+)', line)
#                 if match:
#                     lcz_numbers.append(int(match.group(1)))
#
#             # Store the sorted list of numbers in the results dictionary.
#             sorted_lczs = sorted(lcz_numbers)
#             results[filename] = sorted_lczs
#
#             # Print a clear, informative summary for the user.
#             logging.info(f"Available LCZs for '{filename}': {sorted_lczs}")
#
#         else:
#             # If the check succeeded (shouldn't happen with LCZ 0) or failed
#             # unexpectedly, log an error and return an empty list for this file.
#             logging.error(f"Could not retrieve LCZ list for '{filename}'.")
#             results[filename] = []
#
#     return results


def get_available_lczs(*,
                       epw_paths: Union[str, List[str]],
                       fwg_jar_path: str,
                       java_class_path_prefix: str = 'futureweathergenerator',
                       show_tool_output: bool = False) -> Dict[str, List[int]]:
    """Gets the available Local Climate Zones (LCZs) for one or more EPW files.

    This utility function iterates through a list of EPW files and runs a
    check to determine which LCZs are available for morphing at each location.
    It reuses the `check_lcz_availability` function by intentionally probing
    with an invalid LCZ to trigger the error that lists all available zones.

    After processing each file, it logs an INFO message summarizing the
    available LCZs found.

    Args:
        epw_paths (Union[str, List[str]]): A single path or a list of paths
            to the EPW files to be checked.
        fwg_jar_path (str): Path to the `FutureWeatherGenerator.jar` file.
        java_class_path_prefix (str, optional): The Java package prefix for the
            tool. Defaults to 'futureweathergenerator' for the global tool.
            Use 'futureweathergenerator_europe' for the Europe-specific tool.
        show_tool_output (bool, optional): If True, prints the underlying
            FWG tool's console output in real-time. Defaults to False.

    Returns:
        Dict[str, List[int]]: A dictionary where keys are the EPW filenames
        and values are sorted lists of the available LCZ numbers (as integers).
        If a file cannot be processed, its value will be an empty list.
    """
    # Determine the number of files for the initial log message.
    num_files = len(epw_paths) if isinstance(epw_paths, list) else 1
    logging.info(f"--- Fetching available LCZs for {num_files} EPW file(s) ---")

    # Normalize the input to always be a list for consistent processing.
    epw_files = [epw_paths] if isinstance(epw_paths, str) else epw_paths

    # This dictionary will store the final results.
    results = {}

    # Iterate through each provided EPW file path.
    for epw_path in epw_files:
        filename = os.path.basename(epw_path)

        # Call the check function with an invalid LCZ (0) to force it to
        # return the list of available zones.
        validation_result = check_lcz_availability(
            epw_path=epw_path,
            original_lcz=0,  # Use an invalid LCZ to trigger the listing.
            target_lcz=0,
            fwg_jar_path=fwg_jar_path,
            java_class_path_prefix=java_class_path_prefix,
            show_tool_output=show_tool_output
        )

        # If the result is a dictionary, it contains the data we need.
        if isinstance(validation_result, dict):
            available_lczs_text = validation_result.get("available", [])
            lcz_numbers = []
            # Parse the full text lines to extract just the numbers.
            for line in available_lczs_text:
                match = re.search(r'LCZ (\d+)', line)
                if match:
                    lcz_numbers.append(int(match.group(1)))

            # Store the sorted list of numbers in the results dictionary.
            sorted_lczs = sorted(lcz_numbers)
            results[filename] = sorted_lczs

            # Print a clear, informative summary for the user.
            logging.info(f"Available LCZs for '{filename}': {sorted_lczs}")

        else:
            # If the check succeeded (shouldn't happen with LCZ 0) or failed
            # unexpectedly, log an error and return an empty list for this file.
            logging.error(f"Could not retrieve LCZ list for '{filename}'.")
            results[filename] = []

    return results


def export_template_to_excel(iterator, file_path: str = 'runs_template.xlsx'):
    """Generates and exports a run template DataFrame to an Excel file.

    This function uses the iterator's `get_template_dataframe` method to create
    a blank template and saves it as an Excel file, ready for the user to
    fill in with different runs.

    Args:
        iterator (MorphingIterator): An initialized MorphingIterator instance.
        file_path (str, optional): The path where the Excel file will be saved.
            Defaults to 'runs_template.xlsx'.
    """
    logging.info(f"Generating Excel template for {iterator.workflow_class.__name__}...")
    template_df = iterator.get_template_dataframe()

    # Export to Excel, ensuring the DataFrame index is not written to the file.
    template_df.to_excel(file_path, index=False)
    logging.info(f"Template successfully exported to '{os.path.abspath(file_path)}'")


def load_runs_from_excel(file_path: str) -> pd.DataFrame:
    """Loads a DataFrame of runs from an Excel file, converting data types correctly.

    This function reads an Excel file into a Pandas DataFrame and then performs
    crucial data type conversions. It intelligently converts string representations
    of lists (e.g., "['CanESM5', 'MIROC6']") back into actual Python lists,
    which is essential for the iterator to function correctly.

    Args:
        file_path (str): The path to the Excel file containing the runs.

    Returns:
        pd.DataFrame: A DataFrame with the data types corrected and ready for use
        with the MorphingIterator.
    """
    logging.info(f"Loading runs from '{file_path}'...")

    # Read the Excel file into a DataFrame.
    df = pd.read_excel(file_path)

    # Define columns that are expected to contain lists.
    list_like_columns = ['epw_paths', 'fwg_gcms', 'fwg_rcm_pairs', 'keyword_mapping']

    # Iterate through the columns that might need type conversion.
    for col in df.columns:
        if col in list_like_columns:
            # Use ast.literal_eval to safely convert string representations of lists/dicts
            # back into Python objects. It's much safer than using eval().
            df[col] = df[col].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith(('[', '{')) else x
            )

    logging.info("Runs loaded and data types converted successfully.")
    return df
