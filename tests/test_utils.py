
# tests/test_utils.py
"""
Exhaustive unit tests for the utility functions in pyfwg.utils.
These tests use 'mocking' (simulating dependencies) to test functions
without needing real file systems or running the actual Java tool.
"""

import os
import shutil
import logging
import pytest
import numpy as np
import pandas as pd
import subprocess
from unittest.mock import MagicMock, patch
from pyfwg.utils import (
    detect_fwg_version,
    _robust_rmtree,
    copy_tutorials,
    uhi_morph,
    check_lcz_availability,
    get_available_lczs,
    export_template_to_excel,
    load_runs_from_excel,
    sanitize_epw_minutes,
    get_fwg_parameters_info
)

def test_detect_fwg_version(fwg_jars):
    """
    Test the automatic detection of the Future Weather Generator version from a file name.
    It uses the real paths provided by the user in conftest.py.
    """
    # Test detection for all 4 major versions/variants
    assert detect_fwg_version(fwg_jars["GLOBAL_V4"]) == "4"
    assert detect_fwg_version(fwg_jars["GLOBAL_V3"]) == "3"
    assert detect_fwg_version(fwg_jars["EUROPE_V2"]) == "2"
    assert detect_fwg_version(fwg_jars["EUROPE_V1"]) == "1"
    # FWG Engine distributions use a new naming scheme
    assert detect_fwg_version(fwg_jars["GLOBAL_V5"]) == "5"
    assert detect_fwg_version(fwg_jars["EUROPE_V3"]) == "3"
    assert detect_fwg_version(fwg_jars["CORDEX_NAM"]) == "1"
    
    # Negative test: ensure it raises an error if no version pattern is found
    with pytest.raises(ValueError, match="Could not auto-detect FWG version"):
        detect_fwg_version("NoVersionHere.jar")

def test_robust_rmtree(tmp_path):
    """
    Test the deletion of directories.
    Uses 'tmp_path' which is an automatic temporary folder provided by pytest.
    """
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("dummy data")
    
    # Run the utility to remove the directory and its contents
    _robust_rmtree(str(test_dir))
    assert not test_dir.exists(), "The directory should have been deleted"

@patch("pyfwg.utils.resources.files")
@patch("pyfwg.utils.resources.as_file")
@patch("os.makedirs")
@patch("shutil.copy2")
def test_copy_tutorials(mock_copy2, mock_makedirs, mock_as_file, mock_files):
    """
    Test the copying of tutorial notebook files from the package to a user-defined folder.
    We mock the 'importlib.resources' internal calls to simulate finding files inside the package.
    """
    # Simulate a package structure with one file named 'test_item.ipynb'
    mock_item = MagicMock()
    mock_item.name = "test_item.ipynb"
    mock_files.return_value.iterdir.return_value = [mock_item]
    
    # Simulate the source path where the package file resides
    mock_as_file.return_value.__enter__.return_value = "/mock/source/test_item.ipynb"
    
    # We also mock os.path.isdir to simulate that the destination folder doesn't exist yet
    with patch("os.path.isdir", return_value=False):
        copy_tutorials("/mock/dest")
    
    # Verify the utility creates the destination folder and copies the file
    mock_makedirs.assert_called_once_with("/mock/dest", exist_ok=True)
    mock_copy2.assert_called_once()

def test_uhi_morph_v4_style():
    """
    Test construction of the Java command for UHI morphing using the NEW CLI style (v4).
    The new style uses flags like -jar, -epw=, -uhi=, etc.
    """
    with patch("subprocess.run") as mock_run:
        uhi_morph(
            fwg_epw_path="test.epw",
            fwg_jar_path="FWG_v4.jar",
            fwg_output_dir="out",
            fwg_original_lcz=14,
            fwg_target_lcz=1,
            fwg_version=4
        )
        # Inspect the command passed to subprocess.run
        args, _ = mock_run.call_args
        command = args[0]
        assert "java" in command
        assert "-jar" in command  # Flag for directly running the JAR
        assert "-u" in command    # Custom flag for UHI-only mode in pyfwg
        assert "-uhi=true:14:1" in command

def test_uhi_morph_v3_style():
    """
    Test construction of the Java command for UHI morphing using the LEGACY style (v3).
    The legacy style uses a classpath (-cp) and positional arguments.
    """
    with patch("subprocess.run") as mock_run:
        uhi_morph(
            fwg_epw_path="test.epw",
            fwg_jar_path="FWG_v3.jar",
            fwg_output_dir="out",
            fwg_original_lcz=14,
            fwg_target_lcz=1,
            fwg_version=3
        )
        args, _ = mock_run.call_args
        command = args[0]
        assert "java" in command
        assert "-cp" in command  # Flag for defining the search path of Java classes
        assert "futureweathergenerator.UHI_Morph" in command # The specific Java main class
        assert "14:1" in command # Positional parameters for LCZs

