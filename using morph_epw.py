from pyfwg import morph_epw

jar_path = r"D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\FutureWeatherGenerator_v3.0.1.jar"
epw_file = 'MAD_ICU_type-2.epw'

# La validación se ejecuta automáticamente.
created_files_custom = morph_epw(
    epw_paths=epw_file,
    fwg_jar_path=jar_path,
    output_dir='./custom_output',
    fwg_show_tool_output=True,
    fwg_gcms=['CanESM5'], # Usar solo dos GCMs
    fwg_interpolation_method_id=2  # Usar el método "nearest point"
)

print("Successfully created files:")
for f in created_files_custom:
    print(f)