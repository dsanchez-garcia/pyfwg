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

# --- CORDEX-CMIP5 Regional Distributions (FWG Engine) ---
# Regional distributions released with the shared FWG Engine (v1.x). Keys are
# the CORDEX domain identifiers, which also appear in the JAR filenames
# (e.g., 'FutureWeatherGenerator-CORDEX-CMIP5-North-America-NAM-44-v1.2.0.jar').
# Each GCM-RCM product is written as '<driving GCM>_<regional model>'; the
# engine treats '_' and '-' as equivalent in model identifiers.
CORDEX_REGIONS = {
    'EUR-11': {
        'name': 'Europe',
        'scenarios': ['rcp26', 'rcp45', 'rcp85'],
        'rcm_pairs': set(DEFAULT_EUROPE_RCMS),
    },
    'MNA-22': {
        'name': 'Middle East and North Africa',
        'scenarios': ['rcp85'],
        'rcm_pairs': {'ICHEC_EC_EARTH_SMHI_RCA4', 'NOAA_GFDL_GFDL_ESM2M_SMHI_RCA4'},
    },
    'AFR-22': {
        'name': 'Africa',
        'scenarios': ['rcp26', 'rcp85'],
        'rcm_pairs': {
            'MOHC_HadGEM2_ES_CLMcom_KIT_CCLM5_0_15', 'MPI_M_MPI_ESM_LR_CLMcom_KIT_CCLM5_0_15',
            'NCC_NorESM1_M_CLMcom_KIT_CCLM5_0_15'
        },
    },
    'NAM-44': {
        'name': 'North America',
        'scenarios': ['rcp45', 'rcp85'],
        'rcm_pairs': {'ICHEC_EC_EARTH_DMI_HIRHAM5', 'CCCma_CanESM2_SMHI_RCA4'},
    },
    'CAM-44': {
        'name': 'Central America',
        'scenarios': ['rcp26', 'rcp45', 'rcp85'],
        'rcm_pairs': {
            'ICHEC_EC_EARTH_SMHI_RCA4', 'MPI_M_MPI_ESM_LR_SMHI_RCA4', 'MOHC_HadGEM2_ES_SMHI_RCA4'
        },
    },
    'SAM-44': {
        'name': 'South America',
        'scenarios': ['rcp26', 'rcp45', 'rcp85'],
        'rcm_pairs': {
            'ICHEC_EC_EARTH_SMHI_RCA4', 'NCC_NorESM1_M_SMHI_RCA4', 'MIROC_MIROC5_SMHI_RCA4',
            'MPI_M_MPI_ESM_LR_SMHI_RCA4', 'MOHC_HadGEM2_ES_SMHI_RCA4'
        },
    },
    'WAS-22': {
        'name': 'West & South Asia',
        'scenarios': ['rcp26', 'rcp85'],
        'rcm_pairs': {
            'MPI_M_MPI_ESM_LR_CLMcom_ETH_COSMO_crCLIM_v1_1', 'NCC_NorESM1_M_CLMcom_ETH_COSMO_crCLIM_v1_1'
        },
    },
    'SEA-22': {
        'name': 'Southeast Asia',
        'scenarios': ['rcp45', 'rcp85'],
        'rcm_pairs': {'MOHC_HadGEM2_ES_SMHI_RCA4', 'CNRM_CERFACS_CNRM_CM5_SMHI_RCA4'},
    },
    'AUS-22': {
        'name': 'Australasia',
        'scenarios': ['rcp26', 'rcp85'],
        'rcm_pairs': {
            'MOHC_HadGEM2_ES_CLMcom_HZG_CCLM5_0_15', 'MPI_M_MPI_ESM_LR_CLMcom_HZG_CCLM5_0_15',
            'NCC_NorESM1_M_CLMcom_HZG_CCLM5_0_15'
        },
    },
}
CORDEX_SCENARIOS = ['rcp26', 'rcp45', 'rcp85']
DEFAULT_CORDEX_RCMS = set().union(*(region['rcm_pairs'] for region in CORDEX_REGIONS.values()))

# --- Common Constants ---
ALL_POSSIBLE_YEARS = [2050, 2080]

# --- Command-Line Interface Styles ---
# Global v3.x / Europe v1.x: positional arguments (java -cp <jar> <package>.Morph ...).
FWG_CLI_POSITIONAL = 'positional'
# Global v4.x / Europe v2.x: key-value arguments (java -jar <jar> -key=value ...).
FWG_CLI_KEY_VALUE = 'key_value'
# FWG Engine distributions: Global v5+, Europe v3+ and the CORDEX regional
# distributions (java -jar <jar> -g -key=value ...).
FWG_CLI_ENGINE = 'engine'

# --- FWG Engine Option Values ---
# Integer IDs follow the numbering used internally by the engine.
ENGINE_INTERPOLATION_METHODS = {0: 'IDW', 1: 'BI', 2: 'AVG4P', 3: 'NP', 4: 'SCI', 5: 'SGBI', 6: 'STBI'}
ENGINE_DECOMPOSITION_METHODS = [
    'MULTIMODEL_CONSTRAINED_ENSEMBLE', 'ORGILL_HOLLANDS_1977', 'ERBS_1982', 'MAXWELL_DISC_1987',
    'REINDL_REDUCED_1990', 'BOLAND_LOGISTIC_2008', 'RIDLEY_BOLAND_LAURET_2010',
    'ENGERER_2015_METHOD_2', 'PAULESCU_BLAGA_2019'
]
ENGINE_ILLUMINANCE_METHODS = ['PEREZ_1990', 'SOURCE_CALIBRATED_LUMINOUS_EFFICACY']
ENGINE_INFRARED_METHODS = ['FWG_CURRENT', 'CLARK_ALLEN_WALTON']
ENGINE_MORPHING_METHODS = ['CLASSIC_MONTHLY', 'DISTRIBUTION_AWARE']
ENGINE_UNCERTAINTY_VARIANTS = [
    'CENTRAL', 'PLUS_ONE_SIGMA', 'MINUS_ONE_SIGMA', 'WARM_DRY', 'WARM_HUMID', 'HIGH_SOLAR', 'LOW_SOLAR'
]
ENGINE_OUTPUT_PROFILES = ['MINIMAL', 'STANDARD', 'FULL', 'CUSTOM']
