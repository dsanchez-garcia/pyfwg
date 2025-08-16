



# --- USAGE EXAMPLE ---
## --- EXAMPLE 1: Using a regex pattern for structured filenames ---
import pyfwg
from os import listdir

print("--- EXAMPLE 1: Using a Regex Pattern ---")
jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.0.jar"

epw_files = ['epws/w_pattern/'+ i for i in listdir('epws/w_pattern')]

workflow_pattern = pyfwg.MorphingWorkflow()

mapping = {
        'city': {
            'seville': ['sevilla', 'SVQ'],
            'madrid': ['madrid', 'MAD']
        },
        'uhi': {
            'type_1': ['type-1'],
            'type_2': ['type-2']
        }
    }


workflow_pattern.map_categories(
    epw_files=epw_files,
    input_filename_pattern=r'(?P<city>.*?)_(?P<uhi>.*)',
    keyword_mapping=mapping
)

workflow_pattern.preview_rename_plan(
    final_output_dir='./final_results_direct_map_2',
    output_filename_pattern='{city}_{uhi}_{ssp}_{year}',
    # output_filename_pattern='{city}_{uhi}_{ssp}',
    scenario_mapping={'ssp245': 'SSP2-4.5'}
)


# models = pyfwg.DEFAULT_GCMS

workflow_pattern.set_morphing_config(
    fwg_jar_path=jar_path,
    run_incomplete_files=False,
    delete_temp_files=False,
    fwg_show_tool_output=True,
    fwg_gcms=['BCC_CSM2_MR'],
    temp_base_dir=r'D:\temp_pyfwg_2'
)
#
workflow_pattern.execute_morphing()

## --- EXAMPLE 2: No pattern, using direct mapping for irregular filenames ---

import pyfwg
from os import listdir

# jar_path = 'D:\\OneDrive - Universidad de Cádiz (uca.es)\\Programas\\FutureWeatherGenerator_v3.0.0.jar'
jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.0.jar"

print("--- EXAMPLE 2: Using Direct Mapping (No Pattern) ---")
epw_files = ['epws/wo_pattern/'+ i for i in listdir('epws/wo_pattern')]

mapping = {
        'city': {
            'seville': ['sevilla', 'SVQ'],
            'madrid': ['madrid', 'MAD']
        },
        'uhi': {
            'type_1': 'type-1',
            'type_2': 'type-2'
        }
    }


workflow_direct = pyfwg.MorphingWorkflow()
workflow_direct.map_categories(
    epw_files=epw_files,
    input_filename_pattern=None,  # Explicitly set to None
    keyword_mapping=mapping
)

workflow_direct.preview_rename_plan(
    final_output_dir='./final_results_direct_map',
    output_filename_pattern='{city}_{uhi}_{ssp}_{year}',
    scenario_mapping={'ssp245': 'SSP2-4.5'}
)

workflow_direct.set_morphing_config(
    fwg_jar_path=jar_path,
    run_incomplete_files=False,
    delete_temp_files=False,
    fwg_show_tool_output=True,
    fwg_gcms=['BCC_CSM2_MR'],
    temp_base_dir=r'D:\temp_pyfwg'
)
#
workflow_direct.execute_morphing()