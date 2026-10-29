# pyfwg/utils.py

import os
import sys
import copy
import json
import math
import numbers
import shutil
import logging
import subprocess
import tempfile
import time
import re
import zipfile
from functools import lru_cache
from typing import List, Union, Dict, Optional, Any
import ast
import numpy as np
import pandas as pd
from datetime import datetime

# Import constants from the local constants.py file
from .constants import (
    DEFAULT_GLOBAL_GCMS, GLOBAL_SCENARIOS,
    DEFAULT_EUROPE_RCMS, EUROPE_SCENARIOS,
    CORDEX_REGIONS,
    ALL_POSSIBLE_YEARS,
    FWG_CLI_POSITIONAL, FWG_CLI_KEY_VALUE, FWG_CLI_ENGINE,
    ENGINE_INTERPOLATION_METHODS, ENGINE_DECOMPOSITION_METHODS,
    ENGINE_ILLUMINANCE_METHODS, ENGINE_INFRARED_METHODS,
    ENGINE_MORPHING_METHODS, ENGINE_UNCERTAINTY_VARIANTS,
    ENGINE_OUTPUT_PROFILES
)

logger = logging.getLogger(__name__)

# Locations of the metadata packaged inside FWG Engine JARs.
_ENGINE_RESOURCES_DIR = 'futureweathergenerator/resources/'
_ENGINE_VERSION_PROPERTIES = 'futureweathergenerator/version.properties'

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
        logger.error(f"Could not find the tutorials sub-package '{source_package}'. The package might be corrupted.")
        return

    # Create the destination directory if it doesn't already exist.
    os.makedirs(dest_dir, exist_ok=True)

    logger.info(f"Copying tutorials to '{os.path.abspath(dest_dir)}'...")

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
                logger.info(f"  - Copied directory: {item_name}")
            else:
                # If the item is a file, copy it directly.
                shutil.copy2(source_item_path, dest_path)
                logger.info(f"  - Copied file: {item_name}")

    logger.info("Tutorials copied successfully.")

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
            logger.warning(f"PermissionError deleting {path}. Retrying in {delay}s... (Attempt {i + 1}/{max_retries})")
            time.sleep(delay)
    # If all retries fail, log a final error.
    logger.error(f"Failed to delete directory {path} after {max_retries} retries.")


def _parse_java_properties(text: str) -> Dict[str, str]:
    """(Private) Parses the simple 'key=value' lines of a Java .properties file."""
    properties = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(('#', '!')):
            continue
        key, separator, value = line.partition('=')
        if not separator:
            key, separator, value = line.partition(':')
        if separator:
            properties[key.strip()] = value.strip()
    return properties


def _normalize_scenario_id(value: Any) -> str:
    """(Private) Normalizes a scenario name for comparison (e.g., 'SSP2-4.5' -> 'ssp245')."""
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def _to_bool(value: Any, name: str = 'value') -> bool:
    """(Private) Converts a flag strictly into a boolean.

    Accepts booleans (also NumPy's), the numbers 0 and 1 (e.g., 1.0 read from
    Excel) and the strings 'true', 'false', '1' and '0' in any case.

    Args:
        value (Any): The value to convert.
        name (str, optional): Name of the argument, used in the error message.

    Raises:
        ValueError: For any other value (e.g., 2, 'yes' or None).
    """
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, numbers.Real) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ('true', '1'):
            return True
        if text in ('false', '0'):
            return False
    raise ValueError(f"'{name}' must be True or False, but got {value!r}.")


def _as_integer(value: Any) -> Optional[int]:
    """(Private) Returns the integer value of an integer, of a float without decimals
    (e.g., 14.0, as pandas reads integer columns with gaps) or of a numeric string.

    Returns None for any other value, including booleans and floats with decimals (e.g., 14.5).
    """
    if isinstance(value, (bool, np.bool_)):
        return None
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        value = float(value)
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text)
        except ValueError:
            try:
                number = float(text)
            except ValueError:
                return None
            return int(number) if number.is_integer() else None
    return None


def _as_number(value: Any) -> Optional[Union[int, float]]:
    """(Private) Returns a finite number as a Python int or float (also from NumPy numbers
    or numeric strings), keeping integers as integers. Returns None for any other value.
    """
    if isinstance(value, (bool, np.bool_)):
        return None
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text)
        except ValueError:
            pass
        try:
            number = float(text)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


