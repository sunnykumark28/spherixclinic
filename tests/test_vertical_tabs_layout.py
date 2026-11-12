import re
import pytest
from spherix.models.user import Doctor, Hospital
from spherix.services.database import TEMP_DATA

def test_doctor_detail_vertical_tabs_left_sidebar(client):
    """
    Verify that the doctor details page renders all 14 tabs in a vertical navigation sidebar
    positioned on the left side.
    """
    doc_id = 'DOC-VERT-TEST-001'
    doc = Doctor(
        doc_id,
        'Rohan',
        'Kapoor',
        'rohan.kapoor@example.com',
        'Password123!',
        'Cardiology',
        specialization='Interventional Cardiology',
        consultation_fee=1200.0,
        publishing_status='published',
        is_verified=True,
        is_approved=True,
        is_hidden=False,
        is_blocked=False
    )
    TEMP_DATA['doctors'][doc_id] = doc

    res = client.get(f'/doctor/{doc_id}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify vertical tabs sidebar exists on the left
    assert 'lg:col-span-3' in html
    assert '<aside' in html

    # Verify all 14 vertical buttons
    expected_tabs = [
        "1. Overview",
        "2. About Doctor",
        "3. Qualifications",
        "4. Experience",
        "5. Specializations",
        "6. Conditions Treated",
        "7. Treatments",
        "8. Hospital &amp; Clinics",
        "9. Consultation Fees",
        "10. Availability",
        "11. Reviews &amp; Ratings",
        "12. Achievements",
        "13. Gallery",
        "14. FAQs"
    ]
    for tab_title in expected_tabs:
        assert tab_title in html, f"Tab '{tab_title}' missing in doctor details"

    assert 'nav-tab-vertical' in html
    # Count occurrence of nav-tab-vertical
    assert html.count('nav-tab-vertical') >= 14

    # Verify mobile selector exists
    assert 'x-model="activeTab"' in html


def test_hospital_detail_vertical_tabs_left_sidebar(client):
    """
    Verify that the hospital details page renders all 13 tabs in a vertical navigation sidebar
    positioned on the left side.
    """
    hosp_id = 'HOSP-VERT-TEST-001'
    hosp = Hospital(
        hosp_id,
        'Apex International Medical Institute',
        'admin@apexinstitute.com',
        'Password123!',
        address='Plot 45 Medical Boulevard',
        city='Mumbai',
        state='Maharashtra',
        country='India',
        publishing_status='published',
        is_publicly_visible=True
    )
    TEMP_DATA['hospitals'][hosp_id] = hosp

    res = client.get(f'/hospital/{hosp_id}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify vertical tabs sidebar exists with lg:col-span-3
    assert '<aside class="lg:col-span-3">' in html

    # Verify all 13 vertical links
    expected_hospital_tabs = [
        "1. About",
        "2. Bed Availability",
        "3. Rate Card",
        "4. Specialists",
        "5. Facilities &amp; Tech",
        "6. Diagnostics &amp; Labs",
        "7. Pharmacy &amp; Blood",
        "8. Cashless TPAs",
        "9. Accreditations",
        "10. Visiting &amp; Support",
        "11. FAQs",
        "12. Gallery",
        "13. Contact &amp; Map"
    ]
    for tab_title in expected_hospital_tabs:
        assert tab_title in html, f"Hospital tab '{tab_title}' missing in vertical tabs"

    assert 'hospital-nav-vertical-link' in html
    assert html.count('hospital-nav-vertical-link') >= 13

    # Verify mobile selector exists
    assert 'x-model="activeSection"' in html


def test_hospital_detail_tabs_show_only_active_section(client):
    """
    Verify that each of the 13 hospital sections is gated by x-show so clicking a tab
    or loading #beds displays ONLY that section and not all other sections when scrolling.
    """
    hosp_id = 'HOSP-VERT-TEST-002'
    hosp = Hospital(
        hosp_id,
        'Metro Global Hospital',
        'admin@metroglobal.com',
        'Password123!',
        address='100 Healthcare Avenue',
        city='Delhi',
        state='Delhi',
        country='India',
        publishing_status='published',
        is_publicly_visible=True
    )
    TEMP_DATA['hospitals'][hosp_id] = hosp

    res = client.get(f'/hospital/{hosp_id}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify each section has x-show scoped to its section ID
    section_ids = [
        'about', 'beds', 'rates', 'doctors', 'facilities',
        'diagnostics', 'services', 'insurance', 'accreditations',
        'visiting', 'faqs', 'gallery', 'contact'
    ]
    for sec_id in section_ids:
        expected_x_show = f'x-show="activeSection === \'{sec_id}\' || activeSection === \'all\'"'
        assert expected_x_show in html, f"Section '{sec_id}' missing {expected_x_show}"
        assert f'id="{sec_id}"' in html

    # Verify switchSection method exists and updates hash/scroll
    assert 'switchSection(sec)' in html
    assert 'switchSection(\'beds\')' in html

    # Verify hash-based initialization in x-data
    assert 'window.location.hash' in html
    assert '[x-cloak]' in html
