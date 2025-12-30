# pyfwg Tests

This directory contains the testing suite and utility scripts for `pyfwg`.

## Running Tests

To run the complete test suite, use the following command from the project root:

```bash
python -m tests.run_complete_suite
```

Alternatively:

```bash
python tests/run_complete_suite.py
```

(Ensure the project root is in your `PYTHONPATH`).

## Contents

- `run_complete_suite.py`: A comprehensive suite that verifies utilities, workflows, API, and iterators.
- `test_*.py`: Specific tests focusing on individual features or versions.
- `using_*.py`: Example scripts and manual validation tests.
- `verify_fwg_refactor.py`: Script to verify the library's refactoring and structure.
- `examples/`: Directory containing usage examples for different FWG versions.
