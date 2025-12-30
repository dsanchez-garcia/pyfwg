
# tests/test_api.py
"""
Unit tests for the high-level API functions in pyfwg.api.
These functions (morph_epw_global, morph_epw_europe) are the easiest way 
for users to run a full morphing process on one or more EPW files.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from pyfwg.api import morph_epw_global, morph_epw_europe

@patch("pyfwg.api.MorphingWorkflowGlobal")
@patch("pyfwg.api._robust_rmtree")
@patch("os.path.exists", return_value=True)
@patch("os.makedirs")
def test_morph_epw_global(mock_makedirs, mock_exists, mock_rmtree, mock_workflow_class, tmp_path):
    """
    Test the successful execution of morph_epw_global.
    We mock the underlying 'MorphingWorkflowGlobal' engine to isolate the API function logic.
    """
    # Configure the mock workflow instance
    mock_workflow = mock_workflow_class.return_value
    mock_workflow.is_config_valid = True
    mock_workflow.epws_to_be_morphed = ["test.epw"]
    mock_workflow.inputs = {
        'temp_base_dir': str(tmp_path / 'temp'),
        'fwg_params': {'add_uhi': False},
        'fwg_jar_path': 'FWG.jar',
        'delete_temp_files': True
    }
    # Simulate a successful Java tool execution
    mock_workflow._execute_single_morph.return_value = True
    
    # Mock os.listdir to simulate the generation of one morphed file
    with patch("os.listdir", return_value=["test_morphed.epw"]):
        # Mock shutil.move to avoid real file operations
        with patch("shutil.move"):
            results = morph_epw_global(
                epw_paths="test.epw",
                fwg_jar_path="FWG.jar",
                output_dir=str(tmp_path / "out")
            )
            
    # Verify the results and that internal methods were called
    assert len(results) == 1
    mock_workflow.configure_and_preview.assert_called_once()
    mock_workflow._execute_single_morph.assert_called_once()

@patch("pyfwg.api.MorphingWorkflowEurope")
@patch("pyfwg.api._robust_rmtree")
@patch("os.path.exists", return_value=True)
@patch("os.makedirs")
def test_morph_epw_europe(mock_makedirs, mock_exists, mock_rmtree, mock_workflow_class, tmp_path):
    """
    Test the successful execution of morph_epw_europe.
    Identical logic to the global test but targets the European engine.
    """
    mock_workflow = mock_workflow_class.return_value
    mock_workflow.is_config_valid = True
    mock_workflow.epws_to_be_morphed = ["test.epw"]
    mock_workflow.inputs = {
        'temp_base_dir': str(tmp_path / 'temp'),
        'fwg_params': {'add_uhi': False},
        'fwg_jar_path': 'FWG_Europe.jar',
        'delete_temp_files': True
    }
    mock_workflow._execute_single_morph.return_value = True
    
    with patch("os.listdir", return_value=["test_morphed.epw"]):
        with patch("shutil.move"):
            results = morph_epw_europe(
                epw_paths="test.epw",
                fwg_jar_path="FWG_Europe.jar",
                output_dir=str(tmp_path / "out")
            )
            
    assert len(results) == 1
    mock_workflow.configure_and_preview.assert_called_once()
    mock_workflow._execute_single_morph.assert_called_once()

def test_morph_epw_global_invalid_config():
    """
    Test behavior when parameters provided to the API are invalid.
    The function should raise a ValueError and NOT attempt execution.
    """
    with patch("pyfwg.api.MorphingWorkflowGlobal") as mock_workflow_class:
        mock_workflow = mock_workflow_class.return_value
        # Mark the configuration as invalid (e.g., wrong shift values, etc.)
        mock_workflow.is_config_valid = False
        
        with pytest.raises(ValueError, match="FWG parameter validation failed"):
            morph_epw_global(epw_paths="test.epw", fwg_jar_path="FWG.jar")
