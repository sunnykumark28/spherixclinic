"""
Unit and regression tests verifying that all secondary tabs and subtab navigation bars
have spacious, clean layout styling (padding, gap, margins) across all primary templates.
"""

def test_layout_secondary_navbar_tabs_spacing():
    with open('templates/layout.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Main navbar tab styling
    assert 'gap-1.5 md:gap-2 lg:gap-2.5 xl:gap-3.5' in html or 'gap-1.5' in html
    assert 'padding: 0.35rem 0.75rem' in html
    assert '.spherix-nav-tab' in html

    # 2. Services mega-menu secondary tab items spacing
    assert 'space-y-1.5 sm:space-y-2' in html
    assert 'grid grid-cols-1 sm:grid-cols-3 gap-2.5 sm:gap-3' in html

def test_doctor_dashboard_subtabs_spacing():
    with open('templates/doctor_dashboard.html', 'r', encoding='utf-8') as f:
        html = f.read()

    assert 'padding: 9px 20px;' in html
    assert 'padding: 6px 15px;' in html
    assert 'gap-2.5 sm:gap-3' in html

def test_hospital_dashboard_subtabs_spacing():
    with open('templates/hospital_dashboard.html', 'r', encoding='utf-8') as f:
        html = f.read()

    assert 'padding: 10px 18px;' in html
    assert 'padding: 7px 16px;' in html
    assert 'gap-2.5 sm:gap-3' in html

def test_admin_dashboard_settings_subtabs_spacing():
    with open('templates/admin_dashboard.html', 'r', encoding='utf-8') as f:
        html = f.read()

    assert 'd-flex flex-column gap-2' in html
    assert 'General & Brand' in html

def test_patient_dashboard_subtabs_spacing():
    with open('templates/patient_dashboard.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # Order screen tabs
    assert 'padding: 9px 18px;' in html
    assert 'gap-2.5 sm:gap-3 mb-4 p-2.5 bg-light rounded-3 border' in html

    # Communication toggles
    assert 'gap-2.5 sm:gap-3 p-2 bg-light rounded-pill border' in html

    # Sidebar sublinks
    assert 'ms-3 ps-2 border-start d-flex flex-column gap-1.5 my-2' in html

def test_pathology_layout_secondary_tab_bar_spacing():
    with open('templates/pathology_layout.html', 'r', encoding='utf-8') as f:
        html = f.read()

    assert 'gap-2 sm:gap-3 lg:gap-3.5 shrink-0' in html
    assert 'px-3.5 py-2' in html

def test_insurance_subtabs_spacing():
    with open('templates/insurance/my_insurance.html', 'r', encoding='utf-8') as f:
        my_ins = f.read()
    assert 'gap-2.5 sm:gap-3.5' in my_ins
    assert 'px-4.5 py-2.5' in my_ins

    with open('templates/insurance/admin_insurance.html', 'r', encoding='utf-8') as f:
        admin_ins = f.read()
    assert 'gap-2.5 sm:gap-3.5' in admin_ins
    assert 'px-4.5 py-2.5' in admin_ins

def test_dropdown_icons_on_services_donor_more_tabs():
    with open('templates/layout.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Services dropdown icon
    assert '<span>SERVICES</span>' in html
    assert 'dropdown-icon' in html
    assert 'fa-chevron-down' in html

    # 2. Donor Networks dropdown icon
    assert '<span>DONOR NETWORKS</span>' in html

    # 3. More dropdown icon
    assert '<span>MORE</span>' in html

    # Verify CSS enables dropdown icons
    assert '.spherix-nav-tab .dropdown-icon' in html or '.spherix-nav-tab .fa-chevron-down' in html
    assert 'i:not(.fa-chevron-down):not(.dropdown-icon)' in html

def test_secondary_header_medical_colour():
    with open('templates/layout.html', 'r', encoding='utf-8') as f:
        layout_html = f.read()

    # 1. Main navbar has medical blue styling, not black
    assert 'bg-black' not in layout_html[layout_html.find('id="main-navbar"'):layout_html.find('id="main-navbar"') + 200]
    assert '#005eb8' in layout_html  # Pure medical blue
    assert '#004b87' in layout_html  # Deep medical blue
    assert 'from-[#002e5b] via-[#004b87] to-[#005eb8]' in layout_html

    # 2. Check Pathology secondary navigation bar has medical color
    with open('templates/pathology_layout.html', 'r', encoding='utf-8') as f:
        pathology_html = f.read()
    assert 'from-[#002e5b] via-[#004b87] to-[#005eb8]' in pathology_html

