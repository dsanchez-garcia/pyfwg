# import pyfwg.wip as pyfwg
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

from pyfwg.wip.utils import uhi_morph
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

from pyfwg.wip.utils import check_lcz_availability

lczs = check_lcz_availability(
    epw_path=r'D:\Python\pyfwg\Seville_Present.epw',
    original_lcz=2,
    target_lcz=4,
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar",
)

##

import pyfwg.wip as pyfwg

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
    fwg_target_uhi_lcz=1
)
