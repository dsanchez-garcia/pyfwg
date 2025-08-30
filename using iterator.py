import pandas as pd
from pyfwg.wip import MorphingIterator, MorphingWorkflowGlobal

# --- 1. Elige el flujo de trabajo e inicializa el iterador ---
iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)

# --- 2. Obtén y rellena la plantilla de escenarios ---
user_df = iterator.get_template_dataframe()

# Añade la primera fila (escenario 1)
user_df.loc[0] = {
    'epw_paths': 'epws/sevilla_present.epw', # EPW específico para esta fila
    'input_filename_pattern': r'(?P<city>.*?)_present',
    'final_output_dir': './results/run_sevilla',
    'output_filename_pattern': '{city}_{ssp}_{year}_interp-0',
    'fwg_jar_path': r"D:\path\to\your\FutureWeatherGenerator.jar",
    'fwg_interpolation_method_id': 0,
    'fwg_gcms': ['CanESM5']
}

# Añade la segunda fila (escenario 2)
user_df.loc[1] = {
    'epw_paths': [
        'epws/madrid_present.epw',
        # 'epws/barcelona_present.epw'
    ], # Múltiples EPWs
    'input_filename_pattern': r'(?P<city>.*?)_present',
    'final_output_dir': './results/run_mad',
    'output_filename_pattern': '{city}_{ssp}_{year}_interp-2',
    'fwg_jar_path': r"D:\path\to\your\FutureWeatherGenerator.jar",
    'fwg_interpolation_method_id': 2,
    'fwg_gcms': ['MIROC6']
}

execution_plan_df = iterator.apply_defaults(user_df)

##

# Muestra el plan
print("Scenarios to be executed:")
print(execution_plan_df[['epw_paths', 'final_output_dir', 'fwg_gcms']])

# --- 3. Ejecuta el iterador ---
# Ya no se pasan parámetros estáticos aquí.
iterator.run_from_dataframe(execution_plan_df)