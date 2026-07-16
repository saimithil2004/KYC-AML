"""
Country Risk Agent — Country Normalizer
========================================

Maps ISO 3166-1 Alpha-2, Alpha-3, and common country names/aliases to standardized names.
"""

from typing import Dict, Optional

# Mapping of lowercase aliases, codes, and names to standard English country names.
_COUNTRY_MAP: Dict[str, str] = {
    # United Kingdom
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "gbr": "United Kingdom",
    "united kingdom": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "northern ireland": "United Kingdom",

    # United States
    "us": "United States",
    "usa": "United States",
    "united states": "United States",
    "united states of america": "United States",

    # Germany
    "de": "Germany",
    "deu": "Germany",
    "germany": "Germany",
    "deutschland": "Germany",

    # France
    "fr": "France",
    "fra": "France",
    "france": "France",

    # Iran
    "ir": "Iran",
    "irn": "Iran",
    "iran": "Iran",
    "islamic republic of iran": "Iran",

    # North Korea
    "kp": "North Korea",
    "prk": "North Korea",
    "north korea": "North Korea",
    "democratic people's republic of korea": "North Korea",
    "dprk": "North Korea",

    # Russia
    "ru": "Russia",
    "rus": "Russia",
    "russia": "Russia",
    "russian federation": "Russia",

    # Syria
    "sy": "Syria",
    "syr": "Syria",
    "syria": "Syria",
    "syrian arab republic": "Syria",

    # Cayman Islands
    "ky": "Cayman Islands",
    "cym": "Cayman Islands",
    "cayman islands": "Cayman Islands",
    "cayman": "Cayman Islands",

    # Panama
    "pa": "Panama",
    "pan": "Panama",
    "panama": "Panama",

    # Singapore
    "sg": "Singapore",
    "sgp": "Singapore",
    "singapore": "Singapore",

    # Australia
    "au": "Australia",
    "aus": "Australia",
    "australia": "Australia",

    # Spain
    "es": "Spain",
    "esp": "Spain",
    "spain": "Spain",
    "espana": "Spain",

    # Belgium
    "be": "Belgium",
    "bel": "Belgium",
    "belgium": "Belgium",

    # Switzerland
    "ch": "Switzerland",
    "che": "Switzerland",
    "switzerland": "Switzerland",

    # Canada
    "ca": "Canada",
    "can": "Canada",
    "canada": "Canada",

    # Japan
    "jp": "Japan",
    "jpn": "Japan",
    "japan": "Japan",

    # China
    "cn": "China",
    "chn": "China",
    "china": "China",
    "people's republic of china": "China",
}


def normalize_country(country: Optional[str]) -> Optional[str]:
    """
    Standardizes country string or code into a canonical country name.
    Returns None if the country is not recognized in the mapping.
    """
    if not country:
        return None
    
    clean_val = str(country).strip().lower()
    
    # Check map
    if clean_val in _COUNTRY_MAP:
        return _COUNTRY_MAP[clean_val]

    # Return None for completely unknown codes/aliases to trigger warning CR008
    return None