@lru_cache(maxsize=16)
def _read_distribution_info(jar_path: str, mtime_ns: int, size: int) -> Optional[Dict[str, Any]]:
    """(Private) Reads and caches the distribution metadata of an FWG Engine JAR.

    The modification time and size are part of the cache key so that a JAR
    replaced at the same path is read again.
    """
    try:
        with zipfile.ZipFile(jar_path) as jar:
            names = set(jar.namelist())
            manifest_entry = _ENGINE_RESOURCES_DIR + 'distribution-manifest.json'
            if manifest_entry not in names:
                # JARs prior to the FWG Engine (Global v3/v4, Europe v1/v2) have no manifest.
                return None

            def read_json(entry: str) -> Dict[str, Any]:
                return json.loads(jar.read(entry).decode('utf-8-sig'))

            manifest = read_json(manifest_entry)
            distribution = manifest.get('distribution') or {}
            climate_source = manifest.get('climateSource') or {}
            domain = manifest.get('domain') or {}

            def ordered_ids(entries: Any) -> List[str]:
                entries = [entry for entry in (entries or []) if isinstance(entry, dict) and entry.get('id')]
                entries.sort(key=lambda entry: entry.get('order', 0))
                return [str(entry['id']) for entry in entries]

            scenarios = [_normalize_scenario_id(s) for s in ordered_ids(manifest.get('scenarios'))]
            timeframes = ordered_ids(manifest.get('timeframes'))

            # The climate-model catalog lists the installed products. From schema 1.2
            # onwards, each entry points to a model manifest with its scenarios, future
            # periods and ensemble eligibility.
            model_details = {}
            catalog_entry = _ENGINE_RESOURCES_DIR + 'climate-model-catalog.json'
            if catalog_entry in names:
                for entry in read_json(catalog_entry).get('models') or []:
                    if not isinstance(entry, dict) or not entry.get('id'):
                        continue
                    source = entry
                    model_manifest_entry = _ENGINE_RESOURCES_DIR + str(entry.get('manifest', ''))
                    if entry.get('manifest') and model_manifest_entry in names:
                        source = read_json(model_manifest_entry)
                    if source.get('futurePeriods'):
                        model_timeframes = [str(p.get('timeframe')) for p in source['futurePeriods']
                                            if isinstance(p, dict) and p.get('timeframe')]
                    else:
                        model_timeframes = [str(t) for t in source.get('timeframes') or []]
                    model_details[str(entry['id'])] = {
                        'display_name': source.get('displayName'),
                        'ensemble_eligible': bool(source.get('ensembleEligible', True)),
                        'scenarios': [_normalize_scenario_id(s) for s in source.get('scenarios') or []],
                        'timeframes': model_timeframes,
                        'components': source.get('components'),
                        'grid_topology': ((source.get('grid') or {}).get('coordinateReference') or {}).get('topology'),
                    }

            engine_version = None
            if _ENGINE_VERSION_PROPERTIES in names:
                properties = _parse_java_properties(
                    jar.read(_ENGINE_VERSION_PROPERTIES).decode('utf-8', errors='replace'))
                engine_version = properties.get('version')
    except (OSError, zipfile.BadZipFile, ValueError, KeyError, TypeError, AttributeError) as e:
        logger.debug(f"Could not read FWG distribution metadata from '{jar_path}': {e}")
        return None

    # Classify the distribution into the tool families handled by pyfwg.
    framework = str(climate_source.get('framework', '')).upper()
    grid_domain = domain.get('gridDomain') or None
    if framework == 'CMIP' or str(domain.get('type', '')).lower() == 'global':
        tool = 'global'
    elif grid_domain and str(grid_domain).upper() == 'EUR-11':
        tool = 'europe'
    elif framework == 'CORDEX' or grid_domain:
        tool = 'cordex'
    else:
        tool = None

    return {
        'engine_version': engine_version,
        'distribution_id': distribution.get('id'),
        'name': distribution.get('name'),
        'version': distribution.get('version'),
        'tool': tool,
        'scenario_family': distribution.get('scenarioFamily'),
        'framework': climate_source.get('framework'),
        'cmip_generation': climate_source.get('cmipGeneration'),
        'domain': grid_domain,
        'region': domain.get('region'),
        'scenarios': scenarios,
        'timeframes': timeframes,
        'models': list(model_details),
        'ensemble_models': [model for model, details in model_details.items() if details['ensemble_eligible']],
        'model_details': model_details,
    }


def get_fwg_distribution_info(jar_path: str) -> Optional[Dict[str, Any]]:
    """Reads the metadata packaged inside an FWG Engine distribution JAR.

    Since FWG Global v5, Europe v3 and the CORDEX regional distributions, all
    distributions share the FWG Engine and package a distribution manifest and a
    climate-model catalog inside the JAR. This function reads them directly from
    the JAR file (no Java needed), so that the scenarios, future periods and
    climate models actually installed in a distribution can be inspected and
    validated.

    Args:
        jar_path (str): Path to the FWG JAR file.

    Returns:
        Optional[Dict[str, Any]]: A dictionary with the keys 'engine_version',
        'distribution_id', 'name', 'version', 'tool' ('global', 'europe' or
        'cordex'), 'scenario_family', 'framework', 'cmip_generation', 'domain'
        (e.g., 'NAM-44'), 'region', 'scenarios' (e.g., ['rcp45', 'rcp85']),
        'timeframes' (e.g., ['2050', '2080']), 'models', 'ensemble_models' and
        'model_details' (including each model's 'grid_topology', when declared).
        Returns None if the file does not exist, cannot be read,
        or is a JAR prior to the FWG Engine (Global v3/v4, Europe v1/v2).
    """
    try:
        stat = os.stat(jar_path)
    except (OSError, TypeError, ValueError):
        return None
    info = _read_distribution_info(os.path.abspath(jar_path), stat.st_mtime_ns, stat.st_size)
    # Return a copy so that callers cannot modify the cached dictionary.
    return copy.deepcopy(info)


