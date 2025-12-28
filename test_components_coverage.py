
import os
import logging
from pyfwg.iterator import MorphingIterator
from pyfwg.workflow import MorphingWorkflowGlobal
from pyfwg.utils import get_available_lczs
import pandas as pd

def test_remaining_components():
    logging.basicConfig(level=logging.INFO)
    print("--- Starting Coverage Test for Iterator and Utils ---")

    # Paths
    jar_v3 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"
    jar_v4 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar"
    epw_path = "epws/wo_pattern/GBR_London.Gatwick.037760_IWEC_uhi_type-2.epw"
    
    if not os.path.exists(epw_path):
        print("EPW not found, skipping.")
        return

    # --- Test 1: get_available_lczs (Utils) ---
    print("\n[Test 1] get_available_lczs (expected to list LCZs)")
    try:
        # Test with V3
        print("  Testing with V3 JAR...")
        lczs_v3 = get_available_lczs(epw_paths=[epw_path], fwg_jar_path=jar_v3)
        print(f"  V3 Result: Found {len(lczs_v3.get(epw_path, []))} LCZs.")
        
        # Test with V4
        print("  Testing with V4 JAR...")
        lczs_v4 = get_available_lczs(epw_paths=[epw_path], fwg_jar_path=jar_v4, fwg_version='4')
        print(f"  V4 Result: Found {len(lczs_v4.get(epw_path, []))} LCZs.")
        
    except Exception as e:
        print(f"  FAILED: {e}")

    # --- Test 2: MorphingIterator (Iterator) ---
    print("\n[Test 2] MorphingIterator Configuration Check")
    # We won't run a full grid search (too slow), but we'll configure it to ensure 
    # it accepts the new arguments and sets up the internal workflow correctly.
    
    try:
        iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)
        
        # Setup generic inputs
        epw_files = [epw_path]
        mapping = {'city': {'london': ['london', 'gatwick']}, 'uhi': {'type-2': 'type-2'}}
        
        # Prepare the runs DataFrame
        runs_df = iterator.get_template_dataframe()
        
        # We need to manually construct the dataframe rows to match the expected format
        # The iterator expects a DataFrame where each row is a run.
        
        # Row 1 setup
        row_data = {
            'epw_paths': epw_files,
            'keyword_mapping': mapping,
            'fwg_epw_original_lcz': 2,
            'fwg_target_uhi_lcz': 3,
            'fwg_interpolation_method_id': 0
        }
        
        # Append to dataframe (using loc for simplicity with single row)
        runs_df.loc[0] = pd.Series(row_data)

        print("  Configuring Iterator with V4 parameters...")
        iterator.set_default_values(
            final_output_dir='./test_iterator_results',
            output_filename_pattern='iter_{city}_{ssp}_{year}',
            scenario_mapping={'ssp245': 'SSP2-4.5'},
            fwg_jar_path=jar_v4,
            fwg_gcms=['BCC_CSM2_MR'],
            fwg_version='4' # The new argument we added
        )

        print("  Generating workflows...")
        iterator.generate_morphing_workflows(runs_df)
        
        print("  Iterator successfully generated workflows.")
        print(f"  Total prepared workflows: {len(iterator.prepared_workflows)}")
        
        # If we successfully loaded and configured without error, the pass-through worked.
        print("  Iterator successfully configured with V4 arguments.")

        
        # Verify the 'fwg_version' stored in default inputs
        stored_version = iterator.custom_defaults.get('fwg_version')
        if stored_version == '4':
            print("  PASSED: 'fwg_version' correctly stored in Iterator state.")
        else:
            print(f"  FAILED: 'fwg_version' not stored correctly. Found: {stored_version}")

    except Exception as e:
        print(f"  FAILED: {e}")

if __name__ == "__main__":
    test_remaining_components()
