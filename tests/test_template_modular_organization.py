import os
import pytest
from app import create_app
from flask import render_template

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app

def test_template_module_directories_exist(app):
    """
    Verifies that all modular template directories exist under templates/
    matching cancer_care and insurance structure.
    """
    templates_root = app.template_folder
    expected_modules = [
        'admin',
        'auth',
        'blood_organ',
        'cancer_care',
        'clinical_ai',
        'doctor',
        'hospital',
        'insurance',
        'main',
        'pathology',
        'patient',
        'pharmacy',
        'shared',
        'staff'
    ]
    for mod in expected_modules:
        mod_path = os.path.join(templates_root, mod)
        assert os.path.isdir(mod_path), f"Modular template folder '{mod}' does not exist at {mod_path}"
        files = [f for f in os.listdir(mod_path) if f.endswith('.html')]
        assert len(files) > 0, f"Modular template folder '{mod}' is empty"

def test_universal_loader_dual_path_resolution(app):
    """
    Verifies that templates can be rendered using both modular path (module/file.html)
    and legacy direct path (file.html).
    """
    with app.test_request_context('/'):
        # 1. Admin Module
        t_prefixed = app.jinja_env.get_template('admin/admin_login.html')
        t_direct = app.jinja_env.get_template('admin_login.html')
        assert t_prefixed is not None
        assert t_direct is not None

        # 2. Doctor Module
        t_doc_pref = app.jinja_env.get_template('doctor/doctor_login.html')
        t_doc_dir = app.jinja_env.get_template('doctor_login.html')
        assert t_doc_pref is not None
        assert t_doc_dir is not None

        # 3. Hospital Module
        t_hosp_pref = app.jinja_env.get_template('hospital/hospital_login.html')
        t_hosp_dir = app.jinja_env.get_template('hospital_login.html')
        assert t_hosp_pref is not None
        assert t_hosp_dir is not None

        # 4. Patient Module
        t_pat_pref = app.jinja_env.get_template('patient/patient_login.html')
        t_pat_dir = app.jinja_env.get_template('patient_login.html')
        assert t_pat_pref is not None
        assert t_pat_dir is not None

        # 5. Cancer Care (existing modular standard)
        t_cc_pref = app.jinja_env.get_template('cancer_care/awareness.html')
        assert t_cc_pref is not None

        # 6. Insurance (existing modular standard)
        t_ins_pref = app.jinja_env.get_template('insurance/plans.html')
        assert t_ins_pref is not None

def test_base_layouts_accessible_across_modules(app):
    """
    Verifies that base layout templates (layout.html, dashboard_layout.html)
    can be extended by modular templates across all subdirectories.
    """
    with app.test_request_context('/'):
        # Check that layout.html and dashboard_layout.html are loadable
        t_layout = app.jinja_env.get_template('layout.html')
        assert t_layout is not None
        t_dash = app.jinja_env.get_template('dashboard_layout.html')
        assert t_dash is not None