def detect_fwg_version(jar_path: str) -> str:
    """Detects the major version of the Future Weather Generator distribution.

    For FWG Engine distributions (Global v5+, Europe v3+ and the CORDEX regional
    distributions), the version is read from the distribution manifest packaged
    inside the JAR. Otherwise, it is detected from the JAR filename, which must
    contain the version (e.g., 'FutureWeatherGenerator_v4.0.2.jar' or
    'FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar').

    Args:
        jar_path (str): The path to the FWG JAR file.

    Returns:
        str: The major version number as a string (e.g., "5", "4", "3").

    Raises:
        ValueError: If the version cannot be detected.
    """
    info = get_fwg_distribution_info(jar_path)
    if info and info.get('version'):
        match = re.match(r'\s*v?(\d+)', str(info['version']))
        if match:
            return match.group(1)

    filename = os.path.basename(jar_path)
    # Look for 'v' followed by digits and a dot (e.g., 'v4.', 'v3.')
    match = re.search(r'v(\d+)\.', filename)
    if match:
        return match.group(1)
    else:
        raise ValueError(
            f"Could not auto-detect FWG version from filename '{filename}'. "
            "Please rename the file to include the version (e.g., 'FutureWeatherGenerator_v4.0.2.jar' or "
            "'FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar') or explicitly provide the 'fwg_version' argument."
        )


def _detect_cordex_domain(jar_path: str) -> Optional[str]:
    """(Private) Returns the CORDEX domain (e.g., 'NAM-44') of a JAR, or None if unknown."""
    info = get_fwg_distribution_info(jar_path)
    if info and info.get('domain'):
        return str(info['domain']).upper()
    filename = os.path.basename(jar_path).upper()
    for domain in CORDEX_REGIONS:
        if re.search(rf'(?<![A-Z0-9]){re.escape(domain)}(?![0-9])', filename):
            return domain
    return None


def detect_fwg_tool(jar_path: str) -> Optional[str]:
    """Detects which Future Weather Generator distribution a JAR belongs to.

    The distribution manifest packaged inside FWG Engine JARs is used when
    available. Otherwise, the JAR filename is inspected (e.g.,
    'FutureWeatherGenerator_Europe_v2.0.2.jar' or
    'FutureWeatherGenerator-CORDEX-CMIP5-North-America-NAM-44-v1.2.0.jar').

    Args:
        jar_path (str): The path to the FWG JAR file.

    Returns:
        Optional[str]: 'global', 'europe', 'cordex' (CORDEX regional
        distributions other than Europe) or 'portugal'. Returns None if the
        distribution cannot be identified.
    """
    info = get_fwg_distribution_info(jar_path)
    if info and info.get('tool'):
        return info['tool']
    filename = os.path.basename(jar_path).lower()
    if 'portugal' in filename:
        return 'portugal'
    domain = _detect_cordex_domain(jar_path)
    if 'europe' in filename or domain == 'EUR-11':
        return 'europe'
    if 'cordex' in filename or domain:
        return 'cordex'
    if 'global' in filename or 'cmip6' in filename or re.match(r'futureweathergenerator_v\d', filename):
        return 'global'
    return None


