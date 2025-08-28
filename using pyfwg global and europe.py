




import pyfwg.wip as pyfwg
from os import listdir

# jar_path = 'D:\\OneDrive - Universidad de Cádiz (uca.es)\\Programas\\FutureWeatherGenerator_v3.0.0.jar'
jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"

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


workflow_direct = pyfwg.MorphingWorkflowGlobal()
workflow_direct.map_categories(
    epw_files=epw_files,
    input_filename_pattern=None,  # Explicitly set to None
    keyword_mapping=mapping
)

workflow_direct.preview_rename_plan(
    final_output_dir='./final_results_global',
    output_filename_pattern='{city}_{uhi}_{ssp}_{year}',
    scenario_mapping={'ssp245': 'SSP2-4.5'}
)

workflow_direct.set_morphing_config(
    fwg_jar_path=jar_path,
    run_incomplete_files=False,
    delete_temp_files=False,
    fwg_show_tool_output=True,
    fwg_gcms=['BCC_CSM2_MR'],
    temp_base_dir=r'D:\temp_pyfwg',
    fwg_epw_original_lcz=2,
    fwg_target_uhi_lcz=3
)
#
workflow_direct.execute_morphing()

##

import pyfwg.wip as pyfwg
from os import listdir

jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v1.0.1.jar"

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


workflow_direct = pyfwg.MorphingWorkflowEurope()
workflow_direct.map_categories(
    epw_files=epw_files,
    input_filename_pattern=None,  # Explicitly set to None
    keyword_mapping=mapping
)

workflow_direct.preview_rename_plan(
    final_output_dir='./final_results_europe',
    output_filename_pattern='{city}_{uhi}_{rcp}_{year}',
    scenario_mapping={'rcp26': 'RCP-2.6'}
)

workflow_direct.set_morphing_config(
    fwg_jar_path=jar_path,
    run_incomplete_files=False,
    delete_temp_files=False,
    fwg_show_tool_output=True,
    fwg_rcm_pairs=['ICHEC_EC_EARTH_SMHI_RCA4'],
    temp_base_dir=r'D:\temp_pyfwg',
    fwg_epw_original_lcz=2,
    fwg_target_uhi_lcz=3
)
#
workflow_direct.execute_morphing()
