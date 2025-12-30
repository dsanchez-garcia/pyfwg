import pyfwg
from os import listdir
epw_files = ['epws/wo_pattern/'+ i for i in listdir('epws/wo_pattern')]


lczs = pyfwg.get_available_lczs(
    epw_paths=epw_files,
    # fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v1.0.1.jar",
    fwg_jar_path=r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_Europe_v2.0.2.jar",
    show_tool_output=True
)


