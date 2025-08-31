import pandas as pd
from pyfwg.wip import MorphingIterator, MorphingWorkflowGlobal

# --- 1. Inicializa el iterador ---
iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)

# --- 2. (NUEVO PASO) Define los valores comunes para todas las ejecuciones ---
iterator.set_default_values(
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
    input_filename_pattern=r'(?P<city>.*?)_present'
)

# --- 3. Obtén la plantilla y rellena solo lo que cambia ---
user_df = iterator.get_template_dataframe()

# Fila 1: Solo se definen los parámetros que son diferentes
user_df.loc[0] = {
    'epw_paths': 'epws/sevilla_present.epw',
    'final_output_dir': './results/run_sevilla',
    'output_filename_pattern': '{city}_{ssp}_{year}_interp-0',
    'fwg_interpolation_method_id': 0
}

# Fila 2: El fwg_jar_path y el input_pattern se heredarán de los defaults
user_df.loc[1] = {
    'epw_paths': 'epws/madrid_present.epw',
    'final_output_dir': './results/run_madrid',
    'output_filename_pattern': '{city}_{ssp}_{year}_interp-2',
    'fwg_interpolation_method_id': 2
}

# --- 4. (Opcional) Revisa el plan de ejecución completo ---
execution_plan_df = iterator.apply_defaults(user_df)
print(execution_plan_df[['epw_paths', 'fwg_jar_path', 'fwg_interpolation_method_id']])

# --- 5. Ejecuta el iterador ---
iterator.run_from_dataframe(execution_plan_df)