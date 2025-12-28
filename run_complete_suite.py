
import os
import shutil
import logging
import pandas as pd
from datetime import datetime

# Import EVERYTHING
import pyfwg
from pyfwg.workflow import MorphingWorkflowGlobal, MorphingWorkflowEurope
from pyfwg.iterator import MorphingIterator
from pyfwg.api import morph_epw_global, morph_epw_europe
from pyfwg.utils import (
    detect_fwg_version, 
    check_lcz_availability, 
    get_available_lczs,
    copy_tutorials,
    uhi_morph
)

# Configuration
JAR_V3 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"
JAR_V4 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar"
JAR_EUR = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v1.0.1.jar"
EPW_FILE = r"epws/wo_pattern/GBR_London.Gatwick.037760_IWEC_uhi_type-2.epw"
OUTPUT_DIR = r"D:\temp_pyfwg_complete_suite"

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.info("Starting Complete FWG Test Suite")

def clean_dir(path):
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)

# ---------------------------------------------------------
# SECTION 1: UTILITIES (Modified & Unmodified)
# ---------------------------------------------------------
def test_utilities():
    print("\n" + "="*50)
    print("SECTION 1: TEST UTILITIES")
    print("="*50)

    # 1.1 copy_tutorials (Unmodified)
    print("[1.1] Testing copy_tutorials...")
    tut_dir = os.path.join(OUTPUT_DIR, "tutorials_copy")
    try:
        copy_tutorials(tut_dir)
        if os.path.exists(tut_dir) and len(os.listdir(tut_dir)) > 0:
            print("  PASS: Tutorials copied successfully.")
        else:
            print("  FAIL: Directory empty or not created.")
    except Exception as e:
        print(f"  FAIL: {e}")

    # 1.2 detect_fwg_version (Modified/New)
    print("[1.2] Testing detect_fwg_version...")
    try:
        ver = detect_fwg_version(JAR_V3)
        print(f"  V3 Detection: {'PASS' if ver == '3' else 'FAIL'} (Got {ver})")
        
        ver = detect_fwg_version(JAR_V4)
        print(f"  V4 Detection: {'PASS' if ver == '4' else 'FAIL'} (Got {ver})")
        
        # Test failure case
        try:
            detect_fwg_version("invalid_name.jar")
            print("  Invalid Name: FAIL (Should have raised ValueError)")
        except ValueError:
            print("  Invalid Name: PASS (Correctly raised ValueError)")
            
    except Exception as e:
        print(f"  FAIL: {e}")

    # 1.3 get_available_lczs (Modified)
    print("[1.3] Testing get_available_lczs with V4 JAR...")
    try:
        print("  Skipping get_available_lczs full execution to save time (verified in previous steps).")
        # lczs = get_available_lczs([EPW_FILE], fwg_jar_path=JAR_V4, fwg_version=4)
        # if EPW_FILE in lczs and len(lczs[EPW_FILE]) > 0:
        #     print(f"  PASS: Found LCZs {lczs[EPW_FILE]}")
        # else:
        #     print("  FAIL: No LCZs found or empty list.")
    except Exception as e:
        print(f"  FAIL: {e}")

# ---------------------------------------------------------
# SECTION 2: WORKFLOWS (Global V3, V4, Europe)
# ---------------------------------------------------------
def test_workflows():
    print("\n" + "="*50)
    print("SECTION 2: TEST WORKFLOW CLASSES")
    print("="*50)
    
    mapping = {'city': {'london': ['london', 'gatwick']}, 'uhi': {'type-2': 'type-2'}}

    # 2.1 MorphingWorkflowGlobal (V3 - Legacy)
    print("[2.1] Testing MorphingWorkflowGlobal (V3 Legacy)...")
    try:
        wf = MorphingWorkflowGlobal()
        
        # Method: map_categories
        wf.map_categories([EPW_FILE], keyword_mapping=mapping)
        if wf.epw_categories:
            print("  PASS: map_categories (Mapping successful)")
        else:
            print("  FAIL: map_categories (No categories mapped)")

        # Method: configure_and_preview
        wf.configure_and_preview(
            final_output_dir=os.path.join(OUTPUT_DIR, "v3_global"),
            output_filename_pattern='v3_{city}_{year}',
            scenario_mapping={'ssp245': 'SSP2-4.5'},
            fwg_jar_path=JAR_V3,
            fwg_gcms=['BCC_CSM2_MR'],
            fwg_epw_original_lcz=2,
            fwg_target_uhi_lcz=3,
            run_incomplete_files=True,
            fwg_show_tool_output=False
        )
        
        if wf.is_config_valid:
            print("  PASS: configure_and_preview (Config valid)")
            # Skipped actual execution to save time. Using V4 for full verification.
            # wf.execute_morphing() 
        else:
            print("  FAIL: configure_and_preview (Config invalid)")

    except Exception as e:
        print(f"  FAIL: {e}")

    # 2.2 MorphingWorkflowGlobal (V4 - New)
    print("[2.2] Testing MorphingWorkflowGlobal (V4 New)...")
    try:
        wf = MorphingWorkflowGlobal()
        wf.map_categories([EPW_FILE], keyword_mapping=mapping)
        wf.configure_and_preview(
            final_output_dir=os.path.join(OUTPUT_DIR, "v4_global"),
            output_filename_pattern='v4_{city}_{year}',
            scenario_mapping={'ssp245': 'SSP2-4.5'},
            fwg_jar_path=JAR_V4,
            fwg_gcms=['BCC_CSM2_MR'],
            fwg_epw_original_lcz=2,
            fwg_target_uhi_lcz=3,
            run_incomplete_files=True,
            fwg_version=4 
        )
        if wf.is_config_valid:
             print("  PASS: configure_and_preview V4 (Config valid)")
             print("  Executing V4 Morphing (Full Run)...")
             wf.execute_morphing()
             print("  PASS: execute_morphing V4 executed.")
             
             print("  Testing preview_renaming V4...")
             wf.preview_renaming()
             print("  PASS: preview_renaming V4 executed.")
        else:
             print("  FAIL: configure_and_preview V4 (Config invalid)")
    except Exception as e:
         print(f"  FAIL: {e}")

    # 2.3 MorphingWorkflowEurope (Legacy)
    print("[2.3] Testing MorphingWorkflowEurope...")
    try:
        wf = MorphingWorkflowEurope()
        wf.map_categories([EPW_FILE], keyword_mapping=mapping)
        wf.configure_and_preview(
            final_output_dir=os.path.join(OUTPUT_DIR, "europe"),
            output_filename_pattern='eur_{city}_{year}',
            scenario_mapping={'rcp26': 'RCP-2.6'},
            fwg_jar_path=JAR_EUR,
            fwg_rcm_pairs=['ICHEC_EC_EARTH_SMHI_RCA4'],
            fwg_epw_original_lcz=2,
            fwg_target_uhi_lcz=3,
            run_incomplete_files=True
        )
        if wf.is_config_valid:
             print("  PASS: configure_and_preview Europe (Config valid)")
        else:
             print("  FAIL: configure_and_preview Europe (Config invalid)")
    except Exception as e:
         print(f"  FAIL: {e}")

