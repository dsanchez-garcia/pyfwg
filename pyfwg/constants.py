# pyfwg/constants.py

# --- Global Tool Constants ---
GLOBAL_SCENARIOS = ['ssp126', 'ssp245', 'ssp370', 'ssp585']
DEFAULT_GLOBAL_GCMS = {
    'BCC_CSM2_MR', 'CanESM5', 'CanESM5_1', 'CanESM5_CanOE', 'CAS_ESM2_0',
    'CMCC_ESM2', 'CNRM_CM6_1', 'CNRM_CM6_1_HR', 'CNRM_ESM2_1', 'EC_Earth3',
    'EC_Earth3_Veg', 'EC_Earth3_Veg_LR', 'FGOALS_g3', 'GFDL_ESM4',
    'GISS_E2_1_G', 'GISS_E2_1_H', 'GISS_E2_2_G', 'IPSL_CM6A_LR',
    'MIROC_ES2H', 'MIROC_ES2L', 'MIROC6', 'MRI_ESM2_0', 'UKESM1_0_LL'
}

# --- Europe Tool Constants ---
EUROPE_SCENARIOS = ['rcp26', 'rcp45', 'rcp85']
DEFAULT_EUROPE_RCMS = {
    'ICHEC_EC_EARTH_SMHI_RCA4', 'CNRM_CERFACS_CNRM_CM5_CNRM_ALADIN63',
    'MOHC_HadGEM2_ES_DMI_HIRHAM5', 'NCC_NorESM1_M_SMHI_RCA4',
    'ICHEC_EC_EARTH_DMI_HIRHAM5', 'MOHC_HadGEM2_ES_SMHI_RCA4',
    'MPI_M_MPI_ESM_LR_SMHI_RCA4'
}

# --- Common Constants ---
ALL_POSSIBLE_YEARS = [2050, 2080]