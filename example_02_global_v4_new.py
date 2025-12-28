"""
EXAMPLE 02: Global V4 Usage (New)
---------------------------------
This script demonstrates how to use the `pyfwg` library with the NEW
Future Weather Generator v4.x.

Features of V4 Support:
1. Auto-detection: The library reads "v4" from the JAR filename.
2. New Command Structure: Uses `java -jar ... -key=value` instead of positional args.
"""

import os
import pyfwg
from pyfwg.workflow import MorphingWorkflowGlobal

def run_v4_global():
    # --- 1. Configuration ---
    
    # Path to your V4 JAR file
    # Ensure this path is correct on your system
    jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar"
    
    epw_dir = 'epws/wo_pattern'
    output_dir = './example_results_v4_global'
    temp_dir = r"D:\temp_pyfwg_v4"

    mapping = {
        'city': {
            'seville': ['sevilla', 'SVQ'],
            'london': ['london', 'gatwick'],
            'madrid': ['madrid', 'MAD']
        },
        'uhi': {
            'type-1': 'type-1', # v4 uses specific string keys, but pyfwg handles the translation
            'type-2': 'type-2'
        }
    }

    # --- 2. Initialize ---
    print("--- Initializing V4 Workflow ---")
    workflow = MorphingWorkflowGlobal()

    epw_files = [os.path.join(epw_dir, f) for f in os.listdir(epw_dir) if f.endswith('.epw')]
    
    workflow.map_categories(
        epw_files=epw_files,
        input_filename_pattern=None,
        keyword_mapping=mapping
    )

    # --- 3. Configure (V4 Specifics) ---
    workflow.configure_and_preview(
        final_output_dir=output_dir,
        output_filename_pattern='v4_{city}_{uhi}_{ssp}_{year}',
        scenario_mapping={'ssp245': 'SSP2-4.5', 'ssp585': 'SSP5-8.5'},
        
        fwg_jar_path=jar_path,
        
        # Valid Models: Ensure you use models supported by v4.
        # Check constants.py or the tool docs for list.
        # 'BCC_CSM2_MR' is a safe default for both.
        fwg_gcms=['BCC_CSM2_MR'], 
        
        fwg_create_ensemble=True,
        fwg_epw_original_lcz=2,
        fwg_target_uhi_lcz=3,
        
        run_incomplete_files=True,
        delete_temp_files=False,
        fwg_show_tool_output=True,
        temp_base_dir=temp_dir
        
        # OPTIONAL: You can explicitly set version if the filename doesn't have "v4"
        # fwg_version='4' 
    )

    # --- 4. Execute ---
    if workflow.is_config_valid:
        print("\nConfiguration Valid. Starting V4 Morphing...")
        workflow.execute_morphing()
        print(f"\nDone! Check results in: {os.path.abspath(output_dir)}")
    else:
        print("\nConfiguration Invalid. Please check the logs.")

if __name__ == "__main__":
    run_v4_global()
