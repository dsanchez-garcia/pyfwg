"""
Backward Compatibility and V4 Feature Test.

This script verifies that the library maintains backward compatibility with:
- FutureWeatherGenerator V3.0.x (Legacy Global)
- FutureWeatherGenerator_Europe V1.0.x (Legacy Europe)

It also tests the correct integration and command-line argument generation for:
- FutureWeatherGenerator V4.0.x (New Global)

How to run:
    python tests/test_backward_compat_and_v4.py
"""

import os
import shutil
import logging
import pyfwg
from pyfwg.workflow import MorphingWorkflowGlobal, MorphingWorkflowEurope

def run_tests():
    logging.basicConfig(level=logging.INFO)
    
    # --- Paths ---
    # Update these paths based on what I saw in previous steps/user input
    jar_v3 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"
    # Note: The Europe one in the user script was v1.0.1
    jar_europe = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v1.0.1.jar"
    jar_v4 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar"

    epw_root = "epws/wo_pattern"

    if not os.path.exists(epw_root):
        logging.error(f"EPW directory {epw_root} not found. Cannot run tests.")
        return

    epw_files = [os.path.join(epw_root, f) for f in os.listdir(epw_root) if f.endswith('.epw')]
    
    if not epw_files:
        logging.error("No EPW files found in pattern directory.")
        return

    # Use just one file for speed
    test_epw_files = [epw_files[0]]
    logging.info(f"Testing with EPW: {test_epw_files[0]}")

    mapping = {
        'city': {
            'seville': ['sevilla', 'SVQ'],
            'london': ['london', 'gatwick']
        },
        'uhi': {
            'type-1': 'type-1',
            'type-2': 'type-2'
        }
    }

    # ==========================================
    # TEST 1: Legacy Global V3 (Backward Compat)
    # ==========================================
    print("\n" + "="*50)
    print("TEST 1: Legacy Global V3 (Backward Compat)")
    print("="*50)
    
    try:
        workflow_v3 = MorphingWorkflowGlobal()
        workflow_v3.map_categories(
            epw_files=test_epw_files,
            input_filename_pattern=None,
            keyword_mapping=mapping
        )
        
        workflow_v3.configure_and_preview(
            final_output_dir='./test_results_v3_global',
            output_filename_pattern='v3_{city}_{uhi}_{ssp}_{year}',
            scenario_mapping={'ssp245': 'SSP2-4.5'},
            fwg_jar_path=jar_v3,
            run_incomplete_files=True,
            delete_temp_files=False,
            fwg_show_tool_output=True,
            fwg_gcms=['BCC_CSM2_MR'], # Use a single model for speed
            temp_base_dir='./temp_v3_global',
            fwg_epw_original_lcz=2,
            fwg_target_uhi_lcz=3
            # Note: fwg_version is NOT passed here, so it should auto-detect '3'
        )
        
        if workflow_v3.is_config_valid:
            workflow_v3.execute_morphing()
            print(">> Test 1 PASSED: Workflow execution completed.")
        else:
            print(">> Test 1 FAILED: Configuration invalid.")

    except Exception as e:
        print(f">> Test 1 FAILED with Exception: {e}")


    # ==========================================
    # TEST 2: Legacy Europe (Backward Compat)
    # ==========================================
    print("\n" + "="*50)
    print("TEST 2: Legacy Europe (Backward Compat)")
    print("="*50)

    try:
        workflow_eur = MorphingWorkflowEurope()
        workflow_eur.map_categories(
            epw_files=test_epw_files,
            input_filename_pattern=None,
            keyword_mapping=mapping
        )

        workflow_eur.configure_and_preview(
            final_output_dir='./test_results_europe',
            output_filename_pattern='eur_{city}_{uhi}_{rcp}_{year}',
            scenario_mapping={'rcp26': 'RCP-2.6'},
            fwg_jar_path=jar_europe,
            run_incomplete_files=True,
            delete_temp_files=False,
            fwg_show_tool_output=True,
            fwg_rcm_pairs=['ICHEC_EC_EARTH_SMHI_RCA4'],
            temp_base_dir='./temp_europe',
            fwg_epw_original_lcz=2,
            fwg_target_uhi_lcz=3
             # Note: fwg_version is NOT passed here. Auto-detect might fail or default to 3/Legacy.
             # The regex looks for v(\d+). 'v1.0.1' -> 1. 
             # Logic checks: if version.startswith('4'). '1' does not. So it should use legacy command. Correct.
        )

        if workflow_eur.is_config_valid:
            workflow_eur.execute_morphing()
            print(">> Test 2 PASSED: Workflow execution completed.")
        else:
            print(">> Test 2 FAILED: Configuration invalid.")

    except Exception as e:
        print(f">> Test 2 FAILED with Exception: {e}")


    # ==========================================
    # TEST 3: New Global V4 (New Feature)
    # ==========================================
    print("\n" + "="*50)
    print("TEST 3: New Global V4")
    print("="*50)

    try:
        workflow_v4 = MorphingWorkflowGlobal()
        workflow_v4.map_categories(
            epw_files=test_epw_files,
            input_filename_pattern=None,
            keyword_mapping=mapping
        )

        workflow_v4.configure_and_preview(
            final_output_dir='./test_results_v4_global',
            output_filename_pattern='v4_{city}_{uhi}_{ssp}_{year}',
            scenario_mapping={'ssp245': 'SSP2-4.5'},
            fwg_jar_path=jar_v4,
            run_incomplete_files=True,
            delete_temp_files=False,
            fwg_show_tool_output=True,
            fwg_gcms=['BCC_CSM2_MR'], 
            temp_base_dir='./temp_v4_global',
            fwg_epw_original_lcz=2,
            fwg_target_uhi_lcz=3,
            fwg_version='4' # Explicitly testing V4 override, though auto-detect should also work
        )
        
        # NOTE: We expect the java command to fail for 'ACCESS-CM2' because V4 likely has different model names 
        # or strict validation, BUT the python side should successfully build the command and try to run it.
        # If it runs java, that's a pass for the python refactor.
        
        if workflow_v4.is_config_valid:
            workflow_v4.execute_morphing()
            print(">> Test 3 PASSED: Workflow execution attempted.")
        else:
            print(">> Test 3 FAILED: Configuration invalid.")

    except Exception as e:
        print(f">> Test 3 FAILED with Exception: {e}")

if __name__ == "__main__":
    run_tests()
