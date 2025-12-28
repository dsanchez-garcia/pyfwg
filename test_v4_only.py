
import os
import shutil
import logging
from pyfwg.workflow import MorphingWorkflowGlobal

def run_v4_test():
    logging.basicConfig(level=logging.INFO)
    
    jar_v4 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar"
    epw_root = "epws/wo_pattern"

    if not os.path.exists(epw_root):
        print("EPW dir not found")
        return

    epw_files = [os.path.join(epw_root, f) for f in os.listdir(epw_root) if f.endswith('.epw')]
    if not epw_files:
        print("No EPW files")
        return
        
    test_epw_files = [epw_files[0]]
    print(f"Testing V4 with {test_epw_files[0]}")

    mapping = {
        'city': {'seville': ['sevilla', 'SVQ'], 'london': ['london', 'gatwick']},
        'uhi': {'type-1': 'type-1', 'type-2': 'type-2'}
    }

    print("\n" + "="*50)
    print("TEST 3: V4 Execution Check")
    print("="*50)

    try:
        workflow_v4 = MorphingWorkflowGlobal()
        workflow_v4.map_categories(
            epw_files=test_epw_files,
            input_filename_pattern=None,
            keyword_mapping=mapping
        )

        workflow_v4.configure_and_preview(
            final_output_dir='./test_results_v4_global_only',
            output_filename_pattern='v4_{city}_{uhi}_{ssp}_{year}',
            scenario_mapping={'ssp245': 'SSP2-4.5'},
            fwg_jar_path=jar_v4,
            run_incomplete_files=True,
            delete_temp_files=False,
            fwg_show_tool_output=True,
            fwg_gcms=['BCC_CSM2_MR'],  # VALID MODEL
            temp_base_dir='./temp_v4_global_only',
            fwg_epw_original_lcz=2,
            fwg_target_uhi_lcz=3,
            fwg_version='4'
        )
        
        if workflow_v4.is_config_valid:
            print("Configuration Valid. Launching...")
            # We will just verify it DOES NOT raise an immediate error.
            # We can't easily timeout the python call without threads/signals, 
            # so we let it run for a bit and rely on the agent to kill it if it hangs.
            workflow_v4.execute_morphing() 
            print(">> Test 3 PASSED: Workflow execution attempted.")
        else:
            print(">> Test 3 FAILED: Configuration invalid.")

    except Exception as e:
        print(f">> Test 3 FAILED with Exception: {e}")

if __name__ == "__main__":
    run_v4_test()
