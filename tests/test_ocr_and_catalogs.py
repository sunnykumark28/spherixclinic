import pytest
from prescription_ocr import parse_medicines_with_groq, extract_text_from_image
from disease_catalog import ALL_DISEASES, DISEASES_BY_NAME
from ayurveda_catalog import ALL_AYUR_DISEASES, AYUR_DISEASES_BY_ID
from medicine_catalog import ALL_MEDICINES, MEDICINES_BY_ID
from lab_catalog import HEALTH_PACKAGES, INDIVIDUAL_TESTS

def test_disease_catalog_loaded():
    """Verify disease catalog contains structured disease entries."""
    assert isinstance(ALL_DISEASES, list)
    assert len(ALL_DISEASES) > 0

def test_ayurveda_catalog_loaded():
    """Verify ayurvedic catalog contains remedy profiles."""
    assert isinstance(ALL_AYUR_DISEASES, list)
    assert len(ALL_AYUR_DISEASES) > 0

def test_medicine_catalog_loaded():
    """Verify medicine catalog contains medication entries."""
    assert isinstance(ALL_MEDICINES, list)
    assert len(ALL_MEDICINES) > 0

def test_lab_catalog_loaded():
    """Verify lab tests catalog contains diagnostic health packages and tests."""
    assert isinstance(HEALTH_PACKAGES, list)
    assert len(HEALTH_PACKAGES) > 0
    assert isinstance(INDIVIDUAL_TESTS, list)
    assert len(INDIVIDUAL_TESTS) > 0

def test_ocr_extract_text_empty_path():
    """Verify OCR handles invalid or empty path gracefully without throwing."""
    res = extract_text_from_image("")
    assert res == ""
    res_none = extract_text_from_image("/path/to/nonexistent/file.png")
    assert res_none == ""

def test_ocr_parse_medicines_fallback():
    """Verify medicine parsing regex fallback when no API key is provided."""
    raw_ocr = "Rx: Paracetamol 500mg, Amoxicillin 250mg twice daily for 5 days. Dr. Smith."
    meds = parse_medicines_with_groq(raw_ocr)
    assert isinstance(meds, list)
