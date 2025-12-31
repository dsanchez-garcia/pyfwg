@echo off
REM dist_upload_test.bat
REM This script uploads the package distributions to the TestPyPI repository.
REM It assumes that the .pypirc file is correctly configured.

ECHO --- [Step 1 of 2] Verifying that the 'dist' directory exists...
IF NOT EXIST dist (
    ECHO ERROR: The 'dist' directory was not found.
    ECHO Please, build the package first by running: dist_build_pyfwg.bat
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO --- [Step 2 of 2] Uploading distributions to TestPyPI...
twine upload --repository testpypi dist/*

ECHO.
ECHO --- Process completed ---
ECHO Review your package at: https://test.pypi.org/project/pyfwg/
PAUSE