def get_fwg_cli_style(fwg_version: Union[str, int], tool: str = 'global') -> str:
    """Returns the command-line interface style used by a version of the tool.

    - 'positional' (``FWG_CLI_POSITIONAL``): Global v3.x and Europe v1.x.
    - 'key_value' (``FWG_CLI_KEY_VALUE``): Global v4.x and Europe v2.x.
    - 'engine' (``FWG_CLI_ENGINE``): FWG Engine distributions, i.e., Global v5+,
      Europe v3+ and all CORDEX regional distributions.

    Args:
        fwg_version (Union[str, int]): The version of the tool (e.g., '5' or '5.2.0').
        tool (str, optional): 'global', 'europe' or 'cordex'. Defaults to 'global'.

    Returns:
        str: The CLI style.

    Raises:
        ValueError: If the version or the tool are not valid.
    """
    match = re.match(r'\s*v?(\d+)', str(fwg_version))
    if not match:
        raise ValueError(f"Invalid FWG version: '{fwg_version}'.")
    major = int(match.group(1))
    tool = (tool or 'global').lower()

    if tool == 'cordex':
        # The regional distributions were released directly on the FWG Engine.
        return FWG_CLI_ENGINE
    if tool == 'europe':
        last_positional_version, key_value_version = 1, 2
    elif tool == 'global':
        last_positional_version, key_value_version = 3, 4
    else:
        raise ValueError(f"Unsupported FWG tool: '{tool}'. Expected 'global', 'europe' or 'cordex'.")

    if major <= last_positional_version:
        return FWG_CLI_POSITIONAL
    if major == key_value_version:
        return FWG_CLI_KEY_VALUE
    return FWG_CLI_ENGINE

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
              java_class_path_prefix: Optional[str] = None,
              fwg_limit_variables: bool = True,
              show_tool_output: bool = False,
              raise_on_error: bool = True,
              fwg_version: Optional[Union[str, int]] = None):
    """Applies only the Urban Heat Island (UHI) effect to an EPW file.

    This function is a direct wrapper for the `UHI_Morph` class within the
    Future Weather Generator tool. It modifies an EPW file to reflect the
    climate of a different Local Climate Zone (LCZ) without applying future
    climate change scenarios.

    The UHI effect is only available in Global v3.x/v4.x and Europe v1.x/v2.x.
    The FWG Engine distributions (Global v5+, Europe v3+ and the CORDEX regional
    distributions) no longer support it, so this function raises a ValueError
    for their JAR files.

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
        java_class_path_prefix (str, optional): The Java package prefix for the tool
            (e.g., 'futureweathergenerator' or 'futureweathergenerator_europe'). 
            If None, it will be auto-detected from the JAR filename.
        fwg_limit_variables (bool, optional): If True, bounds variables to their
            physical limits. Defaults to True.
        show_tool_output (bool, optional): If True, prints the tool's console
            output in real-time. Defaults to False.
        raise_on_error (bool, optional): If True, the function will raise an
            exception if the external tool fails. If False, it will log the
            error but not stop the program, allowing the calling function to
            handle the failure. Defaults to True.
        fwg_version (Optional[Union[str, int]], optional): Explicitly provide
            the FWG version. If None, it will be auto-detected.

    Returns:
        bool: True if the UHI effect was applied. False if it could not be
        applied and `raise_on_error` is False.

    Raises:
        FileNotFoundError: If the 'java' command is not found and `raise_on_error` is True.
        subprocess.CalledProcessError: If the FWG tool returns a non-zero exit code
            and `raise_on_error` is True.
        subprocess.TimeoutExpired: If the FWG tool does not finish in time and
            `raise_on_error` is True.
        ValueError: If the version cannot be detected, the JAR is an FWG Engine
            distribution (without UHI support) or the LCZs are not integers, and
            `raise_on_error` is True.
    """
    logger.info(f"--- Applying UHI effect to {os.path.basename(fwg_epw_path)} ---")

    try:
        # --- 0. Resolve FWG Version ---
        version_str = detect_fwg_version(fwg_jar_path) if fwg_version is None else str(fwg_version)

        # --- 1. Auto-detect Class Path Prefix ---
        if java_class_path_prefix is None:
            if 'europe' in os.path.basename(fwg_jar_path).lower():
                java_class_path_prefix = 'futureweathergenerator_europe'
            else:
                java_class_path_prefix = 'futureweathergenerator'

        is_europe = 'europe' in java_class_path_prefix.lower()
        detected_tool = detect_fwg_tool(fwg_jar_path)
        tool = detected_tool if detected_tool in ('europe', 'cordex') else ('europe' if is_europe else 'global')
        cli_style = get_fwg_cli_style(version_str, tool)

        if cli_style == FWG_CLI_ENGINE:
            raise ValueError(
                f"UHI morphing is not available in '{os.path.basename(fwg_jar_path)}'. The FWG Engine distributions "
                "(Global v5+, Europe v3+ and CORDEX regional) do not support the Urban Heat Island effect. "
                "Use FWG Global v4.x/v3.x or Europe v2.x/v1.x to apply it."
            )

        # The tool expects integer LCZs (e.g., 14.0, as read from Excel, is passed as 14).
        original_lcz = _as_integer(fwg_original_lcz)
        target_lcz = _as_integer(fwg_target_lcz)
        if original_lcz is None or target_lcz is None:
            raise ValueError(
                f"The LCZs must be integers, but got {fwg_original_lcz!r} (original) and {fwg_target_lcz!r} (target).")
        limit_variables = _to_bool(fwg_limit_variables, 'fwg_limit_variables')
    except ValueError as e:
        if raise_on_error:
            raise
        logger.error(f"UHI morphing could not be started: {e}")
        return False

    # Ensure the output directory exists before running the tool.
    os.makedirs(fwg_output_dir, exist_ok=True)

    # --- 1. Command Construction ---
    if cli_style == FWG_CLI_KEY_VALUE:
        # --- New CLI Style (Global v4 / Europe v2) Logic ---
        # UHI Morphing is triggered via flags
        # java -jar FWG.jar -epw=... -output_folder=... -uhi=true:orig:target ...

        # Construct the command with named arguments
        command = [
            'java', '-jar', fwg_jar_path,
            '-u',  # <--- CRITICAL FIX: This flag tells the tool to run ONLY UHI mode (no climate models)
            f'-epw={os.path.abspath(fwg_epw_path)}',
            # Note: The tool typically expects output_folder to end with slash
            f'-output_folder={os.path.abspath(fwg_output_dir)}{os.sep}',
            # UHI flag: -uhi=true:orig:target
            f'-uhi=true:{original_lcz}:{target_lcz}',
            # Explicitly request EPW output if needed
            f'-output_type=EPW'
        ]
        
        # Note: The tool might typically run a full morphing process. 
        # For UHI-only, we pass specific flags.
        
    else:
        # --- Legacy (v3.x / Europe v1.x) Logic ---
        # Create the composite LCZ argument string (e.g., "14:2").
        lcz_options = f"{original_lcz}:{target_lcz}"

        # Dynamically build the full Java class path using the provided prefix.
        class_path = f"{java_class_path_prefix}.UHI_Morph"

        # Build the command as a list of strings for robust execution by subprocess.
        command = [
            'java', '-cp', fwg_jar_path, class_path,
            os.path.abspath(fwg_epw_path),
            os.path.abspath(fwg_output_dir) + '/',
            str(limit_variables).lower(),
            lcz_options
        ]

    # Create a user-friendly, copy-pasteable version of the command for logging.
    printable_command = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in command)
    logger.info(f"Executing command: {printable_command}")

    # --- 2. Subprocess Execution ---
    # Determine whether to show the tool's output live or capture it.
    stdout_dest = None if show_tool_output else subprocess.PIPE
    stderr_dest = None if show_tool_output else subprocess.PIPE

    try:
        # Run the command. The `check=True` flag will cause it to raise
        # CalledProcessError if the Java program returns a non-zero exit code.
        subprocess.run(command, text=True, check=True, timeout=300, stdout=stdout_dest, stderr=stderr_dest)
    except Exception as e:
        # --- 3. Error Handling ---
        # The exception is raised unchanged, without logging it, so that callers such as
        # check_lcz_availability can handle it silently.
        if raise_on_error:
            raise
        # Otherwise, the error is logged and the program continues.
        if isinstance(e, FileNotFoundError):
            logger.error("Error: 'java' command not found. Please ensure Java is installed and in the system's PATH.")
        elif isinstance(e, subprocess.CalledProcessError):
            logger.error(f"The UHI_Morph tool returned an error (exit code {e.returncode}).")
            # If output was captured, log it now.
            if e.stdout: logger.error(f"STDOUT:\n{e.stdout}")
            if e.stderr: logger.error(f"STDERR:\n{e.stderr}")
        elif isinstance(e, subprocess.TimeoutExpired):
            logger.error(f"The UHI_Morph tool did not finish within {e.timeout} seconds.")
        else:
            logger.error(f"An unexpected error occurred while applying the UHI effect: {e}")
        return False

    logger.info("UHI effect applied successfully.")
    return True


