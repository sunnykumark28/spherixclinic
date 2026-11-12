import io
import os
import pytest
from PIL import Image
from spherix.models.user import Doctor
from spherix.services.database import TEMP_DATA

@pytest.fixture
def client():
    from spherix import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client

def test_doctor_dashboard_side_tabs_and_cover_ui_rendering(client):
    """Verifies that doctor dashboard renders the 9 side tabs layout, mobile selector, and cover upload controls."""
    doc_id = 'DOC-EDIT-TABS-001'
    doc = Doctor(
        doc_id,
        'Kavita',
        'Rao',
        'kavita.rao@example.com',
        'Password123!',
        'Cardiology',
        specialization='Clinical & Preventative Cardiology',
        medical_degrees='MBBS, MD',
        license_number='MCI-99881',
        consultation_fee=1200.0,
        publishing_status='published',
        is_verified=True,
        cover_image_url='https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=1600&q=80'
    )
    TEMP_DATA['doctors'][doc_id] = doc

    with client.session_transaction() as sess:
        sess['_user_id'] = str(doc_id)
        sess['user_role'] = 'doctor'
        sess['_fresh'] = True

    res = client.get('/doctor/dashboard')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # 1. Summary Card & Panoramic Cover Banner
    assert "doctorProfileSummaryCard" in html
    assert "Change Cover" in html
    assert "switchDoctorEditTab('media')" in html

    # 2. Edit Profile Card & Form
    assert "doctorProfileEditCard" in html
    assert 'id="doctorProfileForm"' in html
    assert 'name="action" value="update_profile"' in html

    # 3. Mobile Section Selector
    assert 'id="doctorEditMobileTabSelect"' in html
    assert 'switchDoctorEditTab(this.value)' in html

    # 4. Vertical Side Tabs (All 9 tabs present)
    assert 'data-tab="media"' in html
    assert 'data-tab="basic"' in html
    assert 'data-tab="qualifications"' in html
    assert 'data-tab="experience"' in html
    assert 'data-tab="specializations"' in html
    assert 'data-tab="location"' in html
    assert 'data-tab="appointments"' in html
    assert 'data-tab="gallery"' in html
    assert 'data-tab="bio"' in html

    # 5. Content Panes (All 9 panes present)
    assert 'id="doctor-edit-pane-media"' in html
    assert 'id="doctor-edit-pane-basic"' in html
    assert 'id="doctor-edit-pane-qualifications"' in html
    assert 'id="doctor-edit-pane-experience"' in html
    assert 'id="doctor-edit-pane-specializations"' in html
    assert 'id="doctor-edit-pane-location"' in html
    assert 'id="doctor-edit-pane-appointments"' in html
    assert 'id="doctor-edit-pane-gallery"' in html
    assert 'id="doctor-edit-pane-bio"' in html

    # 6. Panoramic Cover Banner Controls in Tab 1 (Media)
    assert 'id="doctorCoverPreviewImg"' in html
    assert 'id="doctorCoverFileInput"' in html
    assert 'name="cover_image"' in html
    assert 'id="doctorCoverUrlInput"' in html
    assert 'name="cover_image_url"' in html
    assert 'id="doctorRemoveCoverInput"' in html
    assert 'previewDoctorCoverFile(event)' in html
    assert 'removeDoctorCover()' in html

    # 7. JavaScript Tab & Cover Management Helpers
    assert 'function switchDoctorEditTab(tabKey)' in html
    assert 'function previewDoctorCoverFile(event)' in html
    assert 'function previewDoctorCoverUrl(url)' in html
    assert 'function removeDoctorCover()' in html

