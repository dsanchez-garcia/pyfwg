# import pyfwg as pyfwg
#
#
# pyfwg.uhi_morph(
#     fwg_epw_path=r'D:\Python\pyfwg\Seville_Present.epw',
#     fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
#     fwg_output_dir='./uhi_morph_output',
#     fwg_original_lcz=1,
#     fwg_target_lcz=1,
#     fwg_limit_variables=True,
#     show_tool_output=True
# )

##

from pyfwg.utils import uhi_morph
uhi_morph(
    fwg_epw_path=r'D:\Python\pyfwg\Seville_Present.epw',
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
    fwg_output_dir='./uhi_morph_output',
    fwg_original_lcz=1,
    fwg_target_lcz=1,
    fwg_limit_variables=True,
    show_tool_output=True
)

##

from pyfwg.utils import check_lcz_availability

lczs = check_lcz_availability(
    epw_path=r'D:\PythonProjects\pyfwg\Seville_Present.epw',
    original_lcz=2,
    target_lcz=4,
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
    java_class_path_prefix='futureweathergenerator'
)

##

import pyfwg

available_zones = pyfwg.get_available_lczs(
    epw_paths='Seville_Present.epw',
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
    # In java_class_path_prefix, use 'futureweathergenerator' for the global scope FWG tool, otherwise 'futureweathergenerator_europe'
    java_class_path_prefix='futureweathergenerator',
    show_tool_output=False,
)

##

import pyfwg as pyfwg

jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"
epw_file = 'Seville_Present.epw'

# La validación se ejecuta automáticamente.
created_files_custom = pyfwg.morph_epw_global(
    epw_paths=epw_file,
    fwg_jar_path=jar_path,
    output_dir='./custom_output_3',
    fwg_show_tool_output=True,
    delete_temp_files=False,
    fwg_gcms=['CanESM5'], # Usar solo dos GCMs
    fwg_interpolation_method_id=2,  # Usar el método "nearest point"
    fwg_epw_original_lcz=1,
    fwg_target_uhi_lcz=4
)

##

import pyfwg as pyfwg

jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v1.0.1.jar"
epw_file = 'Seville_Present.epw'

# La validación se ejecuta automáticamente.
created_files_custom = pyfwg.morph_epw_europe(
    epw_paths=epw_file,
    fwg_jar_path=jar_path,
    output_dir='./custom_output_5',
    fwg_show_tool_output=True,
    delete_temp_files=False,
    fwg_rcm_pairs=['ICHEC_EC_EARTH_SMHI_RCA4'], # Usar solo dos GCMs
    fwg_interpolation_method_id=2,  # Usar el método "nearest point"
    fwg_epw_original_lcz=2,
    fwg_target_uhi_lcz=3
)
