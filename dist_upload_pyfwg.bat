@echo off
REM dist_upload_pyfwg.bat
REM This script uploads the package distributions to PyPI.
REM It assumes that the .pypirc file is correctly configured.

ECHO --- [Step 1 of 2] Verifying that the 'dist' directory exists...
IF NOT EXIST dist (
    ECHO ERROR: The 'dist' directory was not found.
    ECHO Please build the package first by running: python -m build
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO --- [Step 2 of 2] Uploading distributions to PyPI using the 'pyfwg' repository configuration...
twine upload --repository pyfwg dist/*

ECHO.
ECHO --- Process complete ---
PAUSE