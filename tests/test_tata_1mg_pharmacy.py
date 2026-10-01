"""
Tests for Tata 1mg Pharmacy System in Spherix Clinic.
Covers shop catalog, medicine detail page, generic substitute finder,
cart management, coupon discounts, care plan savings, and order placement.
"""

import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_medical_shop_page(client):
    res = client.get('/medical-shop')
    assert res.status_code == 200
    assert b'TATA' in res.data or b'1mg' in res.data
    assert b'Medicines' in res.data or b'MEDICINES' in res.data

def test_medicine_detail_page(client):
    res = client.get('/medicine/Augmentin 625 Duo Tablet')
    assert res.status_code == 200
    assert b'Augmentin 625 Duo' in res.data
    assert b'Active Salt Composition' in res.data
    assert b'Substitutes' in res.data

def test_substitute_finder_page(client):
    res = client.get('/substitutes/Augmentin 625 Duo Tablet')
    assert res.status_code == 200
    assert b'Augmentin 625 Duo' in res.data
    assert b'Substitutes' in res.data
    assert b'Identical Chemical Salt' in res.data

def test_cart_and_coupon_workflow(client):
    # Add item to cart
    res = client.post('/api/cart/add', json={
        'id': 'med_1',
        'name': 'Augmentin 625 Duo Tablet',
        'price': 102.0,
        'quantity': 1
    })
    assert res.status_code == 200
    assert res.json['success'] is True

    # View Cart
    res = client.get('/cart')
    assert res.status_code == 200
    assert b'Augmentin 625 Duo Tablet' in res.data

    # Apply Coupon
    res = client.post('/apply-coupon', json={'coupon_code': 'TATA20'})
    assert res.status_code == 200
    assert res.json['success'] is True
    assert res.json['summary']['applied_coupon'] == 'TATA20'
    assert res.json['summary']['coupon_discount'] > 0

    # Toggle Care Plan
    res = client.post('/toggle-care-plan', json={'action': 'enable'})
    assert res.status_code == 200
    assert res.json['care_plan_active'] is True

def test_checkout_and_order_success(client):
    # Prepare cart
    client.post('/api/cart/add', json={
        'id': 'med_1',
        'name': 'Augmentin 625 Duo Tablet',
        'price': 102.0,
        'quantity': 1
    })

    # Checkout page
    res = client.get('/checkout')
    assert res.status_code == 200
    assert b'Delivery Address' in res.data

    # Submit order
    res = client.post('/checkout', data={
        'name': 'Dev Test Patient',
        'phone': '9876543210',
        'address': 'Test Apartment 101, Connaught Place',
        'city': 'New Delhi',
        'state': 'Delhi',
        'pincode': '110001',
        'payment_method': 'cod'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Order Confirmed' in res.data
    assert b'Dev Test Patient' in res.data