def check_lcz_availability(*,
                           epw_path: str,
                           original_lcz: int,
                           target_lcz: int,
                           fwg_jar_path: str,
                           java_class_path_prefix: Optional[str] = None,
                           show_tool_output: bool = False,
                           fwg_version: Optional[Union[str, int]] = None) -> Union[bool, Dict[str, List]]:
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
        java_class_path_prefix (str, optional): The Java package prefix for the 
            tool. If None, it will be auto-detected from the JAR filename.
        show_tool_output (bool, optional): If True, prints the underlying
            FWG tool's console output in real-time. This is useful for
            debugging the check itself. Defaults to False.
        fwg_version (Optional[Union[str, int]], optional): Explicitly provide 
            the FWG version. If None, it will be auto-detected.

    Returns:
        Union[bool, Dict[str, List]]:
        - `True` if both LCZs are available.
        - A dictionary with keys 'invalid_messages' (listing specific errors)
          and 'available' (listing valid LCZ descriptions) if validation fails
          due to unavailable LCZs.
        - `False` if an unexpected error occurs (e.g., Java not found).
    """
    logger.info(f"Checking LCZ pair (Original: {original_lcz}, Target: {target_lcz}) availability for {os.path.basename(epw_path)}...")

    # Use a temporary directory that is automatically created and cleaned up,
    # preventing leftover files from the check.
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Copy and sanitize the EPW file in the temp directory to avoid Java MinuteOfHour: 60 errors
            temp_epw_path = os.path.join(temp_dir, os.path.basename(epw_path))
            shutil.copy2(epw_path, temp_epw_path)
            sanitize_epw_minutes(temp_epw_path)

            # Call uhi_morph. It is expected to raise a CalledProcessError if
            # the LCZs are invalid, which we will catch and handle.
            # CRITICAL: We MUST set show_tool_output=False here so that
            # subprocess captures the output in the exception object.
            uhi_morph(
                fwg_epw_path=temp_epw_path,
                fwg_jar_path=fwg_jar_path,
                fwg_output_dir=temp_dir,
                fwg_original_lcz=original_lcz,
                fwg_target_lcz=target_lcz,
                java_class_path_prefix=java_class_path_prefix,
                show_tool_output=False,  # Always capture internally
                raise_on_error=True,
                fwg_version=fwg_version
            )
            # If no exception was raised, the LCZ pair is valid.
            logger.info(f"LCZ pair (Original: {original_lcz}, Target: {target_lcz}) is available.")
            return True

        except subprocess.CalledProcessError as e:
            # If the user wanted to see the output, print it now since we captured it.
            if show_tool_output:
                if e.stdout: print(e.stdout.strip())
                if e.stderr: print(e.stderr.strip(), file=sys.stderr)

            # Combine stdout and stderr to ensure we capture the full error message.
            # Use 'or ""' to avoid TypeError if they are None for some reason.
            output = (e.stdout or "") + (e.stderr or "")
            available_lczs_full_text = []
            available_lcz_numbers = set()
            start_parsing = False

            # Iterate through the captured output line by line.
            for line in output.splitlines():
                # The line "The LCZs available are:" is our trigger to start parsing.
                if 'The LCZs available are:' in line:
                    start_parsing = True
                    # Use only the part after the trigger to avoid matching the requested (invalid) LCZ
                    parts = line.split('The LCZs available are:')
                    relevant_text = parts[1] if len(parts) > 1 else ""
                elif start_parsing:
                    relevant_text = line
                else:
                    continue

                # Look for lines containing LCZ information.
                # Use regex to safely extract the LCZ number from the text.
                match = re.search(r'LCZ (\d+)', relevant_text)
                if match:
                    # Store the number for logical checks and the full text for display.
                    available_lcz_numbers.add(int(match.group(1)))
                    available_lczs_full_text.append(relevant_text.strip())

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
                logger.error("An unexpected error occurred during LCZ check. Could not parse available LCZs.")
                logger.error(f"STDERR:\n{e.stderr}")
                return False

        except Exception as e:
            # Catch any other exceptions (e.g., Java not found, invalid user input,
            # or an FWG Engine JAR, which does not support UHI).
            logger.error(f"LCZ availability check could not be completed: {e}")
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
                       java_class_path_prefix: Optional[str] = None,
                       show_tool_output: bool = False,
                       fwg_version: Optional[Union[str, int]] = None) -> Dict[str, List[int]]:
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
            tool. If None (default), it will be auto-detected from the JAR
            filename (contains 'europe' -> 'futureweathergenerator_europe',
            else 'futureweathergenerator').
        show_tool_output (bool, optional): If True, prints the underlying
            FWG tool's console output in real-time. Defaults to False.
        fwg_version (Optional[Union[str, int]], optional): Explicitly provide 
            the FWG version. If None, it will be auto-detected.

    Returns:
        Dict[str, List[int]]: A dictionary where keys are the EPW filenames
        and values are sorted lists of the available LCZ numbers (as integers).
        If a file cannot be processed, its value will be an empty list.
    """
    # --- Auto-detect Class Path Prefix ---
    if java_class_path_prefix is None:
        if 'europe' in os.path.basename(fwg_jar_path).lower():
            java_class_path_prefix = 'futureweathergenerator_europe'
        else:
            java_class_path_prefix = 'futureweathergenerator'

    # Determine the number of files for the initial log message.
    num_files = len(epw_paths) if isinstance(epw_paths, list) else 1
    logger.info(f"--- Fetching available LCZs for {num_files} EPW file(s) ---")

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

            show_tool_output=show_tool_output,
            fwg_version=fwg_version
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
            logger.info(f"Available LCZs for '{filename}': {sorted_lczs}")

        else:
            # If the check succeeded (shouldn't happen with LCZ 0) or failed
            # unexpectedly, log an error and return an empty list for this file.
            logger.error(f"Could not retrieve LCZ list for '{filename}'.")
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
    logger.info(f"Generating Excel template for {iterator.workflow_class.__name__}...")
    template_df = iterator.get_template_dataframe()

    # Export to Excel, ensuring the DataFrame index is not written to the file.
    template_df.to_excel(file_path, index=False)
    logger.info(f"Template successfully exported to '{os.path.abspath(file_path)}'")


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
    logger.info(f"Loading runs from '{file_path}'...")

    # Read the Excel file into a DataFrame.
    df = pd.read_excel(file_path)

    # Define columns that are expected to contain lists or dictionaries.
    list_like_columns = ['epw_paths', 'fwg_gcms', 'fwg_rcm_pairs', 'keyword_mapping', 'scenario_mapping',
                         'fwg_params', 'fwg_scenarios', 'fwg_timeframes', 'fwg_extra_args']

    # Iterate through the columns that might need type conversion.
    for col in df.columns:
        if col in list_like_columns:
            # Use ast.literal_eval to safely convert string representations of lists/dicts
            # back into Python objects. It's much safer than using eval().
            df[col] = df[col].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith(('[', '{')) else x
            )


    logger.info("Runs loaded and data types converted successfully.")
    return df


