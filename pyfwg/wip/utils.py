# pyfwg/utils.py

import os
import shutil
import logging
import subprocess
import tempfile
import time
import re
from typing import List, Union, Dict


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


def uhi_morph(*,
              fwg_epw_path: str,
              fwg_jar_path: str,
              fwg_output_dir: str,
              fwg_original_lcz: int,
              fwg_target_lcz: int,
              java_class_path_prefix: str,
              fwg_limit_variables: bool = True,
              show_tool_output: bool = False):
    """Applies only the Urban Heat Island (UHI) effect to an EPW file.

    This function is a direct wrapper for the `UHI_Morph` class within the
    FutureWeatherGenerator tool. It modifies an EPW file to reflect the
    climate of a different Local Climate Zone (LCZ) without applying future
    climate change scenarios.

    Args:
        fwg_epw_path (str): Path to the source EPW file.
        fwg_jar_path (str): Path to the `FutureWeatherGenerator.jar` file.
        fwg_output_dir (str): Directory where the final UHI-morphed file will be saved.
        fwg_original_lcz (int): The LCZ of the original EPW file (1-17).
        fwg_target_lcz (int): The target LCZ for which to calculate the UHI effect (1-17).
        java_class_path_prefix (str): The Java package prefix, which differs
            between tool versions (e.g., 'futureweathergenerator' or
            'futureweathergenerator_europe').
        fwg_limit_variables (bool, optional): If True, bounds variables to their
            physical limits. Defaults to True.
        show_tool_output (bool, optional): If True, prints the tool's console
            output in real-time. Defaults to False.

    Raises:
        ValueError: If LCZ values are out of the valid range (1-17).
        FileNotFoundError: If the 'java' command is not found.
        subprocess.CalledProcessError: If the FWG tool returns a non-zero exit code.
    """
    logging.info(f"--- Applying UHI effect to {os.path.basename(fwg_epw_path)} ---")

    # --- 1. Parameter Validation ---
    if not 1 <= fwg_original_lcz <= 17: raise ValueError("'fwg_original_lcz' must be between 1 and 17.")
    if not 1 <= fwg_target_lcz <= 17: raise ValueError("'fwg_target_lcz' must be between 1 and 17.")

    # Ensure the output directory exists.
    os.makedirs(fwg_output_dir, exist_ok=True)

    # --- 2. Command Construction ---
    # Create the composite LCZ argument string (e.g., "14:2").
    lcz_options = f"{fwg_original_lcz}:{fwg_target_lcz}"

    # Dynamically build the full Java class path using the provided prefix.
    class_path = f"{java_class_path_prefix}.UHI_Morph"

    # Build the command as a list of strings for robust execution.
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

    # --- 3. Subprocess Execution ---
    # Determine whether to show the tool's output live or capture it.
    stdout_dest = None if show_tool_output else subprocess.PIPE
    stderr_dest = None if show_tool_output else subprocess.PIPE

    try:
        # Run the command. The `check=True` flag will cause it to raise
        # CalledProcessError if the Java program returns a non-zero exit code.
        subprocess.run(command, text=True, check=True, timeout=300, stdout=stdout_dest, stderr=stderr_dest)
        logging.info("UHI effect applied successfully.")
    except FileNotFoundError:
        logging.error("Error: 'java' command not found. Please ensure Java is installed and in the system's PATH.")
        raise
    except subprocess.CalledProcessError as e:
        # Handle errors from the Java tool itself.
        logging.error("The UHI_Morph tool returned an error.")
        if e.stdout: logging.error(f"STDOUT:\n{e.stdout}")
        if e.stderr: logging.error(f"STDERR:\n{e.stderr}")
        raise
    except Exception as e:
        # Handle other potential errors.
        logging.error(f"An unexpected error occurred: {e}")
        raise


def check_lcz_availability(*,
                           epw_path: str,
                           original_lcz: int,
                           target_lcz: int,
                           fwg_jar_path: str,
                           java_class_path_prefix: str) -> Union[bool, Dict[str, List]]:
    """Checks if the specified original and target LCZs are available for a given EPW file.

    This utility function internally calls `uhi_morph` in a temporary directory
    to validate the LCZ pair. If the tool fails because an LCZ is unavailable,
    this function intelligently parses the error message to determine which of
    the input LCZs was invalid.

    It is designed to be used as a pre-flight check before running a full
    morphing workflow, providing precise feedback to the user.

    Args:
        epw_path (str): Path to the source EPW file to check.
        original_lcz (int): The original LCZ number (1-17) you want to validate.
        target_lcz (int): The target LCZ number (1-17) you want to validate.
        fwg_jar_path (str): Path to the `FutureWeatherGenerator.jar` file.
        java_class_path_prefix (str): The Java package prefix for the tool
            (e.g., 'futureweathergenerator').

    Returns:
        Union[bool, Dict[str, List]]:
        - `True` if both LCZs are available.
        - A dictionary with keys 'invalid_messages' (listing specific errors)
          and 'available' (listing valid LCZ descriptions) if validation fails.
        - `False` if an unexpected error occurs.
    """
    logging.info(f"Checking LCZ pair (Original: {original_lcz}, Target: {target_lcz}) availability for {os.path.basename(epw_path)}...")

    # Use a temporary directory that is automatically created and cleaned up.
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Call uhi_morph once. It will raise CalledProcessError on failure.
            uhi_morph(
                fwg_epw_path=epw_path,
                fwg_jar_path=fwg_jar_path,
                fwg_output_dir=temp_dir,
                fwg_original_lcz=original_lcz,
                fwg_target_lcz=target_lcz,
                java_class_path_prefix=java_class_path_prefix,
                show_tool_output=False  # Always run silently for checks.
            )
            # If no exception was raised, the LCZ pair is valid.
            logging.info(f"LCZ pair (Original: {original_lcz}, Target: {target_lcz}) is available.")
            return True

        except subprocess.CalledProcessError as e:
            # If the tool failed, parse its output to find the available LCZs.
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

                # If both are the same and invalid, the message is simpler.
                if original_lcz == target_lcz and original_lcz not in available_lcz_numbers:
                    invalid_lczs_messages = [f"The specified LCZ '{original_lcz}' is not available."]

                # Return a structured dictionary with the diagnosis.
                return {
                    "invalid_messages": invalid_lczs_messages,
                    "available": available_lczs_full_text
                }
            else:
                # If the error was for a different, unexpected reason, report it.
                logging.error("An unexpected error occurred during LCZ check. Could not parse available LCZs.")
                logging.error(f"STDERR:\n{e.stderr}")
                return False

        except Exception:
            # Catch any other exceptions (e.g., Java not found, invalid user input).
            return False