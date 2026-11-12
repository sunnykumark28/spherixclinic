import pytest
from spherix.models.user import Hospital
from spherix.services.database import TEMP_DATA

def test_hospital_5_actions_slide_over_drawers(client):
    """
    Test that on the hospital detail page:
    1. 'Request Inpatient Bed', 'Book Doctor Consultation', 'Medical Travel & Visa',
       'Blood Reserves', and 'Organ Donors' are all implemented as right-hand slide-over sidebar drawers.
    2. Header, navbar, footer, and floating docks are hidden when any drawer is active via CSS rules.
    3. All 5 drawer controllers, openers, closers, and body-state synchronizers are present.
    """
    hosp_id = 'HOSP_DRAWER_TEST_01'
    hosp = Hospital(
        hosp_id,
        'Metro Health Multi-Speciality Hospital',
        'contact@metrohealth.com',
        'Password123!',
        address='12 Hospital Road',
        city='New Delhi',
        state='Delhi',
        country='India',
        publishing_status='published',
        is_publicly_visible=True
    )
    TEMP_DATA['hospitals'][hosp_id] = hosp

    res = client.get(f'/hospital/{hosp_id}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # 1. Action Buttons trigger drawer openers
    assert 'onclick="openBedDrawer()"' in html
    assert 'onclick="openApptDrawer()"' in html
    assert 'onclick="openTravelDrawer()"' in html
    assert 'onclick="openBloodBankDrawer()"' in html
    assert 'onclick="openOrganDonorDrawer()"' in html

    # 2. Bed selection buttons call openBedDrawer with parameter
    assert "onclick=\"openBedDrawer('General')\"" in html
    assert "onclick=\"openBedDrawer('Private')\"" in html
    assert "onclick=\"openBedDrawer('ICU')\"" in html

    # 3. Slide-over sidebar drawers markup
    # Bed Drawer (replaces centered modal)
    assert 'id="bookBedModal"' in html
    assert 'id="bedDrawerBackdrop"' in html
    assert 'id="bedDrawerPanel"' in html
    assert 'onclick="closeBedDrawer()"' in html
    assert 'Request Inpatient Bed' in html

    # Appointment Drawer (replaces centered modal)
    assert 'id="bookApptModal"' in html
    assert 'id="apptDrawerBackdrop"' in html
    assert 'id="apptDrawerPanel"' in html
    assert 'onclick="closeApptDrawer()"' in html
    assert 'Book Doctor Consultation' in html

    # Travel & Visa Drawer
    assert 'id="travelDrawerContainer"' in html
    assert 'id="travelDrawerBackdrop"' in html
    assert 'id="travelDrawerPanel"' in html
    assert 'onclick="closeTravelDrawer()"' in html

    # Blood Reserves Drawer
    assert 'id="bloodBankDrawerContainer"' in html
    assert 'id="bloodBankDrawerBackdrop"' in html
    assert 'id="bloodBankDrawerPanel"' in html
    assert 'onclick="closeBloodBankDrawer()"' in html

    # Organ Donors Drawer
    assert 'id="organDonorDrawerContainer"' in html
    assert 'id="organDonorDrawerBackdrop"' in html
    assert 'id="organDonorDrawerPanel"' in html
    assert 'onclick="closeOrganDonorDrawer()"' in html

    # 4. Right-hand slide-over classes on drawer panels
    assert 'fixed right-0 top-0 bottom-0 h-full w-full max-w-xl' in html
    assert 'translate-x-full' in html

    # 5. CSS rules hiding header, navbar, footer, and docks when sidebar-drawer-open or hospital-drawer-open
    assert 'body.sidebar-drawer-open #top-utility-bar' in html
    assert 'body.sidebar-drawer-open header' in html
    assert 'body.sidebar-drawer-open #main-navbar' in html
    assert 'body.sidebar-drawer-open footer' in html
    assert 'body.sidebar-drawer-open #main-footer' in html
    assert 'body.hospital-drawer-open #main-navbar' in html
    assert 'body.hospital-drawer-open #main-footer' in html

    # 6. JavaScript functions
    assert 'window.openBedDrawer = function' in html
    assert 'window.closeBedDrawer = function' in html
    assert 'window.openApptDrawer = function' in html
    assert 'window.closeApptDrawer = function' in html
    assert 'window.openTravelDrawer = function' in html
    assert 'window.closeTravelDrawer = function' in html
    assert 'window.openBloodBankDrawer = function' in html
    assert 'window.closeBloodBankDrawer = function' in html
    assert 'window.openOrganDonorDrawer = function' in html
    assert 'window.closeOrganDonorDrawer = function' in html
    assert 'function checkAndRestoreBodyState()' in html


def test_doctor_consultation_departments_and_doctor_sync(client):
    """
    Test that when opening Book Doctor Consultation:
    1. The department dropdown shows all available departments in the hospital.
    2. The doctor dropdown lists specialists with their data-dept.
    3. The dynamic doctor card is rendered for previewing doctor details.
    4. initApptDepartmentDoctorSync and syncApptDepartmentAndDoctor functions are defined
       to bi-directionally sync department and doctor choice.
    """
    from spherix.models.user import Doctor

    hosp_id = 'HOSP_DOC_SYNC_TEST_02'
    hosp = Hospital(
        hosp_id,
        'City Care Super Specialty Hospital',
        'admin@citycare.com',
        'Password123!',
        address='55 Healthcare Park',
        city='Bangalore',
        state='Karnataka',
        country='India',
        publishing_status='published',
        is_publicly_visible=True
    )
    TEMP_DATA['hospitals'][hosp_id] = hosp

    doc1 = Doctor(
        'DOC_SYNC_01',
        'Aarav',
        'Sharma',
        'aarav.sharma@citycare.com',
        'Password123!',
        'Cardiology',
        specialization='Interventional Cardiology',
        consultation_fee=1500.0,
        hospital_id=hosp_id,
        publishing_status='published',
        is_verified=True,
        is_approved=True
    )
    doc2 = Doctor(
        'DOC_SYNC_02',
        'Priya',
        'Nair',
        'priya.nair@citycare.com',
        'Password123!',
        'Neurology',
        specialization='Neurosurgeon',
        consultation_fee=2000.0,
        hospital_id=hosp_id,
        publishing_status='published',
        is_verified=True,
        is_approved=True
    )
    doc3 = Doctor(
        'DOC_SYNC_03',
        'Vikram',
        'Mehta',
        'vikram.mehta@citycare.com',
        'Password123!',
        'Orthopedics',
        specialization='Joint Replacement Specialist',
        consultation_fee=1200.0,
        hospital_id=hosp_id,
        publishing_status='published',
        is_verified=True,
        is_approved=True
    )
    TEMP_DATA['doctors']['DOC_SYNC_01'] = doc1
    TEMP_DATA['doctors']['DOC_SYNC_02'] = doc2
    TEMP_DATA['doctors']['DOC_SYNC_03'] = doc3

    res = client.get(f'/hospital/{hosp_id}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Department selector has option to choose and displays all departments
    assert 'id="apptDepartment"' in html
    assert 'Choose a Department (All Departments Available)' in html
    assert '<option value="Cardiology">Cardiology</option>' in html
    assert '<option value="Neurology">Neurology</option>' in html
    assert '<option value="Orthopedics">Orthopedics</option>' in html

    # Doctor selector contains all doctors with data-dept and data-name
    assert 'id="apptDoctor"' in html
    assert 'data-dept="Cardiology"' in html
    assert 'Dr. Aarav Sharma' in html
    assert 'data-dept="Neurology"' in html
    assert 'Dr. Priya Nair' in html
    assert 'data-dept="Orthopedics"' in html
    assert 'Dr. Vikram Mehta' in html

    # Selected doctor card is present
    assert 'id="selectedDoctorCard"' in html
    assert 'id="selectedDocName"' in html
    assert 'id="selectedDocDept"' in html
    assert 'id="selectedDocSpec"' in html
    assert 'id="selectedDocFee"' in html

    # Bi-directional sync functions and controllers are in script
    assert 'initApptDepartmentDoctorSync' in html
    assert 'window.syncApptDepartmentAndDoctor = function' in html
    assert "onclick=\"openApptDrawer('DOC_SYNC_01', 'Cardiology')\"" in html
    assert "onclick=\"openApptDrawer('DOC_SYNC_02', 'Neurology')\"" in html
    assert "onclick=\"openApptDrawer('DOC_SYNC_03', 'Orthopedics')\"" in html

    assert 'function checkAndRestoreBodyState()' in html
