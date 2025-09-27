import pandas as pd
from pyfwg import MorphingWorkflowGlobal, export_template_to_excel, load_runs_from_excel, get_available_lczs

import os, pandas as pd
from pyfwg import MorphingIterator


# --- PASO 1: Instanciar la clase ---
iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)

# --- PASO 2: Define los valores comunes para todas las ejecuciones (valores por defecto) ---

mapping_rules = {
    'city': {
        'seville': ['sevilla', 'SVQ'],
        'london': ['london', 'gatwick']
    },
    'uhi': {
        'type_1': 'type-1',
        'type_2': 'type-2'
    }
}


# Define the list of EPW files to be processed.
epw_files_dir = 'epws/wo_pattern'
epw_files = [os.path.join(epw_files_dir, f) for f in os.listdir(epw_files_dir) if f.endswith('.epw')]


# Get available LCZs for each EPW file. Check the LCZs are valid.
available_lczs = get_available_lczs(
    epw_paths=epw_files,
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
)


iterator.set_default_values(
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
    # output_filename_pattern='{city}_{uhi}_gcm-{fwg_gcms}_{ssp}_{year}', # to avoid overwriting files, you should include in the filename pattern the parameters that change between runs
    # output_filename_pattern='{city}_{uhi}_gcm-sindistinguir_{ssp}_{year}',  # to avoid overwriting files, you should include in the filename pattern the parameters that change between runs
    output_filename_pattern='{city}_no-uhi_gcm-{fwg_gcms}_{ssp}_{year}',  # to avoid overwriting files, you should include in the filename pattern the parameters that change between runs
    # output_filename_pattern='{city}_no-uhi_no-gcm_{ssp}_{year}',  # to avoid overwriting files, you should include in the filename pattern the parameters that change between runs

    # Acabamos de comprobar que los LCZs 2 y 3 están disponibles para todos los EPWs, por lo que procedemos a usarlos como valores por defecto.
    # En caso de que no coincidieran, habría que definir los LCZs en los parámetros que cambian, en el siguiente paso
    fwg_epw_original_lcz=2,
    fwg_target_uhi_lcz=3,
    # fwg_rcm_pairs=['ICHEC_EC_EARTH_SMHI_RCA4'],

)



# --- PASO 3: definir los valores de los parámetros que van a cambiar ---


# --- PASO 3.1: Opción 1. El Usuario Edita el Archivo Excel ---
template_path = 'my_parametric_study.xlsx'
export_template_to_excel(iterator, file_path=template_path)

#
# En este punto, el usuario abre 'my_parametric_study.xlsx',
# rellena las filas con sus escenarios y lo guarda.
# Por ejemplo, en la columna 'fwg_gcms', escribiría: ['CanESM5', 'MIROC6']

# Definimos el path del archivo modificado
template_path_mod = 'my_parametric_study_modified.xlsx'

#Mostramos el dataframe modificado
print(pd.read_excel(template_path_mod))

# -- Cargar los runs desde Excel ---
runs_from_excel = load_runs_from_excel(template_path_mod)

print("--- Scenarios Loaded from Excel ---")
print(runs_from_excel)

# --- PASO 3.2: Opción 2. El Usuario añade filas al dataframe

# This DataFrame will define what changes between each run.
user_df = iterator.get_template_dataframe()


# --- Run 1: Run the first EPW file with one set of GCMs ---

user_df.loc[0] = {
    'epw_paths': epw_files[0],
    'final_output_dir': './results/0',
    'fwg_gcms': ['CanESM5'],
    # 'fwg_rcm_pairs': ['ICHEC_EC_EARTH_SMHI_RCA4']
}

# --- Run 2: Run the second EPW file with a different GCM ---
user_df.loc[1] = {
    'epw_paths': epw_files[1],
    'final_output_dir': './results/1',
    'fwg_gcms': ['MIROC6'],
    # 'fwg_rcm_pairs': ['ICHEC_EC_EARTH_SMHI_RCA4']
}

# --- PASO 3.3: Opción 3. El Usuario añade filas al dataframe modificado con excel

from pyfwg import DEFAULT_GLOBAL_GCMS
first_gcm = list(DEFAULT_GLOBAL_GCMS)[0]
runs_from_excel_modified = runs_from_excel.copy()
runs_from_excel_modified.loc[2] = {
    'epw_paths': epw_files[1],
    'final_output_dir': 'results_using_excel/seville',
    'fwg_gcms': [first_gcm],
    # 'fwg_rcm_pairs': ['ICHEC_EC_EARTH_SMHI_RCA4']
}


# --- PASO 4: Generar los MorphingWorkflow instances ---





iterator.generate_morphing_workflows(
    runs_df=runs_from_excel_modified,
    keyword_mapping=mapping_rules
    # ... parámetros de mapeo
)

## --- PASO 5: Ejecutar los MorphingWorkflow instances ---
iterator.run_morphing_workflows(show_tool_output=True)
