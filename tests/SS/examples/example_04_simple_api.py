"""
EXAMPLE 04: Simplified API Usage (Direct Call)
----------------------------------------------
This script demonstrates how to use the simplified API functions `morph_epw_global`
and `morph_epw_europe`.

These functions are wrappers that handle the workflow setup for you. They are
ideal for simple scripts where you don't need complex file renaming tables.
"""

import os
from pyfwg.api import morph_epw_global, morph_epw_europe

def run_simple_api_examples():
    
    # --- Example A: Global Tool (V3 Legacy) ---
    print("\n--- Running Global V3 (Simple API) ---")
    jar_v3 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"
    
    # Just provide a list of paths
    epw_files = [r"epws/wo_pattern/GBR_London.Gatwick.037760_IWEC.epw"] 
    # (Update path above to a real file on your system if testing)

    if os.path.exists(epw_files[0]):
        morph_epw_global(
            epw_paths=epw_files,
            fwg_jar_path=jar_v3,
            output_dir='./example_results_api_v3',
            fwg_gcms=['BCC_CSM2_MR'],
            fwg_create_ensemble=False, # Faster for testing
            fwg_add_uhi=True,
            fwg_epw_original_lcz=2,
            fwg_target_uhi_lcz=3,
            fwg_show_tool_output=True
            # No version specified -> Auto-detects v3
        )
    else:
        print(f"Skipping V3 test: File not found {epw_files[0]}")


    # --- Example B: Global Tool (V4 New) ---
    print("\n--- Running Global V4 (Simple API) ---")
    jar_v4 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar"
    
    if os.path.exists(epw_files[0]):
        morph_epw_global(
            epw_paths=epw_files,
            fwg_jar_path=jar_v4,
            output_dir='./example_results_api_v4',
            fwg_gcms=['BCC_CSM2_MR'],
            fwg_add_uhi=True,
            fwg_target_uhi_lcz=3,
            fwg_show_tool_output=True,
            
            # Auto-detection works, but you can explicitly enforce it:
            fwg_version='4'
        )
    else:
        print(f"Skipping V4 test: File not found {epw_files[0]}")

if __name__ == "__main__":
    run_simple_api_examples()
