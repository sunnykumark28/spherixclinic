import pytest
import json

def test_health_check(client):
    """Test /api/v1/health returns 200 and healthy status."""
    response = client.get('/api/v1/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "healthy"
    assert "subsystems" in data

def test_system_status(client):
    """Test /api/v1/status returns operational metrics."""
    response = client.get('/api/v1/status')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "operational"
    assert "metrics" in data

def test_analyze_symptoms_valid(client):
    """Test /api/v1/diagnostics/analyze-symptoms with valid symptom input."""
    payload = {
        "symptoms": "headache, mild fever, fatigue",
        "age": 28,
        "gender": "male"
    }
    response = client.post('/api/v1/diagnostics/analyze-symptoms',
                           data=json.dumps(payload),
                           content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] in ["success", "partial_success"]

def test_analyze_symptoms_empty(client):
    """Test /api/v1/diagnostics/analyze-symptoms with empty body returns 400."""
    response = client.post('/api/v1/diagnostics/analyze-symptoms',
                           data=json.dumps({}),
                           content_type='application/json')
    assert response.status_code == 400

def test_get_medicines(client):
    """Test /api/v1/medicines returns list of medicines."""
    response = client.get('/api/v1/medicines?limit=5')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "results" in data
    assert isinstance(data["results"], list)

def test_get_hospitals_and_beds(client):
    """Test /api/v1/hospitals and /api/v1/beds telemetry."""
    hosp_resp = client.get('/api/v1/hospitals')
    assert hosp_resp.status_code == 200
    hosp_data = json.loads(hosp_resp.data)
    assert "hospitals" in hosp_data

    beds_resp = client.get('/api/v1/beds')
    assert beds_resp.status_code == 200
    beds_data = json.loads(beds_resp.data)
    assert "facilities" in beds_data

def test_get_blood_stock(client):
    """Test /api/v1/blood-stock returns blood groups."""
    response = client.get('/api/v1/blood-stock')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "blood_stock" in data
    assert "A+" in data["blood_stock"]

def test_get_doctors(client):
    """Test /api/v1/doctors returns doctor directory."""
    response = client.get('/api/v1/doctors')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "doctors" in data

def test_clinical_soap_notes(client):
    """Test /api/v1/clinical/soap-notes parses clinical text."""
    payload = {
        "text": "Patient feels severe headache and nausea for 3 days. BP 120/80, pulse 72 normal. Suspected acute migraine. Prescribe rest and hydration."
    }
    response = client.post('/api/v1/clinical/soap-notes',
                           data=json.dumps(payload),
                           content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "success"
    assert "soap_notes" in data
    assert "subjective" in data["soap_notes"]
    assert "objective" in data["soap_notes"]
    assert "assessment" in data["soap_notes"]
    assert "plan" in data["soap_notes"]
