import os
import logging
from pyfwg.utils import uhi_morph

# Constants (adapted from run_complete_suite.py)
# Note: These paths are specific to the user's system as seen in run_complete_suite.py
JAR_V4 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar"
JAR_EUR_V2 = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v2.0.2.jar"
EPW_FILE = r"epws/wo_pattern/GBR_London.Gatwick.037760_IWEC_uhi_type-2.epw"
OUTPUT_DIR = os.path.join(os.getcwd(), "tests", "test_uhi_results")

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def test_uhi_morph_global_autodetect():
    print("\n" + "="*50)
    print("Testing uhi_morph (Global) - AUTODETECT")
    print("="*50)
    out_dir = os.path.join(OUTPUT_DIR, "global_uhi_auto")
    if not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    
    try:
        # Testing autodetection of version and tool type
        uhi_morph(
            fwg_epw_path=os.path.abspath(EPW_FILE),
            fwg_jar_path=JAR_V4,
            fwg_output_dir=out_dir,
            fwg_original_lcz=2,
            fwg_target_lcz=3,
            # java_class_path_prefix and fwg_version omitted
            show_tool_output=True
        )
        print("\nSUCCESS: Global UHI (Autodetect) completed.")
        files = os.listdir(out_dir)
        print(f"Produced files: {files}")
    except Exception as e:
        print(f"\nFAILED Global Autodetect: {e}")

def test_uhi_morph_europe_autodetect():
    print("\n" + "="*50)
    print("Testing uhi_morph (Europe) - AUTODETECT")
    print("="*50)
    out_dir = os.path.join(OUTPUT_DIR, "europe_uhi_auto")
    if not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    
    try:
        # Testing autodetection of version and tool type
        uhi_morph(
            fwg_epw_path=os.path.abspath(EPW_FILE),
            fwg_jar_path=JAR_EUR_V2,
            fwg_output_dir=out_dir,
            fwg_original_lcz=2,
            fwg_target_lcz=3,
            # java_class_path_prefix and fwg_version omitted
            show_tool_output=True
        )
        print("\nSUCCESS: Europe UHI (Autodetect) completed.")
        files = os.listdir(out_dir)
        print(f"Produced files: {files}")
    except Exception as e:
        print(f"\nFAILED Europe Autodetect: {e}")

if __name__ == "__main__":
    setup_logger()
    
    # Ensure paths are absolute and accessible
    full_epw_path = os.path.abspath(EPW_FILE)
    
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"Checking EPW file at: {full_epw_path}")
    
    if not os.path.exists(full_epw_path):
        print(f"CRITICAL ERROR: EPW file not found at {full_epw_path}")
    else:
        # Check if JARs exist
        if not os.path.exists(JAR_V4):
            print(f"WARNING: Global JAR not found at {JAR_V4}")
        else:
            test_uhi_morph_global_autodetect()
            
        if not os.path.exists(JAR_EUR_V2):
            print(f"WARNING: Europe JAR not found at {JAR_EUR_V2}")
        else:
            test_uhi_morph_europe_autodetect()
    
    print("\n" + "="*50)
    print("TESTING FINISHED")
    print("="*50)
