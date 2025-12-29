"""
EXAMPLE 03: Europe Legacy Usage
-------------------------------
This script demonstrates how to use the Europe-specific version of FWG.
Note that Europe v1.x uses the Legacy command structure (Positional Arguments),
similar to Global v3.
"""

import os
import pyfwg
from pyfwg.workflow import MorphingWorkflowEurope

def run_europe_legacy():
    # --- 1. Configuration ---
    
    # Path to Europe JAR
    jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v1.0.1.jar"
    
    epw_dir = 'epws/wo_pattern'
    output_dir = './example_results_europe'
    temp_dir = r"D:\temp_pyfwg_europe"

    mapping = {
        'city': {
            'seville': ['sevilla', 'SVQ'],
            'london': ['london', 'gatwick'],
            'madrid': ['madrid', 'MAD']
        },
        'uhi': {
            'type-1': 'type-1',
            'type-2': 'type-2'
        }
    }

    # --- 2. Initialize Europe Workflow ---
    print("--- Initializing Europe Workflow ---")
    workflow = MorphingWorkflowEurope()

    epw_files = [os.path.join(epw_dir, f) for f in os.listdir(epw_dir) if f.endswith('.epw')]
    
    workflow.map_categories(
        epw_files=epw_files,
        input_filename_pattern=None,
        keyword_mapping=mapping
    )

    # --- 3. Configure ---
    workflow.configure_and_preview(
        final_output_dir=output_dir,
        # Europe tool typically uses {rcp} instead of {ssp}
        output_filename_pattern='europe_{city}_{uhi}_{rcp}_{year}',
        
        # Map scenario keys to official names
        scenario_mapping={'rcp26': 'RCP-2.6', 'rcp85': 'RCP-8.5'},
        
        fwg_jar_path=jar_path,
        
        # Europe tool uses RCM pairs, not single GCMs
        fwg_rcm_pairs=['ICHEC_EC_EARTH_SMHI_RCA4'],
        
        fwg_create_ensemble=True,
        fwg_epw_original_lcz=2,
        fwg_target_uhi_lcz=3,
        
        run_incomplete_files=True,
        delete_temp_files=False,
        fwg_show_tool_output=True,
        temp_base_dir=temp_dir
    )

    # --- 4. Execute ---
    if workflow.is_config_valid:
        print("\nConfiguration Valid. Starting Europe Morphing...")
        workflow.execute_morphing()
        print(f"\nDone! Check results in: {os.path.abspath(output_dir)}")
    else:
        print("\nConfiguration Invalid. Please check the logs.")

if __name__ == "__main__":
    run_europe_legacy()