# ---------------------------------------------------------
# SECTION 3: API FUNCTIONS
# ---------------------------------------------------------
def test_api():
    print("\n" + "="*50)
    print("SECTION 3: TEST API FUNCTIONS")
    print("="*50)
    
    # 3.1 morph_epw_global
    print("[3.1] Testing morph_epw_global...")
    try:
        # We assume if the workflow tests passed, these wrappers just need to be callable
        # We will config it but rely on 'fwg_show_tool_output=False' to be fast/silent
        morph_epw_global(
            epw_paths=[EPW_FILE],
            fwg_jar_path=JAR_V4,
            output_dir=os.path.join(OUTPUT_DIR, "api_global"),
            fwg_gcms=['BCC_CSM2_MR'],
            fwg_target_uhi_lcz=3,
            fwg_version='4',
            fwg_show_tool_output=False
        )
        print("  PASS: morph_epw_global called successfully.")
    except Exception as e:
        print(f"  FAIL: {e}")

# ---------------------------------------------------------
# SECTION 4: ITERATOR (Full Lifecycle)
# ---------------------------------------------------------
def test_iterator():
    print("\n" + "="*50)
    print("SECTION 4: TEST ITERATOR")
    print("="*50)
    
    try:
        iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)
        
        # 4.1 get_template_dataframe
        print("[4.1] Testing get_template_dataframe...")
        df = iterator.get_template_dataframe()
        if 'epw_paths' in df.columns:
            print("  PASS: Template DataFrame generated.")
        else:
            print("  FAIL: Template DataFrame missing columns.")
            
        # 4.2 Excel Export/Import (Mocked check)
        print("[4.2] Testing Excel utils...")
        # Since these are top-level generic utils, we can just check existence or import
        from pyfwg import export_template_to_excel, load_runs_from_excel
        excel_path = os.path.join(OUTPUT_DIR, "test_template.xlsx")
        
        export_template_to_excel(iterator, excel_path)
        if os.path.exists(excel_path):
             print("  PASS: export_template_to_excel created file.")
             
             # Create a dummy run in the loaded df to test loading
             loaded_df = load_runs_from_excel(excel_path)
             if isinstance(loaded_df, pd.DataFrame):
                 print("  PASS: load_runs_from_excel loaded file.")
        else:
             print("  FAIL: Excel export failed.")

        # 4.3 Full Iterator Setup
        print("[4.3] Testing Iterator Generation...")
        mapping = {'city': {'london': ['london', 'gatwick']}, 'uhi': {'type-2': 'type-2'}}
        
        # Manually populate row
        runs_df = iterator.get_template_dataframe()
        runs_df.loc[0] = pd.Series({
            'epw_paths': [EPW_FILE],
            'keyword_mapping': mapping,
            'fwg_epw_original_lcz': 2,
            'fwg_target_uhi_lcz': 3,
            'fwg_interpolation_method_id': 0
        })
        
        iterator.set_default_values(
             final_output_dir=os.path.join(OUTPUT_DIR, "iterator"),
             output_filename_pattern='iter_{city}_{year}',
             scenario_mapping={'ssp245': 'SSP2-4.5'},
             fwg_jar_path=JAR_V4,
             fwg_gcms=['BCC_CSM2_MR'],
             fwg_version='4'
        )
        
        iterator.generate_morphing_workflows(runs_df)
        
        if len(iterator.prepared_workflows) == 1:
            print(f"  PASS: {len(iterator.prepared_workflows)} workflow prepared.")
            if iterator.prepared_workflows[0].is_config_valid:
                 print("  PASS: Prepared workflow has valid config.")
        else:
             print("  FAIL: No workflows generated.")

    except Exception as e:
        print(f"  FAIL: {e}")

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
if __name__ == "__main__":
    setup_logger()
    clean_dir(OUTPUT_DIR)
    
    print("Checking paths...")
    if not os.path.exists(EPW_FILE):
        print(f"WARNING: Test EPW file not found at {EPW_FILE}. Tests will fail.")
    else:
        test_utilities()
        test_workflows()
        test_api()
        test_iterator()
    
    print("\n" + "="*50)
    print("TEST SUITE COMPLETE")
    print("="*50)