# Number of header lines (LOCATION to DATA PERIODS) before the data records of an EPW file.
_EPW_HEADER_LINES = 8


def sanitize_epw_minutes(epw_path: str):
    """
    Sanitizes an EPW file by replacing minute '60' with '0' in data records.
    This prevents issues with strict date-time libraries (like java.time)
    that expect MinuteOfHour to be between 0 and 59.

    The file is processed as bytes, so its encoding (e.g., Latin-1 location
    names such as 'Málaga') and line endings are preserved. In a standard EPW
    file, which starts with the LOCATION line, only the data records after
    the header (the 8 lines from LOCATION to DATA PERIODS) are modified. The
    file is only rewritten if a record uses minute 60.

    Args:
        epw_path (str): The path to the EPW file to sanitize.
    """
    temp_file = epw_path + ".tmp"
    try:
        with open(epw_path, 'rb') as f_in:
            lines = f_in.read().splitlines(keepends=True)

        # Skip the header of standard EPW files, which ends with the DATA PERIODS line.
        # Otherwise, every line is checked.
        first_data_line = 0
        if lines and lines[0].lstrip(b'\xef\xbb\xbf \t').upper().startswith(b'LOCATION'):
            first_data_line = _EPW_HEADER_LINES
            for index, line in enumerate(lines[:_EPW_HEADER_LINES]):
                if line.lstrip().upper().startswith(b'DATA PERIODS'):
                    first_data_line = index + 1
                    break

        modified = False
        for index in range(first_data_line, len(lines)):
            line = lines[index]
            # EPW data lines start with a year (e.g., 19xx, 20xx) and have many columns.
            if not line[:1].isdigit():
                continue
            parts = line.split(b',')
            # 5th column (index 4) is the minute
            if len(parts) >= 5 and parts[4].strip() == b'60':
                parts[4] = b' 0' if parts[4].startswith(b' ') else b'0'
                lines[index] = b','.join(parts)
                modified = True

        if modified:
            with open(temp_file, 'wb') as f_out:
                f_out.writelines(lines)
            os.replace(temp_file, epw_path)
            logger.debug(f"Sanitized minute 60 in: {os.path.basename(epw_path)}")

    except Exception as e:
        logger.warning(f"Failed to sanitize EPW minutes for {epw_path}: {e}")
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass


