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


def test_order_tracking_and_telemetry(client):
    # Order delivery telemetry portal
    res = client.get('/medicine-delivery')
    assert res.status_code == 200
    assert b'Medicine Online Delivery' in res.data or b'Live Delivery' in res.data or b'Telemetry' in res.data

    # Add item and checkout to get an order ID
    client.post('/api/cart/add', json={'name': 'Dolo 650 Tablet', 'price': 30.5, 'quantity': 1})
    res = client.post('/checkout', data={
        'name': 'Telemetry Tester',
        'phone': '9998887776',
        'address': 'MG Road, Bengaluru',
        'city': 'Bengaluru',
        'state': 'Karnataka',
        'pincode': '560001',
        'payment_method': 'cod'
    }, follow_redirects=False)
    assert res.status_code == 302
    order_id = res.headers['Location'].split('/')[-1]

    # Test order tracking portal with specific order ID
    res = client.get(f'/medicine-delivery/{order_id}')
    assert res.status_code == 200

    # Test order details
    res = client.get(f'/order-details/{order_id}')
    assert res.status_code == 200
    assert b'Telemetry Tester' in res.data

    # Test tracking telemetry API
    res = client.get(f'/api/delivery/track/{order_id}')
    assert res.status_code == 200
    assert res.json['success'] is True
    assert 'status' in res.json


def test_cart_quantity_stepper(client):
    # Add initial item
    client.post('/api/cart/add', json={'name': 'Pan 40 Tablet', 'price': 85.0, 'quantity': 1})
    
    # Increase quantity
    res = client.post('/update-cart-item', json={'name': 'Pan 40 Tablet', 'action': 'increase'})
    assert res.status_code == 200
    assert res.json['success'] is True

    # Decrease quantity
    res = client.post('/update-cart-item', json={'name': 'Pan 40 Tablet', 'action': 'decrease'})
    assert res.status_code == 200
    assert res.json['success'] is True

    # Direct quantity update
    res = client.post('/update-cart-item', json={'name': 'Pan 40 Tablet', 'quantity': 5})
    assert res.status_code == 200
    assert res.json['item']['quantity'] == 5
