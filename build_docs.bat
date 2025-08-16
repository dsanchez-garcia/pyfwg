@echo off
REM build_docs.bat
REM This script automates the generation of the pyfwg documentation.
REM It should be executed from the project root.

ECHO --- [Step 1 of 3] Cleaning previous builds...
REM Delete the contents of the output folder to ensure a clean build.
REM The /Q flag executes the deletion without asking for confirmation.
IF EXIST docs\build rmdir /s /q docs\build

ECHO.
ECHO --- [Step 2 of 3] Generating API .rst files with sphinx-apidoc...
REM Execute sphinx-apidoc to generate/update .rst files from the source code.
REM -o docs\source\api: Output directory for the .rst files.
REM pyfwg: Path to the package to be documented.
REM --force: Overwrite existing files.
sphinx-apidoc --force -o docs\source\api pyfwg

ECHO.
ECHO --- [Step 3 of 3] Building the HTML documentation with Sphinx...
REM Change to the 'docs' directory and run the 'make html' command.
cd docs
call make.bat html
cd ..

ECHO.
ECHO --- Process complete ---
ECHO The HTML documentation has been generated at: docs\build\html\index.html
PAUSE