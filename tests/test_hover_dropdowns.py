import os
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client

def test_layout_hover_dropdowns_configured():
    """Verifies that templates/shared/layout.html has auto-open on hover for all dropdowns."""
    path = os.path.join('templates', 'shared', 'layout.html')
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Navigation bar dropdowns (Services, Donor Networks, More) have hover listeners
    assert '@mouseenter="clearTimeout(timeout); open = true"' in html
    assert '@mouseleave="timeout = setTimeout(() => open = false, 150)"' in html

    # 2. Login dropdown has hover container and mouseenter/mouseleave listeners
    assert 'id="loginDropdownContainer"' in html
    assert "loginDropdownContainer.addEventListener('mouseenter'" in html
    assert "loginDropdownContainer.addEventListener('mouseleave'" in html

    # 3. User profile dropdown has hover container and mouseenter/mouseleave listeners
    assert 'id="userProfileContainer"' in html
    assert "userProfileContainer.addEventListener('mouseenter'" in html
    assert "userProfileContainer.addEventListener('mouseleave'" in html

    # 4. Universal Bootstrap hover dropdowns configured
    assert 'initUniversalHoverDropdowns' in html
    assert "container.addEventListener('mouseenter'" in html
    assert "container.addEventListener('mouseleave'" in html

def test_dashboard_layout_hover_dropdowns_configured():
    """Verifies that templates/shared/dashboard_layout.html has universal hover dropdown auto-open."""
    path = os.path.join('templates', 'shared', 'dashboard_layout.html')
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Universal dashboard hover dropdown initializer
    assert 'initDashboardHoverDropdowns' in html
    assert "container.addEventListener('mouseenter'" in html
    assert "container.addEventListener('mouseleave'" in html

    # 2. CSS bridge preventing cursor gap flickering
    assert '.dropdown-menu::before' in html
    assert "top: -12px;" in html

def test_admin_dashboard_hover_dropdowns_configured():
    """Verifies that templates/admin/admin_dashboard.html has hover auto-open on notifications & user profile."""
    path = os.path.join('templates', 'admin', 'admin_dashboard.html')
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Admin notifications dropdown has hover listeners
    assert 'openAdminNotifDropdown' in html
    assert 'closeAdminNotifDropdown' in html
    assert "notifContainer.addEventListener('mouseenter'" in html
    assert "notifContainer.addEventListener('mouseleave'" in html

    # 2. Admin user profile dropdown has hover listeners
    assert 'openAdminUserDropdown' in html
    assert 'closeAdminUserDropdown' in html
    assert "userContainer.addEventListener('mouseenter'" in html
    assert "userContainer.addEventListener('mouseleave'" in html

    # 3. CSS bridge for smooth hover across gaps
    assert '#adminNotifDropdownMenu::before' in html
    assert '#adminUserDropdownMenu::before' in html