def test_check_lcz_availability_success():
    """
    Test the pre-flight check for LCZ availability.
    If the tool runs without errors, the availability check returns True.
    """
    with patch("pyfwg.utils.uhi_morph") as mock_uhi:
        mock_uhi.return_value = None # Simulate success (no exception)
        # We need to mock filesystem checks because the function validates the EPW file existence
        with patch("shutil.copy2"):
            with patch("pyfwg.utils.sanitize_epw_minutes"):
                with patch("os.path.exists", return_value=True):
                    result = check_lcz_availability(
                        epw_path="test.epw",
                        original_lcz=14,
                        target_lcz=1,
                        fwg_jar_path="FWG_v4.jar"
                    )
        assert result is True

def test_check_lcz_availability_failure():
    """
    Test the LCZ availability check when the tool returns an error.
    The function should parse the error message to extract the list of LCZs that ARE available.
    """
    # A sample error message from the Java tool when an invalid LCZ is requested
    msg = "The LCZs available are:\nLCZ 1: Natural\nLCZ 2: Urban"
    mock_error = subprocess.CalledProcessError(1, "cmd", output=msg)
    
    with patch("pyfwg.utils.uhi_morph", side_effect=mock_error):
        with patch("shutil.copy2"):
            with patch("pyfwg.utils.sanitize_epw_minutes"):
                with patch("os.path.exists", return_value=True):
                    result = check_lcz_availability(
                        epw_path="test.epw",
                        original_lcz=14,
                        target_lcz=1,
                        fwg_jar_path="FWG_v4.jar"
                    )
        
        # When it fails, it returns a dictionary with details instead of 'True'
        assert isinstance(result, dict)
        assert "invalid_messages" in result
        assert "available" in result
        # Check if it correctly identified that LCZ 14 was the problem
        assert any("14" in m for m in result["invalid_messages"])

def test_get_available_lczs():
    """
    Test the batch utility that checks LCZ availability for multiple files.
    """
    with patch("pyfwg.utils.check_lcz_availability") as mock_check:
        # Mocking the result of one file check
        mock_check.return_value = {
            "available": ["LCZ 1: Natural", "LCZ 2: Urban"],
            "invalid_messages": []
        }
        results = get_available_lczs(
            epw_paths=["test1.epw", "test2.epw"],
            fwg_jar_path="FWG_v4.jar"
        )
        assert "test1.epw" in results
        # Should extract just the numbers from the text list
        assert results["test1.epw"] == [1, 2]

def test_export_template_to_excel(tmp_path):
    """
    Test exporting a parametric study template to Excel.
    """
    mock_iterator = MagicMock()
    # Simulate the iterator providing a blank DataFrame with two columns
    mock_iterator.get_template_dataframe.return_value = pd.DataFrame(columns=["A", "B"])
    mock_iterator.workflow_class.__name__ = "TestWorkflow"
    
    file_path = tmp_path / "template.xlsx"
    export_template_to_excel(mock_iterator, str(file_path))
    
    assert file_path.exists(), "Excel file should be created"
    # Load it back to verify content
    df = pd.read_excel(file_path)
    assert list(df.columns) == ["A", "B"]

def test_load_runs_from_excel(tmp_path):
    """
    Test loading parametric study definitions from an Excel file into a DataFrame.
    """
    file_path = tmp_path / "runs.xlsx"
    # Create an Excel file where one column contains a string representation of a list
    df_data = pd.DataFrame({
        "epw_paths": ["['path1', 'path2']"],
        "other": [123]
    })
    df_data.to_excel(file_path, index=False)
    
    loaded_df = load_runs_from_excel(str(file_path))
    # The 'load_runs_from_excel' function should convert the string "['path1', ...]" back to a Python list
    assert isinstance(loaded_df["epw_paths"].iloc[0], list)
    assert loaded_df["epw_paths"].iloc[0] == ["path1", "path2"]

def test_sanitize_epw_minutes(tmp_path):
    """
    Test the fix for the 'Minute 60' bug in some Java date libraries.
    FWG fails if it sees minute 60; we replace it with minute 0.
    """
    epw_file = tmp_path / "test.epw"
    # Sample EPW content with one line having minute 60
    content = "2023,1,1,1,60,data\n2023,1,1,2,30,data"
    epw_file.write_text(content)
    
    sanitize_epw_minutes(str(epw_file))
    
    new_content = epw_file.read_text()
    assert "1,0,data" in new_content, "Minute 60 should be replaced with 0"
    assert "2,30,data" in new_content, "Other minutes should remain unchanged"

