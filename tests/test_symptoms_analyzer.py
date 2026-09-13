import pytest
from symptoms_analyzer import SymptomAnalyzer

@pytest.fixture
def analyzer():
    return SymptomAnalyzer()

def test_symptom_analyzer_init(analyzer):
    """Test analyzer initializes successfully with knowledge base."""
    assert analyzer is not None
    assert isinstance(analyzer.knowledge_base, dict)

def test_tokenize(analyzer):
    """Test text tokenization removes stop words and non-alphanumeric chars."""
    tokens = analyzer._tokenize("I have a severe headache and high fever!")
    assert "severe" in tokens
    assert "headache" in tokens
    assert "fever" in tokens
    assert "i" not in tokens
    assert "a" not in tokens
    assert "and" not in tokens

def test_analyze_common_symptoms(analyzer):
    """Test analysis returns structured diagnostic results."""
    res = analyzer.analyze("headache fever nausea", age=30, gender="male")
    assert isinstance(res, dict)
    assert "all_matches" in res or "analysis" in res or "confidence_level" in res
    if "analysis" in res:
        assert "primary_condition" in res["analysis"]
        assert "medical_category" in res["analysis"]

def test_empty_symptom_handling(analyzer):
    """Test analyzer handles blank string gracefully."""
    res = analyzer.analyze("")
    assert isinstance(res, dict)
