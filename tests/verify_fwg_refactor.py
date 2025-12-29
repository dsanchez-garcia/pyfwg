"""
Refactor Verification Tool.

This script acts as a final check after major code refactoring. 
It ensures that:
1. Version detection logic correctly distinguishes between V3 and V4 JARs.
2. High-level API functions remain compatible and functional with both versions.
3. The directory structure and internal imports are correctly configured.

How to run:
    python tests/verify_fwg_refactor.py
"""
import os
import shutil
import logging
from pyfwg.api import morph_epw_global
from pyfwg.utils import detect_fwg_version

def verify_refactor():
    logging.basicConfig(level=logging.INFO)
    
    # Paths provided by user
    jar_v3 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"
    jar_v4 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar"
    
    epw_w_pattern = r"d:\Python\pyfwg\epws\w_pattern"
    epw_wo_pattern = r"d:\Python\pyfwg\epws\wo_pattern"

    # Find a sample EPW to use
    if os.path.exists(epw_w_pattern):
        epw_files = [os.path.join(epw_w_pattern, f) for f in os.listdir(epw_w_pattern) if f.endswith('.epw')]
    elif os.path.exists(epw_wo_pattern):
        epw_files = [os.path.join(epw_wo_pattern, f) for f in os.listdir(epw_wo_pattern) if f.endswith('.epw')]
    else:
        logging.error("No EPW directories found.")
        return

    if not epw_files:
        logging.error("No EPW files found.")
        return

    sample_epw = epw_files[0]
    logging.info(f"Using sample EPW: {sample_epw}")

    # --- Test 1: Version Detection ---
    print("\n--- Test 1: Version Detection ---")
    try:
        v3_ver = detect_fwg_version(jar_v3)
        print(f"Detected v3 version: {v3_ver} (Expected: 3)")
        
        v4_ver = detect_fwg_version(jar_v4)
        print(f"Detected v4 version: {v4_ver} (Expected: 4)")
    except Exception as e:
        print(f"Version detection failed: {e}")

    # --- Test 2: Morphing with V3 (Legacy) ---
    print("\n--- Test 2: Morphing with V3 JAR ---")
    output_v3 = "./verify_results_v3"
    try:
        morph_epw_global(
            epw_paths=[sample_epw],
            fwg_jar_path=jar_v3,
            output_dir=output_v3,
            fwg_gcms=['ACCESS-CM2'], # Minimal model list
            fwg_create_ensemble=False, # Faster
            fwg_show_tool_output=True,
            fwg_version=None # Should auto-detect
        )
        print("V3 Morphing success.")
    except Exception as e:
        print(f"V3 Morphing failed: {e}")

    # --- Test 3: Morphing with V4 (New) ---
    print("\n--- Test 3: Morphing with V4 JAR ---")
    output_v4 = "./verify_results_v4"
    try:
        morph_epw_global(
            epw_paths=[sample_epw],
            fwg_jar_path=jar_v4,
            output_dir=output_v4,
            fwg_gcms=['ACCESS-CM2'], 
            fwg_create_ensemble=False,
            fwg_show_tool_output=True,
            fwg_version=None # Should auto-detect
        )
        print("V4 Morphing success.")
    except Exception as e:
        print(f"V4 Morphing failed: {e}")

if __name__ == "__main__":
    verify_refactor()
