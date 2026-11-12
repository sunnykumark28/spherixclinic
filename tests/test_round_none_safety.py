import pytest
from flask import render_template_string
from spherix.models.user import Doctor, Hospital
from spherix.services.database import TEMP_DATA

def test_safe_round_function_and_filter(app):
    """Verifies that safe_round and Jinja round filter handle None gracefully without TypeError."""
    with app.test_request_context():
        # Test Jinja filter with None and empty values
        t1 = render_template_string("{{ val | round }}", val=None)
        assert t1 == "0"

        t2 = render_template_string("{{ val | round(2) }}", val=None)
        assert t2 == "0.0"

        t3 = render_template_string("{{ val | round }}", val="")
        assert t3 == "0"

        t4 = render_template_string("{{ val | round(1) }}", val=4.567)
        assert t4 == "4.6"

        t5 = render_template_string("{{ val | round(0, 'ceil') }}", val=3.2)
        assert t5 == "4"

        t6 = render_template_string("{{ val | round(0, 'floor') }}", val=3.8)
        assert t6 == "3"

        # Test Jinja global round() function directly
        t7 = render_template_string("{{ round(val) }}", val=None)
        assert t7 == "0"

        t8 = render_template_string("{{ round(val, 2) }}", val=None)
        assert t8 == "0.0"

def test_home_page_renders_with_doctor_having_none_rating(client):
    """Verifies home page renders without TypeError when doctor has zero reviews and None rating."""
    doc_id = 'DOC/2026/TEST_UNRATED'
    test_doc = Doctor(
        id=doc_id,
        name="Dr. Unrated Doctor",
        first_name="Unrated",
        last_name="Doctor",
        email="unrated@spherixclinic.com",
        password="password123",
        phone="9999999999",
        specialization="Cardiology",
        department="Cardiology",
        hospital_name="Apex Care Hospital",
        experience="5",
        license_number="MED-12345",
        consultation_fee=500.0,
        publishing_status="published",
        is_verified=True
    )
    TEMP_DATA['doctors'][doc_id] = test_doc

    assert test_doc.reviews == []
    assert test_doc.average_rating is None

    resp = client.get('/')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Unrated" in html
    assert "Dedicated medical consultant" in html or "Cardiology" in html

def test_hospital_dashboard_revenue_round_none_safety(client):
    """Verifies hospital dashboard template snippets render safely even when revenues and stats are None."""
    with client.application.test_request_context():
        hosp = Hospital(
            id='HPT-TEST-001',
            name='Test Metro Hospital',
            email='test@metro.com',
            phone='9876543210',
            address='123 Healthcare Blvd',
            total_beds=100,
            available_beds=None, # None available beds
            consultation_fee=None,
            password='password123'
        )
        rendered = render_template_string("""
            "total_appointment_revenue": {{ (total_appointment_revenue or 0) | round(2) }},
            "total_bed_revenue": {{ (total_bed_revenue or 0) | round(2) }},
            "total_revenue": {{ (total_revenue or 0) | round(2) }},
            "bed_occupancy": {% if hosp.total_beds and hosp.total_beds > 0 %}{{ (((hosp.total_beds - (hosp.available_beds or 0)) / hosp.total_beds) * 100)|round(0) }}%{% else %}0%{% endif %}
        """, total_appointment_revenue=None, total_bed_revenue=None, total_revenue=None, hosp=hosp)

        assert '"total_appointment_revenue": 0.0' in rendered
        assert '"total_bed_revenue": 0.0' in rendered
        assert '"total_revenue": 0.0' in rendered
        assert '"bed_occupancy": 100%' in rendered
