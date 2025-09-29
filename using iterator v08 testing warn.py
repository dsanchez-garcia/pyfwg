from pyfwg import MorphingWorkflowGlobal, export_template_to_excel, load_runs_from_excel, get_available_lczs, MorphingIterator
import os, pandas as pd


# --- 1. Initialize the iterator ---
# We specify that we want to use the Global tool for all runs.
iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)

# --- 2. Define common parameters for all runs ---
# We set the JAR path and other common settings as defaults for the entire batch.
mapping_rules = {
    'city': {
        'seville': ['sevilla', 'SVQ'],
        'london': ['london', 'gatwick']
    },
    'uhi': {
        'type-1': 'type-1',
        'type-2': 'type-2'
    }
}

# Define the list of EPW files to be processed.
epw_files_dir = 'epws/wo_pattern'
epw_files = [os.path.join(epw_files_dir, f) for f in os.listdir(epw_files_dir) if f.endswith('.epw')]


available_lczs = get_available_lczs(
    epw_paths=epw_files,
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
)

iterator.set_default_values(
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
    output_filename_pattern='{city}_{uhi}_gcm-{fwg_gcms}_{ssp}_{year}', # to avoid overwriting files, you should include in the filename pattern the parameters that change between runs
    # output_filename_pattern='{city}_{uhi}_gcm-nodif_{ssp}_{year}',  # to avoid overwriting files, you should include in the filename pattern the parameters that change between runs

    # Acabamos de comprobar que los LCZs 2 y 3 están disponibles para todos los EPWs, por lo que procedemos a usarlos como valores por defecto.
    # En caso de que no coincidieran, habría que definir los LCZs en los parámetros que cambian, en el siguiente paso
)



# --- PASO 3: definir los valores de los parámetros que van a cambiar ---

# This DataFrame will define what changes between each run.
user_df = iterator.get_template_dataframe()


# --- Run 1: Run the first EPW file with one set of GCMs ---

user_df.loc[0] = {
    'epw_paths': epw_files[0],
    'final_output_dir': './results/0',
    'fwg_gcms': ['CanESM5'],
    'fwg_epw_original_lcz': 1,
    'fwg_target_uhi_lcz': 2,
}

# --- Run 2: Run the second EPW file with a different GCM ---
# user_df.loc[1] = {
#     'epw_paths': epw_files[1],
#     'final_output_dir': './results/1',
#     'fwg_gcms': ['MIROC6'],
#     'fwg_epw_original_lcz': 2,
#     'fwg_target_uhi_lcz': 3,
# }
user_df.loc[1] = {
    'epw_paths': epw_files[0],
    'final_output_dir': './results/0',
    'fwg_gcms': ['MIROC6'],
    'fwg_epw_original_lcz': 2,
    'fwg_target_uhi_lcz': 3,
}

# --- PASO 4: Generar los MorphingWorkflow instances ---





iterator.generate_morphing_workflows(
    runs_df=user_df,
    keyword_mapping=mapping_rules,
    raise_on_overwrite=False

)
##
iterator.run_morphing_workflows()