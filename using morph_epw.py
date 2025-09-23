from pyfwg import morph_epw_global

jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"
epw_file = 'MAD_ICU_type-2.epw'

# La validación se ejecuta automáticamente.
created_files_custom = morph_epw_global(
    epw_paths=epw_file,
    fwg_jar_path=jar_path,
    output_dir='./custom_output',
    fwg_show_tool_output=False,
    delete_temp_files=False,
    fwg_gcms=['CanESM5'], # Usar solo dos GCMs
    fwg_interpolation_method_id=2,  # Usar el método "nearest point"
    fwg_epw_original_lcz=2,
    fwg_target_uhi_lcz=3,
)

# print("Successfully created files:")
# for f in created_files_custom:
#     print(f)

##

from pyfwg import morph_epw_europe

jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v1.0.1.jar"
epw_file = 'MAD_ICU_type-2.epw'

# La validación se ejecuta automáticamente.
created_files_custom = morph_epw_europe(
    epw_paths=epw_file,
    fwg_jar_path=jar_path,
    output_dir='./custom_output',
    fwg_show_tool_output=True,
    delete_temp_files=False,
    fwg_rcm_pairs=['ICHEC_EC_EARTH_SMHI_RCA4'],
    fwg_interpolation_method_id=2,  # Usar el método "nearest point"
    fwg_epw_original_lcz=2,
    fwg_target_uhi_lcz=3
)

# print("Successfully created files:")
# for f in created_files_custom:
#     print(f)

##
import os
from pyfwg import morph_epw_global

# --- Configuration ---
# Define the path to the EPW file to be processed. You can also define a list of paths to process multiple EPW files.
# epw_file = 'epws/w_pattern/sevilla_uhi-type-1.epw'
# epw_file = 'pyfwg/tutorials/epws/wo_pattern/GBR_London.Gatwick.037760_IWEC_uhi_type-2.epw'
epw_file = r'pyfwg/tutorials/epws/wo_pattern/GBR_London.Gatwick.037760_IWEC_uhi_type-2.epw'


# !!! IMPORTANT: You MUST change this path to the correct location on your PC !!!
jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"
# The validation of parameters is executed automatically inside the function.
created_files_custom = morph_epw_global(
    epw_paths=epw_file,
    fwg_jar_path=jar_path,
    output_dir='./custom_output',
    fwg_show_tool_output=True,
    delete_temp_files=False,
    fwg_gcms=['CanESM5'], # Usar solo dos GCMs
    fwg_interpolation_method_id=2,  # Usar el método "nearest point"
    fwg_epw_original_lcz=2,
    fwg_target_uhi_lcz=3,
)

print("\nSuccessfully created files:")
for f in created_files_custom:
    print(f)