def get_fwg_parameters_info() -> Dict[str, Dict[str, Any]]:
    """Returns a comprehensive dictionary of all FWG parameters, their descriptions, defaults, and allowed values.

    This function is intended to help users understand the available options for
    the Global, Europe-specific and CORDEX regional Future Weather Generator tools
    within `pyfwg`. Parameters marked with 'requires': 'FWG Engine' are only
    available for Global v5+, Europe v3+ and the CORDEX regional distributions.
    """
    return {
        'fwg_gcms': {
            'description': 'List of Global Climate Models (GCMs) to use for the Global tool.',
            'allowed_values': sorted(list(DEFAULT_GLOBAL_GCMS)),
            'default': 'All available GCMs',
            'applies_to': 'Global'
        },
        'fwg_rcm_pairs': {
            'description': 'List of GCM-RCM model pairs to use for the Europe-specific and CORDEX regional tools.',
            'allowed_values': sorted(list(DEFAULT_EUROPE_RCMS)),
            'default': 'All available RCM pairs',
            'applies_to': 'Europe, CORDEX regional',
            'note': ('The pairs of each CORDEX region are listed in pyfwg.CORDEX_REGIONS. FWG Engine '
                     'distributions accept both "_" and "-" as separators.')
        },
        'fwg_create_ensemble': {
            'description': 'Whether to create an ensemble (average) of all selected models.',
            'allowed_values': [True, False],
            'default': True,
            'note': 'The FWG Engine requires at least two models to create an ensemble.'
        },
        'fwg_winter_sd_shift': {
            'description': 'Standard deviation shift for winter temperatures.',
            'range': [-2.0, 2.0],
            'default': 0.0
        },
        'fwg_summer_sd_shift': {
            'description': 'Standard deviation shift for summer temperatures.',
            'range': [-2.0, 2.0],
            'default': 0.0
        },
        'fwg_month_transition_hours': {
            'description': 'Number of hours used for smooth transitions between months.',
            'range': [0, 336],
            'default': 72
        },
        'fwg_interpolation_method_id': {
            'description': 'Method used for spatial interpolation of climate data.',
            'allowed_values': dict(ENGINE_INTERPOLATION_METHODS),
            'default': 0,
            'note': ('Global v3 / Europe v1 accept 0-2; Global v4 / Europe v2 accept 0-3; the FWG Engine '
                     'accepts 0-6. SCI, SGBI and STBI are structured-grid methods of the FWG Engine.')
        },
        'fwg_solar_hour_adjustment': {
            'description': 'Correction method for solar hour based on location.',
            'allowed_values': {
                0: 'None',
                1: 'By_Month',
                2: 'By_Day'
            },
            'default': 1,
            'note': 'Deprecated and ignored by the FWG Engine.'
        },
        'fwg_diffuse_irradiation_model': {
            'description': 'The mathematical model used to calculate diffuse horizontal irradiation.',
            'allowed_values': {
                0: 'Ridley_Boland_Lauret_2010',
                1: 'Engerer_2015',
                2: 'Paulescu_Blaga_2019'
            },
            'default': 1,
            'note': ('For the FWG Engine, use fwg_decomposition_method instead. A non-default value is '
                     'translated to the equivalent decomposition method.')
        },
        'fwg_output_type': {
            'description': 'The format of the generated weather files.',
            'allowed_values': ['EPW', 'SPAIN_MET', 'PORTUGAL_CSV'],
            'default': 'EPW'
        },
        'fwg_add_uhi': {
            'description': 'Whether to apply the Urban Heat Island (UHI) effect using LCZs.',
            'allowed_values': [True, False, None],
            'default': None,
            'note': ('None applies the UHI effect with tools that support it (Global v3/v4, Europe v1/v2). '
                     'The FWG Engine does not support UHI.')
        },
        'fwg_epw_original_lcz': {
            'description': 'The Local Climate Zone (LCZ) corresponding to the original EPW file location.',
            'range': [1, 17],
            'default': 14,
            'note': 'Commonly 14 for rural/airport locations.'
        },
        'fwg_target_uhi_lcz': {
            'description': 'The target Local Climate Zone (LCZ) to which the EPW should be morphed.',
            'range': [1, 17],
            'default': 1
        },
        'fwg_use_multithreading': {
            'description': 'Whether to use multiple CPU cores to speed up calculations.',
            'allowed_values': [True, False],
            'default': True
        },
        'fwg_limit_variables': {
            'description': 'Whether to force weather variables to stay within physical limits.',
            'allowed_values': [True, False],
            'default': True
        },
        'fwg_version': {
            'description': 'The version of the Future Weather Generator tool to use.',
            'allowed_values': ['3', '4', '5', '1', '2'],
            'default': 'Auto-detected from the JAR',
            'note': 'Use 3/4/5 for Global, 1/2/3 for Europe and 1 for the CORDEX regional distributions.'
        },
        'fwg_scenarios': {
            'description': 'Subset of climate scenarios to generate (e.g., [\'ssp245\', \'ssp585\'] or [\'rcp85\']).',
            'default': 'All scenarios of the distribution',
            'requires': 'FWG Engine'
        },
        'fwg_timeframes': {
            'description': 'Subset of future periods to generate.',
            'allowed_values': list(ALL_POSSIBLE_YEARS),
            'default': 'All periods of the distribution',
            'requires': 'FWG Engine'
        },
        'fwg_decomposition_method': {
            'description': 'Solar decomposition model used to split global radiation into direct and diffuse components.',
            'allowed_values': list(ENGINE_DECOMPOSITION_METHODS),
            'default': 'MULTIMODEL_CONSTRAINED_ENSEMBLE (tool default)',
            'requires': 'FWG Engine'
        },
        'fwg_illuminance_method': {
            'description': 'Model used to regenerate the illuminance and zenith luminance fields.',
            'allowed_values': list(ENGINE_ILLUMINANCE_METHODS),
            'default': 'PEREZ_1990 (tool default)',
            'requires': 'FWG Engine'
        },
        'fwg_infrared_method': {
            'description': 'Model used for horizontal infrared radiation from the sky.',
            'allowed_values': list(ENGINE_INFRARED_METHODS),
            'default': 'FWG_CURRENT (tool default)',
            'requires': 'FWG Engine',
            'note': 'Available from Global v5.2, Europe v3.2 and CORDEX regional v1.2 (FWG Engine v1.1).'
        },
        'fwg_morphing_method': {
            'description': 'Climate morphing methodology.',
            'allowed_values': list(ENGINE_MORPHING_METHODS),
            'default': 'CLASSIC_MONTHLY (tool default)',
            'requires': 'FWG Engine',
            'note': 'DISTRIBUTION_AWARE is experimental.'
        },
        'fwg_uncertainty_variant': {
            'description': 'Climate-signal uncertainty case to generate (deterministic boundary cases).',
            'allowed_values': list(ENGINE_UNCERTAINTY_VARIANTS),
            'default': 'CENTRAL (tool default)',
            'requires': 'FWG Engine',
            'note': 'Non-central variants cannot be combined with non-zero winter/summer SD shifts.'
        },
        'fwg_uncertainty_sigma': {
            'description': 'Standard-deviation multiplier used by the uncertainty variant.',
            'range': [0.0, None],
            'default': '1.0 (tool default)',
            'requires': 'FWG Engine'
        },
        'fwg_output_profile': {
            'description': 'Set of reports, manifests and diagnostics written by the tool alongside the weather files.',
            'allowed_values': list(ENGINE_OUTPUT_PROFILES),
            'default': 'STANDARD (tool default)',
            'requires': 'FWG Engine',
            'note': 'These auxiliary files remain in the temporary folder (see delete_temp_files).'
        },
        'fwg_model_unzipped_folder': {
            'description': ('Folder where the tool caches the unzipped climate-model data. Reusing it '
                            'across runs avoids extracting the data again.'),
            'default': 'Temporary output folder of each run (tool default)',
            'requires': 'FWG Engine'
        },
        'fwg_extra_args': {
            'description': ('Additional command-line options passed to the tool as -key=value (e.g., '
                            '{\'threads\': 4, \'save_present_day\': True}).'),
            'default': None,
            'applies_to': 'Global v4+, Europe v2+, CORDEX regional',
            'note': 'Options that pyfwg already sets (e.g., epw, output_folder or models) cannot be overridden.'
        },
    }
