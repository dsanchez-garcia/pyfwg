
# tests/test_constants.py
"""
Tests for the constants defined in the pyfwg package.
This module verifies that the hardcoded lists of scenarios, models, and years
are correct, contain expected values, and have the right data types.
"""

import pytest
from pyfwg.constants import (
    GLOBAL_SCENARIOS,
    DEFAULT_GLOBAL_GCMS,
    EUROPE_SCENARIOS,
    DEFAULT_EUROPE_RCMS,
    ALL_POSSIBLE_YEARS,
    CORDEX_REGIONS,
    CORDEX_SCENARIOS,
    DEFAULT_CORDEX_RCMS,
    ENGINE_INTERPOLATION_METHODS
)

def test_global_constants():
    """Verify Global tool constants (SSPs and GCMs)."""
    # Check that we have the 4 standard SSP scenarios as a list
    assert isinstance(GLOBAL_SCENARIOS, list)
    assert set(GLOBAL_SCENARIOS) == {"ssp126", "ssp245", "ssp370", "ssp585"}
    
    # Check that the default GCM list is a set and contains expected model names
    assert isinstance(DEFAULT_GLOBAL_GCMS, set)
    assert "CanESM5" in DEFAULT_GLOBAL_GCMS
    assert "MIROC6" in DEFAULT_GLOBAL_GCMS

def test_europe_constants():
    """Verify Europe tool constants (RCPs and RCM-GCM pairs)."""
    # Check that we have the 3 standard RCP scenarios as a list
    assert isinstance(EUROPE_SCENARIOS, list)
    assert set(EUROPE_SCENARIOS) == {"rcp26", "rcp45", "rcp85"}
    
    # Check that the default RCM list is a set and contains correctly formatted pairs
    assert isinstance(DEFAULT_EUROPE_RCMS, set)
    # Example of a known pair
    assert "ICHEC_EC_EARTH_SMHI_RCA4" in DEFAULT_EUROPE_RCMS

def test_years_constant():
    """Verify the list of supported years for future projection."""
    # The tool supports these future years landmark
    assert list(ALL_POSSIBLE_YEARS) == [2050, 2080]

def test_cordex_constants():
    """Verify the CORDEX regional distributions released on the FWG Engine."""
    # Nine CORDEX-CMIP5 domains (including Europe EUR-11) are available
    assert set(CORDEX_REGIONS) == {
        "EUR-11", "MNA-22", "AFR-22", "NAM-44", "CAM-44", "SAM-44", "WAS-22", "SEA-22", "AUS-22"
    }
    for domain, region in CORDEX_REGIONS.items():
        # Each region only provides a subset of the RCP scenarios
        assert set(region["scenarios"]) <= set(CORDEX_SCENARIOS), domain
        assert region["rcm_pairs"] <= DEFAULT_CORDEX_RCMS, domain
    # Europe keeps the same GCM-RCM pairs as the Europe tool
    assert CORDEX_REGIONS["EUR-11"]["rcm_pairs"] == DEFAULT_EUROPE_RCMS
    # Middle East and North Africa only provides RCP8.5
    assert CORDEX_REGIONS["MNA-22"]["scenarios"] == ["rcp85"]

def test_engine_interpolation_methods():
    """Verify the interpolation IDs, which follow the numbering of the FWG Engine."""
    assert ENGINE_INTERPOLATION_METHODS[0] == "IDW"
    assert ENGINE_INTERPOLATION_METHODS[6] == "STBI"
