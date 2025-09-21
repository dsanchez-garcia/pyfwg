import pandas as pd
import os
from pyfwg.wip import MorphingWorkflowGlobal, get_available_lczs
from pyfwg.wip.iterator_v06 import MorphingIterator


# --- 1. Initialize the iterator ---
# We specify that we want to use the Global tool for all runs.
iterator = MorphingIterator(workflow_class=MorphingWorkflowGlobal)

# --- 2. Define common parameters for all runs ---
# We set the JAR path and other common settings as defaults for the entire batch.
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

iterator.set_default_values(
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
    output_filename_pattern='{city}_{uhi}_interp-{fwg_interpolation_method_id}_{ssp}_{year}',
    fwg_epw_original_lcz=2,
    fwg_target_uhi_lcz=3,
    # fwg_rcm_pairs=['ICHEC_EC_EARTH_SMHI_RCA4'],
)

# --- 3. Get the template and define the scenarios ---
# This DataFrame will define what changes between each run.
user_df = iterator.get_template_dataframe()

# Define the list of EPW files to be processed.
epw_files_dir = 'epws/wo_pattern'
epw_files = [os.path.join(epw_files_dir, f) for f in os.listdir(epw_files_dir)]

# Get available LCZs for each EPW file.
available_lczs = get_available_lczs(
    epw_paths=epw_files,
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
)

## --- Scenario 1: Run the first EPW file with one set of GCMs ---
user_df.loc[0] = {
    'epw_paths': epw_files[0],
    'final_output_dir': './results/0',
    'fwg_gcms': ['CanESM5'],
    # 'fwg_rcm_pairs': ['ICHEC_EC_EARTH_SMHI_RCA4']
}

# --- Scenario 2: Run the second EPW file with a different GCM ---
user_df.loc[1] = {
    'epw_paths': epw_files[1],
    'final_output_dir': './results/1',
    'fwg_gcms': ['MIROC6'],
    # 'fwg_rcm_pairs': ['ICHEC_EC_EARTH_SMHI_RCA4']
}

# --- 4. Generate the full execution plan AND prepare the workflows ---
# This single method now applies defaults, adds the new 'cat_' columns,
# and prepares the workflow instances in the background.
execution_plan_df = iterator.generate_execution_plan(
    scenarios_df=user_df,
    keyword_mapping=mapping_rules # The mapping strategy is now a static argument here.
)

# print("--- Detailed Execution Plan ---")
# # Display the key columns to verify the plan, including the new category columns.
# print(execution_plan_df[[
#     'epw_paths',
#     'final_output_dir',
#     'fwg_gcms',
#     'cat_city', # This column is new!
#     'cat_uhi'   # This column is new!
# ]])

## --- 5. (Optional) Inspect a prepared workflow ---
# You can now access the list of prepared workflows to check them before running.
print("\n--- Inspecting first prepared workflow ---")
if iterator.prepared_workflows:
    first_workflow = iterator.prepared_workflows[0]
    print(f"Is config valid? {first_workflow.is_config_valid}")
    print(f"Files to be morphed: {[os.path.basename(p) for p in first_workflow.epws_to_be_morphed]}")
    print(f"Final FWG Params: {first_workflow.inputs['fwg_params']}")
else:
    print("No workflows were prepared, likely due to errors in the plan.")

## --- 6. Execute the entire batch ---
# This method now takes no arguments and runs the workflows prepared in the previous step.
print("\n--- Running Step 6: execute_workflows ---")
# Uncomment the following line to run the process:
iterator.execute_workflows()

print("\nScript finished. Uncomment the final line to execute the morphing.")