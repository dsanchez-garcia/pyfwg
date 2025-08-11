from pyfwg import morph_epw

jar_path = r"D:\path\to\your\FutureWeatherGenerator_v3.0.0.jar"
epw_file = 'epws/sevilla_present.epw'

# --- CASO 1: Uso simple con valores por defecto ---
# Solo se requieren las rutas.
# created_files = morph_epw(epw_paths=epw_file, fwg_jar_path=jar_path)


# --- CASO 2: Uso avanzado con parámetros personalizados ---
# El usuario puede anular cualquier parámetro de FWG que desee.
# La validación se ejecuta automáticamente.
created_files_custom = morph_epw(
    epw_paths=epw_file,
    fwg_jar_path=jar_path,
    output_dir='./custom_output',
    fwg_show_tool_output=True,
    fwg_gcms=['CanESM5', 'MIROC6'], # Usar solo dos GCMs
    fwg_interpolation_method_id=2  # Usar el método "nearest point"
)

print("Successfully created files:")
for f in created_files_custom:
    print(f)