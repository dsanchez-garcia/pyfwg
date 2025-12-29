



"""
Work-in-Progress (WIP) Workflow Integration Test.

This script tests the direct usage of `MorphingWorkflowGlobal` and 
`MorphingWorkflowEurope` classes. It covers:
1. Category mapping across multiple EPW files.
2. Configuration of output filename patterns.
3. Execution of both global and European workflows in sequence.
"""

import pyfwg as pyfwg
from os import listdir

# jar_path = 'D:\\OneDrive - Universidad de Cádiz (uca.es)\\Programas\\FutureWeatherGenerator_v3.0.0.jar'
# jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"
jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar"

jar_paths = {
    r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar": './final_results_global_v3',
    r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v4.0.2.jar": './final_results_global_v4'
}

epw_files = ['epws/wo_pattern/'+ i for i in listdir('epws/wo_pattern')]

mapping = {
        'city': {
            'seville': ['sevilla', 'SVQ'],
            'london': ['london', 'gatwick']
        },
        'uhi': {
            'type-1': 'type-1',
            'type-2': 'type-2'
        }
    }

for k, v in jar_paths.items():
    workflow_direct = pyfwg.MorphingWorkflowGlobal()
    workflow_direct.map_categories(
        epw_files=epw_files,
        input_filename_pattern=None,  # Explicitly set to None
        keyword_mapping=mapping
    )

    workflow_direct.configure_and_preview(
        final_output_dir=v,
        output_filename_pattern='{city}_{uhi}_interp-{fwg_interpolation_method_id}_{ssp}_{year}',
        scenario_mapping={'ssp245': 'SSP2-4.5'},

        fwg_jar_path=k,
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

import pyfwg as pyfwg
from os import listdir

# jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v1.0.1.jar"

jar_paths = {
    r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v1.0.1.jar": './final_results_europe_v1',
    r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v2.0.2.jar": './final_results_europe_v2'
}


epw_files = ['epws/wo_pattern/'+ i for i in listdir('epws/wo_pattern')]

mapping = {
    'city': {
        'seville': ['sevilla', 'SVQ'],
        'london': ['london', 'gatwick']
    },
    'uhi': {
        'type-1': 'type-1',
        'type-2': 'type-2'
    }
}

for k, v in jar_paths.items():

    workflow_direct = pyfwg.MorphingWorkflowEurope()
    workflow_direct.map_categories(
        epw_files=epw_files,
        input_filename_pattern=None,  # Explicitly set to None
        keyword_mapping=mapping
    )


    workflow_direct.configure_and_preview(
        final_output_dir=v,
        output_filename_pattern='{city}_{uhi}_interp-{fwg_interpolation_method_id}_{rcp}_{year}',
        scenario_mapping={'rcp26': 'RCP-2.6'},

        fwg_jar_path=k,
        run_incomplete_files=False,
        delete_temp_files=False,
        fwg_show_tool_output=True,
        fwg_rcm_pairs=['ICHEC_EC_EARTH_SMHI_RCA4'],
        temp_base_dir=r'D:\temp_pyfwg_europe',
        fwg_epw_original_lcz=2,
        fwg_target_uhi_lcz=3
    )
    #
    workflow_direct.execute_morphing()
