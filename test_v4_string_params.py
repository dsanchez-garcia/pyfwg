
import os
from pyfwg.workflow import MorphingWorkflowGlobal

def test_v4_string_params():
    print("Testing V4 String Parameters...")
    
    workflow = MorphingWorkflowGlobal()
    
    # Mock inputs
    workflow.inputs = {
        'fwg_jar_path': 'dummy/path.jar',
        'fwg_params': {
            'interpolation_method_id': 'AVG4P', # String input!
            'solar_hour_adjustment': 'By_Day', # String input!
            'diffuse_irradiation_model': 'Paulescu_Blaga_2019', # String input!
            'add_uhi': True,
            'epw_original_lcz': 2,
            'target_uhi_lcz': 3
        }
    }
    
    # Manually invoke the potentially modified method
    print("  Invoking _build_command_v4 with string parameters...")
    try:
        cmd = workflow._build_command_v4(
            original_epw_path='test.epw',
            temp_epw_path='temp/test.epw',
            temp_output_dir='temp/out'
        )
        
        # Check if the strings persisted in the command
        cmd_str = " ".join(cmd)
        print(f"  Generated Command: {cmd_str}")
        
        if "-grid_interpolation_method=AVG4P" in cmd_str:
            print("  PASS: grid_interpolation_method correctly set to 'AVG4P'")
        else:
            print("  FAIL: grid_interpolation_method NOT set correctly")
            
        if "-solar_correction=By_Day" in cmd_str:
             print("  PASS: solar_correction correctly set to 'By_Day'")
        else:
             print("  FAIL: solar_correction NOT set correctly")
             
    except Exception as e:
        print(f"  FAIL: Exception raised: {e}")

if __name__ == "__main__":
    test_v4_string_params()
