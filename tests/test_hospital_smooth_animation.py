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

def test_hospital_dashboard_smooth_animations_and_telemetry(client):
    """Verify that templates/hospital_dashboard.html contains smooth animations and realistic telemetry widgets."""
    with open("templates/hospital_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Verify CSS styles for realistic clinical telemetry & smooth transitions
    assert ".ecg-monitor-box" in html
    assert ".ecg-svg-path" in html
    assert "@keyframes ecg-sweep" in html
    assert ".live-beacon-dot" in html
    assert ".hospital-command-hero" in html
    assert "scroll-behavior: smooth" in html

    # 2. Verify Real-time Digital Clock & Status Badges
    assert "liveClockTime" in html
    assert "liveClockDate" in html
    assert "initLiveClock()" in html

    # 3. Verify Realistic ICU ECG Sinus Rhythm Monitor & Operational Metrics
    assert "ICU TELEMETRY SYNC" in html
    assert "NORMAL SINUS RHYTHM" in html
    assert "Central Oxygen" in html
    assert "4.8 Bar PSA" in html
    assert "Grid & DG Sync" in html

    # 4. Verify Micro-animated KPI Progress Bars
    assert "bed_occupancy_percent" in html
    assert "today_appointments_count" in html
    # Check bed capacity progress bar
    assert "stats.bed_occupancy_percent || 0) > 85 ? 'bg-danger'" in html

    # 5. Verify smooth Alpine transition directives on activeTab containers
    tab_transitions = re.findall(r'<div[^>]*x-show="activeTab\s*===[^"]+"[^>]*x-transition:enter', html)
    assert len(tab_transitions) >= 25, f"Expected tab transitions on tab containers, got {len(tab_transitions)}"

    # 6. Verify HTML tag balance
    open_divs = len(re.findall(r"<div\b", html))
    close_divs = len(re.findall(r"</div\b", html))
    assert open_divs == close_divs, f"Mismatched div tags: {open_divs} opens vs {close_divs} closes"
