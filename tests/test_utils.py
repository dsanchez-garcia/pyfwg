
# tests/test_utils.py
"""
Exhaustive unit tests for the utility functions in pyfwg.utils.
These tests use 'mocking' (simulating dependencies) to test functions
without needing real file systems or running the actual Java tool.
"""

import os
import shutil
import pytest
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
