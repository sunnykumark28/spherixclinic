import re
import pytest
from spherix import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client

def test_hospital_settings_default_view_mode_and_edit_buttons(client):
    """Verifies that all hospital settings subtabs start in view mode by default and only open editing via the Edit button."""
    with open("templates/hospital_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Verify CSS prevents display: none overrides from Bootstrap !important rules
    assert '[style*="display: none"]' in html
    assert "display: none !important" in html
    assert ".settings-view-container" in html
    assert ".settings-edit-container" in html

    # 2. Verify all 10 subtabs in editMode object initialize to false
    expected_subtabs = [
        "profile",
        "branding",
        "resources",
        "clinical",
        "infrastructure",
        "rates",
        "emergency",
        "policies",
        "social",
        "security"
    ]

    for tab in expected_subtabs:
        # Check editMode definition has tab: false
        pattern = rf"{tab}\s*:\s*false"
        assert re.search(pattern, html), f"Expected editMode.{tab} to initialize to false"

        # Check view mode wrapper exists
        assert f'x-show="!editMode.{tab}"' in html, f"Missing view container x-show='!editMode.{tab}'"

        # Check edit mode wrapper exists
        assert f'x-show="editMode.{tab}"' in html, f"Missing edit container x-show='editMode.{tab}'"

        # Check toggle button exists for this tab
        btn_pattern = rf'@click="editMode\.{tab}\s*=\s*!editMode\.{tab}"'
        assert re.search(btn_pattern, html), f"Missing toggle button for editMode.{tab}"

    # 3. Verify no x-show with editMode has the conflicting 'd-flex' utility class directly on it
    conflicting_edit_divs = re.findall(r'<div[^>]*x-show="editMode\.[^"]*"[^>]*class="[^"]*\bd-flex\b[^"]*"', html)
    assert len(conflicting_edit_divs) == 0, f"Found conflicting d-flex on editMode divs: {conflicting_edit_divs}"

    conflicting_view_divs = re.findall(r'<div[^>]*x-show="!editMode\.[^"]*"[^>]*class="[^"]*\bd-flex\b[^"]*"', html)
    assert len(conflicting_view_divs) == 0, f"Found conflicting d-flex on !editMode divs: {conflicting_view_divs}"

    # 4. Verify switchSettingsTab resets editMode so cards are always shown by default
    assert "Object.keys(this.editMode).forEach" in html

    # 5. Verify topbar dropdown does not force editMode.profile = true
    assert "editMode.profile = true" not in html

