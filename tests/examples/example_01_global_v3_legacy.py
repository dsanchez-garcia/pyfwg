"""
EXAMPLE 01: Global V3 Legacy Usage
----------------------------------
This script demonstrates how to use the `pyfwg` library with the legacy
Future Weather Generator v3.x (Global).

It uses the Class-based workflow (`MorphingWorkflowGlobal`) which is best
when you need detailed categorization, renaming maps, and control over step-by-step execution.
"""

import os
import pyfwg
from pyfwg.workflow import MorphingWorkflowGlobal

def run_legacy_global():
    # --- 1. Configuration ---
    
    # Path to your V3 JAR file
    jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"
    
    # Directory containing your source EPW files
    epw_dir = 'epws/wo_pattern'
    
    # Where to save the final results
    output_dir = './example_results_v3_global'
    
    # Temporary directory (useful to verify intermediate steps, or delete later)
    temp_dir = r"D:\temp_pyfwg_v3"

    # Define how to interpret filenames (Pattern Matching)
    # Example: seville_uhi-type-1.epw -> city=seville, uhi=type-1
    mapping = {
        'city': {
            'seville': ['sevilla', 'SVQ'],
            'london': ['london', 'gatwick'],
            'madrid': ['madrid', 'MAD']
        },
        'uhi': {
            'type-1': 'type-1',
            'type_1': 'type-1',
            'type-2': 'type-2',
            'type_2': 'type-2'
        }
    }

    # --- 2. Initialize Workflow ---
    print("--- Initializing V3 Workflow ---")
    workflow = MorphingWorkflowGlobal()

    # --- 3. Map Files ---
    # Get all .epw files from the directory
    epw_files = [os.path.join(epw_dir, f) for f in os.listdir(epw_dir) if f.endswith('.epw')]
    
    workflow.map_categories(
        epw_files=epw_files,
        input_filename_pattern=None, # Use keyword mapping mode
        keyword_mapping=mapping
    )

    # --- 4. Configure & Preview ---
    workflow.configure_and_preview(
        final_output_dir=output_dir,
        # Define how you want the output files to be named
        output_filename_pattern='v3_{city}_{uhi}_{ssp}_{year}',
        
        scenario_mapping={'ssp245': 'SSP2-4.5', 'ssp585': 'SSP5-8.5'},
        
        fwg_jar_path=jar_path,
        
        # Tool Parameters
        fwg_gcms=['BCC_CSM2_MR'], # Select specific models (must be valid for v3)
        fwg_create_ensemble=True,
        fwg_epw_original_lcz=2,
        fwg_target_uhi_lcz=3,
        
        # Operational parameters
        run_incomplete_files=True,
        delete_temp_files=False,
        fwg_show_tool_output=True,
        temp_base_dir=temp_dir
        
        # Note: 'fwg_version' is NOT specified. 
        # The system will auto-detect "v3" from the jar filename and use Legacy mode.
    )

    # --- 5. Execute ---
    if workflow.is_config_valid:
        print("\nConfiguration Valid. Starting Morphing...")
        workflow.execute_morphing()
        print(f"\nDone! Check results in: {os.path.abspath(output_dir)}")
    else:
        print("\nConfiguration Invalid. Please check the logs.")

if __name__ == "__main__":
    run_legacy_global()
