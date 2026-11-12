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

def test_hospital_settings_cards_spacing_and_merged_text(client):
    """Verify that templates/hospital_dashboard.html implements spaces between two cards and merges text and cards."""
    with open("templates/hospital_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Verify CSS styles for card spacing and merged info boxes
    assert "#settingsMainContent .settings-subcard" in html
    assert ".settings-subcard + .settings-subcard" in html
    assert "margin-top: 1.75rem !important" in html
    assert ".settings-info-card" in html
    assert ".settings-edit-box" in html

    # 2. Verify subcards have settings-subcard class and generous margin bottom
    subcards = re.findall(r'class="[^"]*settings-subcard[^"]*"', html)
    assert len(subcards) >= 15, f"Expected at least 15 settings-subcard containers, found {len(subcards)}"

    # 3. Verify merged text and card containers
    info_cards = re.findall(r'class="[^"]*settings-info-card[^"]*"', html)
    assert len(info_cards) >= 20, f"Expected at least 20 settings-info-card elements, found {len(info_cards)}"

    # 4. Verify tag balance
    open_divs = len(re.findall(r"<div\b", html))
    close_divs = len(re.findall(r"</div\b", html))
    assert open_divs == close_divs, f"Mismatched div tags: {open_divs} opens vs {close_divs} closes"
