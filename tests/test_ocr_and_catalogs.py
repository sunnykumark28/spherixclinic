import pytest
from prescription_ocr import parse_medicines_with_groq, extract_text_from_image
from disease_catalog import ALL_DISEASES, DISEASES_BY_NAME, load_all_diseases
from ayurveda_catalog import ALL_AYUR_DISEASES, AYUR_DISEASES_BY_ID
from medicine_catalog import ALL_MEDICINES, MEDICINES_BY_ID, load_all_medicines

def test_disease_catalog_loaded():
    """Verify disease catalog contains structured disease entries."""
    if not ALL_DISEASES:
        load_all_diseases()
    assert isinstance(ALL_DISEASES, list)
    assert len(ALL_DISEASES) > 0

def test_ayurveda_catalog_loaded():
    """Verify ayurvedic catalog contains remedy profiles."""
    assert isinstance(ALL_AYUR_DISEASES, list)
    assert len(ALL_AYUR_DISEASES) > 0

def test_medicine_catalog_loaded():
    """Verify medicine catalog contains medication entries."""
    meds = load_all_medicines()
    assert isinstance(meds, list)
    assert len(meds) > 0

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
