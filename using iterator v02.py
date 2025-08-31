import pandas as pd
import os
from pyfwg.wip import MorphingWorkflowGlobal
from pyfwg.wip.iterator_v02 import MorphingIterator

# --- 1. Initialize the iterator ---
iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)

# --- 2. Define common parameters for all runs ---
iterator.set_default_values(
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
    output_filename_pattern='{city}_{uhi}_interp-{fwg_interpolation_method_id}_{ssp}_{year}',
    fwg_epw_original_lcz=2,
    fwg_target_uhi_lcz=3
)

# --- 3. Get the template and define the scenarios ---
user_df = iterator.get_template_dataframe()
epw_files_dir = 'epws/wo_pattern'
epw_files = [os.path.join(epw_files_dir, f) for f in os.listdir(epw_files_dir)]

user_df.loc[0] = {
    'epw_paths': epw_files[0],
    'final_output_dir': './results/0',
    'fwg_gcms': ['CanESM5']
}
user_df.loc[1] = {
    'epw_paths': epw_files[1],
    'final_output_dir': './results/1',
    'fwg_gcms': ['MIROC6']
}

# --- 4. Generate the full execution plan ---
# The mapping strategy is now a static argument for the whole batch.
mapping_rules = {
    'city': {'seville': ['sevilla', 'SVQ'], 'madrid': ['madrid', 'MAD']},
    'uhi': {'type_1': 'type-1', 'type_2': 'type-2'}
}
execution_plan_df = iterator.generate_execution_plan(
    user_df,
    keyword_mapping=mapping_rules
)

print("--- Detailed Execution Plan ---")
print(execution_plan_df[['epw_paths', 'final_output_dir', 'fwg_gcms', 'cat_city', 'cat_uhi']])

# --- 5. Prepare all workflow instances for execution ---
iterator.prepare_workflows(
    execution_plan_df,
    keyword_mapping=mapping_rules
)

# --- 6. (Optional) Inspect a prepared workflow ---
# ... (inspection code remains the same)

# --- 7. Execute the entire batch ---
iterator.execute_workflows()