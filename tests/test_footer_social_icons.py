import pytest

@pytest.fixture
def client():
    from spherix import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client

def test_footer_social_media_real_svg_icons(client):
    """Verifies that the global footer renders real official SVG vector icons for all social channels without CSS hiding rules."""
    res = client.get('/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # 1. Verify presence of footer
    assert '<footer id="main-footer"' in html
    assert 'Connect With Spherix' in html

    # 2. Verify real SVG vector icons for all 6 social media platforms
    assert 'aria-label="Facebook"' in html
    assert 'title="Facebook"' in html
    assert 'https://facebook.com' in html

    assert 'aria-label="X (Twitter)"' in html
    assert 'title="X (Twitter)"' in html
    assert 'https://twitter.com' in html

    assert 'aria-label="Instagram"' in html
    assert 'title="Instagram"' in html
    assert 'https://instagram.com' in html

    assert 'aria-label="LinkedIn"' in html
    assert 'title="LinkedIn"' in html
    assert 'https://linkedin.com' in html

    assert 'aria-label="YouTube"' in html
    assert 'title="YouTube"' in html
    assert 'https://youtube.com' in html

    assert 'aria-label="WhatsApp"' in html
    assert 'title="WhatsApp 24x7 Help"' in html
    assert 'https://wa.me/919334325920' in html

    # 3. Verify real SVG markup is rendered inside the social links
    assert '<svg class="w-4 h-4 fill-current group-hover:scale-110' in html
    assert 'viewBox="0 0 24 24"' in html

    # 4. Verify that '#main-footer i { display: none !important; }' has been removed
    assert '#main-footer i {' not in html
    assert '#main-footer i {\n                display: none !important;\n            }' not in html

