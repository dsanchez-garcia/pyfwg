import pandas as pd
import os
from pyfwg.wip import MorphingWorkflowGlobal
from pyfwg.wip.iterator_v01 import MorphingIterator

# --- 1. Initialize the iterator ---
# We specify that we want to use the Global tool for all runs.
iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)

# Define the keyword mapping rules that will be used for all runs in this batch.
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


# --- 2. Define common parameters for all runs ---
# We set the JAR path as a default for the entire batch.
iterator.set_default_values(
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
    keyword_mapping=mapping_rules,
    output_filename_pattern='{city}_{uhi}_interp-{fwg_interpolation_method_id}_{ssp}_{year}',
    fwg_epw_original_lcz=2,
    fwg_target_uhi_lcz=3
)

# --- 3. Get the template and define the scenarios ---
# This DataFrame will define what changes between each run.
user_df = iterator.get_template_dataframe()


# Define the list of EPW files to be processed.
epw_files_dir = 'epws/wo_pattern'
epw_files = [os.path.join(epw_files_dir, f) for f in os.listdir(epw_files_dir)]

# --- Scenario 1: Run all EPW files with one set of GCMs ---
user_df.loc[0] = {
    'epw_paths': epw_files[0],
    'final_output_dir': './results/0',
    # 'output_filename_pattern': '{city}_{uhi}_interp-{fwg_interpolation_method_id}_{ssp}_{year}',
    'fwg_gcms': ['CanESM5']
}

# --- Scenario 2: Run all EPW files again with a different GCM ---
user_df.loc[1] = {
    'epw_paths': epw_files[1],
    'final_output_dir': './results/1',
    # 'output_filename_pattern': '{city}_{uhi}_interp-{fwg_interpolation_method_id}_{ssp}_{year}',
    'fwg_gcms': ['MIROC6']
}

# --- 4. (Optional) Apply defaults and review the full execution plan ---
execution_plan_df = iterator.apply_defaults(user_df)

print("--- Final Execution Plan ---")
# Display the key columns to verify the plan.
print(execution_plan_df[[
    'epw_paths',
    'final_output_dir',
    'fwg_gcms',
    'fwg_interpolation_method_id' # This will be filled with the default value (0)
]])

## --- 5. Execute the iterator ---
# The iterator will now run two scenarios based on the DataFrame.
# Uncomment the following line to run the process:
iterator.run_from_dataframe(execution_plan_df)

print("\nScript finished. Uncomment the final line to execute the morphing.")