def test_get_fwg_parameters_info():
    """
    Test the documentation utility that returns a dictionary describing all FWG parameters.
    """
    info = get_fwg_parameters_info()
    assert isinstance(info, dict)
    # Check for presence of essential parameters
    assert "fwg_gcms" in info
    assert "fwg_rcm_pairs" in info
    # Verify some default metadata
    assert info["fwg_create_ensemble"]["default"] is True

def test_sanitize_epw_minutes_preserves_the_header(tmp_path):
    """
    The header of the EPW file is kept byte for byte (e.g., Latin-1 location
    names) and the line endings are preserved: only the minute of the data
    records after the 8 header lines changes.
    """
    header = [
        "LOCATION,M\xe1laga,AND,ESP,SWEC,084820,36.67,-4.48,1.0,7.0",
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,Estaci\xf3n de M\xe1laga; also S\xe3o Paulo and Z\xfcrich",
        "COMMENTS 2,Minute 60 is used in all records",
        "DATA PERIODS,1,1,Data,Sunday, 1/ 1,12/31",
    ]
    records = ["1985,1,1,1,60,A7A7,13.0", "1985,1,1,2, 60,A7A7,12.5", "1985,1,1,3,30,A7A7,12.0"]
    epw = tmp_path / "malaga.epw"
    epw.write_bytes("\r\n".join(header + records).encode("latin-1") + b"\r\n")

    sanitize_epw_minutes(str(epw))

    lines = epw.read_bytes().split(b"\r\n")
    assert lines[:8] == [line.encode("latin-1") for line in header]
    assert lines[8:] == [b"1985,1,1,1,0,A7A7,13.0", b"1985,1,1,2, 0,A7A7,12.5", b"1985,1,1,3,30,A7A7,12.0", b""]

@pytest.mark.parametrize("error", [
    subprocess.CalledProcessError(1, "java", output="tool output", stderr="tool error"),
    FileNotFoundError("java"),
    subprocess.TimeoutExpired(cmd="java", timeout=300),
])
def test_uhi_morph_does_not_raise_when_requested(tmp_path, caplog, error):
    """With raise_on_error=False, a failure of the tool is logged and False is returned."""
    with patch("subprocess.run", side_effect=error):
        with caplog.at_level(logging.ERROR, logger="pyfwg"):
            result = uhi_morph(fwg_epw_path="test.epw", fwg_jar_path="FWG_v4.jar", fwg_output_dir=str(tmp_path / "uhi"),
                               fwg_original_lcz=14, fwg_target_lcz=1, fwg_version=4, raise_on_error=False)
    assert result is False
    assert any(record.levelno == logging.ERROR for record in caplog.records)

def test_uhi_morph_raises_by_default(tmp_path):
    """By default, errors are raised; a successful run returns True."""
    kwargs = dict(fwg_epw_path="test.epw", fwg_jar_path="FWG_v4.jar", fwg_output_dir=str(tmp_path / "uhi"),
                  fwg_original_lcz=14, fwg_target_lcz=1, fwg_version=4)
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "java")):
        with pytest.raises(subprocess.CalledProcessError):
            uhi_morph(**kwargs)
    with patch("subprocess.run"):
        assert uhi_morph(**kwargs) is True

def test_uhi_morph_normalizes_arguments(tmp_path):
    """LCZs given as floats (e.g., read from Excel) reach the tool as integers, and flags are strict."""
    kwargs = dict(fwg_epw_path="test.epw", fwg_jar_path="FWG.jar", fwg_output_dir=str(tmp_path / "uhi"))
    with patch("subprocess.run") as mock_run:
        uhi_morph(fwg_original_lcz=14.0, fwg_target_lcz=np.float64(2.0), fwg_version=4, **kwargs)
        assert "-uhi=true:14:2" in mock_run.call_args[0][0]

        uhi_morph(fwg_original_lcz=14.0, fwg_target_lcz=2.0, fwg_limit_variables="False", fwg_version=3, **kwargs)
        assert mock_run.call_args[0][0][-2:] == ["false", "14:2"]

        with pytest.raises(ValueError, match="must be integers"):
            uhi_morph(fwg_original_lcz=14.5, fwg_target_lcz=2, fwg_version=4, **kwargs)
        assert uhi_morph(fwg_original_lcz=14, fwg_target_lcz=2, fwg_limit_variables="maybe", fwg_version=3,
                         raise_on_error=False, **kwargs) is False
        assert mock_run.call_count == 2