def test_doctor_profile_cover_url_update(client):
    """Verifies that submitting a direct cover image URL persists to the doctor model."""
    doc_id = 'DOC-EDIT-TABS-002'
    doc = Doctor(
        doc_id,
        'Rohan',
        'Mehta',
        'rohan.mehta@example.com',
        'Password123!',
        'Neurology',
        consultation_fee=1000.0,
        cover_image_url=''
    )
    TEMP_DATA['doctors'][doc_id] = doc

    with client.session_transaction() as sess:
        sess['_user_id'] = str(doc_id)
        sess['user_role'] = 'doctor'
        sess['_fresh'] = True

    new_cover_url = 'https://images.unsplash.com/photo-custom-cover-test'
    res = client.post('/doctor/dashboard', data={
        'action': 'update_profile',
        'first_name': 'Rohan',
        'last_name': 'Mehta',
        'email': 'rohan.mehta@example.com',
        'cover_image_url': new_cover_url,
        'remove_cover_image': '0'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert doc.cover_image_url == new_cover_url
    assert doc.cover_display_url == new_cover_url

def test_doctor_profile_cover_file_upload(client):
    """Verifies that uploading a cover image file saves to disk and updates doctor cover_image_url."""
    doc_id = 'DOC-EDIT-TABS-003'
    doc = Doctor(
        doc_id,
        'Ananya',
        'Deshmukh',
        'ananya.deshmukh@example.com',
        'Password123!',
        'Pediatrics',
        consultation_fee=800.0,
        cover_image_url=''
    )
    TEMP_DATA['doctors'][doc_id] = doc

    with client.session_transaction() as sess:
        sess['_user_id'] = str(doc_id)
        sess['user_role'] = 'doctor'
        sess['_fresh'] = True

    # Generate a small in-memory test image
    img_byte_arr = io.BytesIO()
    image = Image.new('RGB', (800, 300), color=(10, 80, 160))
    image.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)

    res = client.post('/doctor/dashboard', data={
        'action': 'update_profile',
        'first_name': 'Ananya',
        'last_name': 'Deshmukh',
        'email': 'ananya.deshmukh@example.com',
        'cover_image': (img_byte_arr, 'test_cover.jpg'),
        'remove_cover_image': '0'
    }, content_type='multipart/form-data', follow_redirects=True)

    assert res.status_code == 200
    assert doc.cover_image_url.startswith('doctor_covers/') or 'cover_' in doc.cover_image_url

    # Check cover image serving route
    cover_res = client.get(f'/doctor/cover/{doc_id}')
    assert cover_res.status_code in [200, 302]

def test_doctor_profile_cover_removal(client):
    """Verifies that clicking reset cover removes the custom cover and restores procedural default."""
    doc_id = 'DOC-EDIT-TABS-004'
    doc = Doctor(
        doc_id,
        'Vikram',
        'Patel',
        'vikram.patel@example.com',
        'Password123!',
        'Dermatology',
        consultation_fee=1100.0,
        cover_image_url='https://images.unsplash.com/photo-old-cover'
    )
    TEMP_DATA['doctors'][doc_id] = doc

    with client.session_transaction() as sess:
        sess['_user_id'] = str(doc_id)
        sess['user_role'] = 'doctor'
        sess['_fresh'] = True

    res = client.post('/doctor/dashboard', data={
        'action': 'update_profile',
        'first_name': 'Vikram',
        'last_name': 'Patel',
        'email': 'vikram.patel@example.com',
        'remove_cover_image': '1',
        'cover_image_url': ''
    }, follow_redirects=True)

    assert res.status_code == 200
    assert not doc.cover_image_url
    assert not doc.cover_display_url

def test_doctor_dashboard_reload_safety_and_resolver(client):
    """Verifies that doctor dashboard reload logic safely resolves tabs, supports #tab- prefixes, and never leaves screens hidden."""
    doc_id = 'DOC-RELOAD-TEST-005'
    doc = Doctor(
        doc_id,
        'Sunita',
        'Kapoor',
        'sunita.kapoor@example.com',
        'Password123!',
        'Internal Medicine',
        consultation_fee=1000.0,
        publishing_status='published'
    )
    TEMP_DATA['doctors'][doc_id] = doc

    with client.session_transaction() as sess:
        sess['_user_id'] = str(doc_id)
        sess['user_role'] = 'doctor'
        sess['_fresh'] = True

    # 1. Plain dashboard load
    res = client.get('/doctor/dashboard')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify overview section is active by default in HTML
    assert '<section id="tab-overview" class="tab-section active">' in html

    # Verify resolver function and reload listeners exist in client JS
    assert 'function resolveDoctorTargetTab(rawId)' in html
    assert 'function initDoctorDashboardTabs()' in html
    assert "window.addEventListener('hashchange'" in html
    assert "window.addEventListener('popstate'" in html

    # Verify safe fallback in switchDoctorTab
    assert "target = document.getElementById('tab-overview') || document.querySelector('.tab-section')" in html
    assert "sessionStorage.setItem('spherix_doctor_active_tab', effectiveTabId)" in html

    # 2. Query param ?tab=profile
    res_profile = client.get('/doctor/dashboard?tab=profile')
    assert res_profile.status_code == 200

    # 3. Query param ?tab=opinion or ?tab=referrals (legacy redirects)
    res_opinion = client.get('/doctor/dashboard?tab=opinion')
    assert res_opinion.status_code == 200

