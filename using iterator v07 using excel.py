import pandas as pd
from pyfwg.wip import MorphingWorkflowGlobal, export_template_to_excel, load_runs_from_excel, get_available_lczs

import os
from pyfwg.wip.iterator_v07 import MorphingIterator


# --- PASO 1: Exportar la Plantilla ---
iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)


iterator.set_default_values(
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
    output_filename_pattern='{city}_{uhi}_interp-{fwg_interpolation_method_id}_{ssp}_{year}',
    fwg_epw_original_lcz=2,
    fwg_target_uhi_lcz=3,
    # fwg_rcm_pairs=['ICHEC_EC_EARTH_SMHI_RCA4'],

)


template_path = 'my_parametric_study.xlsx'
export_template_to_excel(iterator, file_path=template_path)

# --- PASO 2: El Usuario Edita el Archivo Excel ---
#
# En este punto, el usuario abre 'my_parametric_study.xlsx',
# rellena las filas con sus escenarios y lo guarda.
# Por ejemplo, en la columna 'fwg_gcms', escribiría: ['CanESM5', 'MIROC6']
#
# --- PASO 3: Cargar los Escenarios desde Excel ---
template_path_mod = 'my_parametric_study_modified.xlsx'
scenarios_from_excel = load_runs_from_excel(template_path_mod)

print("--- Scenarios Loaded from Excel ---")
print(scenarios_from_excel)

# --- PASO 4: Generar el Plan de Ejecución (como antes) ---

epw_files_dir = 'epws/wo_pattern'
epw_files = [os.path.join(epw_files_dir, f) for f in os.listdir(epw_files_dir)]

# Get available LCZs for each EPW file.
available_lczs = get_available_lczs(
    epw_paths=epw_files,
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
)
##


mapping_rules = {
    'city': {
        'seville': ['sevilla', 'SVQ'],
        'madrid': ['madrid', 'MAD']
    },
    'uhi': {
        'type_1': 'type-1',
        'type_2': 'type-2'
    }
}


iterator.generate_morphing_workflows(
    runs_df=scenarios_from_excel,
    keyword_mapping=mapping_rules
    # ... parámetros de mapeo
)

## --- PASO 5: Preparar y Ejecutar (como antes) ---
iterator.run_morphing_workflows(show_tool_output=True)
# iterator.execute_workflows()