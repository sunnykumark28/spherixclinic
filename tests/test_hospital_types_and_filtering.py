import os
import sys
import unittest
import pytest

# Ensure app is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from spherix.hospital_types import (
    HOSPITAL_TYPE_MASTER_DATA, MASTER_FACILITIES_LIST, HospitalType,
    get_all_hospital_types, get_hospital_type_by_id, get_hospital_type_by_slug
)
from spherix.models.user import Hospital
from spherix.services.database import (
    TEMP_DATA, get_hospital_types, get_hospital_type_by_id as db_get_type_by_id,
    add_hospital_type, update_hospital_type, toggle_hospital_type_status,
    delete_hospital_type, calculate_haversine_distance, filter_hospitals_advanced
)
from app import app


class TestHospitalTypeMasterData(unittest.TestCase):
    """Tests for the 18 Master Hospital Categories + Other and catalog structures."""

    def test_master_catalog_contains_18_standard_categories_plus_other(self):
        self.assertGreaterEqual(len(HOSPITAL_TYPE_MASTER_DATA), 19)
        
        # Verify 18 standard categories exist with exact IDs and names
        expected_types = {
            1: "General Hospital",
            2: "Multispecialty Hospital",
            3: "Super Specialty Hospital",
            4: "Cardiology Hospital",
            5: "Oncology Hospital",
            6: "Neurology Hospital",
            7: "Orthopedic Hospital",
            8: "Maternity Hospital",
            9: "Pediatric Hospital",
            10: "Psychiatric Hospital",
            11: "Eye Hospital",
            12: "Dental Hospital",
            13: "ENT Hospital",
            14: "Nephrology Hospital",
            15: "Rehabilitation Hospital",
            16: "Infectious Disease Hospital",
            17: "Burns and Plastic Surgery Hospital",
            18: "Emergency and Trauma Hospital",
            19: "Other"
        }
        
        for t_id, t_name in expected_types.items():
            t_obj = get_hospital_type_by_id(t_id)
            self.assertIsNotNone(t_obj, f"Category ID {t_id} ({t_name}) should exist in master data")
            self.assertEqual(t_obj.name, t_name)
            self.assertTrue(len(t_obj.description) > 0)
            self.assertTrue(t_obj.is_active)

    def test_get_by_slug(self):
        cardio = get_hospital_type_by_slug("cardiology-hospital")
        self.assertIsNotNone(cardio)
        self.assertEqual(cardio.id, 4)
        self.assertEqual(cardio.name, "Cardiology Hospital")

        onco = get_hospital_type_by_slug("oncology-hospital")
        self.assertIsNotNone(onco)
        self.assertEqual(onco.id, 5)

    def test_master_facilities_list(self):
        self.assertIsInstance(MASTER_FACILITIES_LIST, list)
        facility_names = [f['name'] if isinstance(f, dict) else f for f in MASTER_FACILITIES_LIST]
        self.assertIn("Intensive Care Unit (ICU)", facility_names)
        self.assertIn("24x7 Emergency", facility_names)
        self.assertIn("24x7 Pharmacy", facility_names)
        self.assertIn("Blood Bank", facility_names)


class TestHospitalModelIntegration(unittest.TestCase):
    """Tests for Hospital model classification attributes, helper properties and methods."""

    def test_hospital_model_properties(self):
        h = Hospital(
            id=9901,
            name="Apex Heart & Trauma Institute",
            email="apex@hospital.org",
            password="hashed_secure_password_123",
            hospital_type_id=4,
            hospital_type="Cardiology Hospital",
            specialties=["Cardiology", "Cardiothoracic Surgery", "Vascular Surgery"],
            facilities=["Cath Lab (Cardiac)", "Intensive Care Unit (ICU)", "24/7 Pharmacy"],
            emergency_services=True,
            emergency_phone="+91 11 2658 8999",
            ambulance_phone="+91 11 2658 8998",
            about="Premier cardiac surgical center with 24/7 cath lab and ECMO support.",
            latitude=28.5672,
            longitude=77.2100,
            city="New Delhi",
            state="Delhi",
            country="India"
        )
        
        # Test helper properties
        self.assertEqual(h.type_name, "Cardiology Hospital")
        self.assertIn("Heart and cardiovascular", h.type_description)
        self.assertEqual(h.type_icon, "fa-solid fa-heart-pulse")
        self.assertEqual(h.type_color, "rose")
        
        # Test helper query methods
        self.assertTrue(h.has_facility("Cath Lab (Cardiac)"))
        self.assertTrue(h.has_facility("cath lab"))
        self.assertFalse(h.has_facility("Dialysis Center"))
        
        self.assertTrue(h.has_specialty("Cardiology"))
        self.assertTrue(h.has_specialty("vascular"))
        self.assertFalse(h.has_specialty("Neurology"))


class TestAdvancedFilterEngine(unittest.TestCase):
    """Tests for multi-parameter hospital search and filtering."""

    def setUp(self):
        # Create isolated test fixtures in TEMP_DATA['hospitals']
        self.h1 = Hospital(
            id=8001,
            name="Delhi Heart Institute",
            email="delhiheart@test.org",
            password="pass",
            hospital_type_id=4,
            hospital_type="Cardiology Hospital",
            specialties=["Cardiology", "Heart Surgery"],
            facilities=["Cath Lab (Cardiac)", "Intensive Care Unit (ICU)", "24/7 Pharmacy"],
            emergency_services=True,
            city="New Delhi",
            state="Delhi",
            country="India",
            latitude=28.6139,
            longitude=77.2090,
            is_verified=True,
            is_hidden=False,
            is_blocked=False
        )
        self.h2 = Hospital(
            id=8002,
            name="Mumbai Cancer & Oncology Center",
            email="mumbaionco@test.org",
            password="pass",
            hospital_type_id=5,
            hospital_type="Oncology Hospital",
            specialties=["Oncology", "Radiation Therapy", "Chemotherapy"],
            facilities=["PET-CT Scan", "Chemotherapy Daycare", "Blood Bank"],
            emergency_services=False,
            city="Mumbai",
            state="Maharashtra",
            country="India",
            latitude=19.0760,
            longitude=72.8777,
            is_verified=True,
            is_hidden=False,
            is_blocked=False
        )
        self.h3 = Hospital(
            id=8003,
            name="Bangalore Multispecialty Clinic",
            email="blrgeneral@test.org",
            password="pass",
            hospital_type_id=2,
            hospital_type="Multispecialty Hospital",
            specialties=["General Medicine", "Pediatrics", "Cardiology"],
            facilities=["24/7 Pharmacy", "Emergency Room (ER)"],
            emergency_services=True,
            city="Bengaluru",
            state="Karnataka",
            country="India",
            latitude=12.9716,
            longitude=77.5946,
            is_verified=False,
            is_hidden=False,
            is_blocked=False
        )
        
        TEMP_DATA['hospitals'][8001] = self.h1
        TEMP_DATA['hospitals'][8002] = self.h2
        TEMP_DATA['hospitals'][8003] = self.h3

    def tearDown(self):
        TEMP_DATA['hospitals'].pop(8001, None)
        TEMP_DATA['hospitals'].pop(8002, None)
        TEMP_DATA['hospitals'].pop(8003, None)

    def test_filter_by_hospital_type_id(self):
        # Filter Cardiology (type_id=4)
        cardio_results = filter_hospitals_advanced(type_id=4)
        self.assertTrue(any(h.id == 8001 for h in cardio_results))
        self.assertFalse(any(h.id == 8002 for h in cardio_results))

        # Filter Oncology (type_id=5)
        onco_results = filter_hospitals_advanced(type_id=5)
        self.assertTrue(any(h.id == 8002 for h in onco_results))
        self.assertFalse(any(h.id == 8001 for h in onco_results))

    def test_filter_by_specialty(self):
        res = filter_hospitals_advanced(specialty="Oncology")
        self.assertTrue(any(h.id == 8002 for h in res))
        self.assertFalse(any(h.id == 8001 for h in res))

    def test_filter_by_city_and_type_combined(self):
        res = filter_hospitals_advanced(city="Delhi", type_id=4)
        self.assertTrue(any(h.id == 8001 for h in res))
        
        res_none = filter_hospitals_advanced(city="Mumbai", type_id=4)
        self.assertFalse(any(h.id == 8001 for h in res_none))

    def test_filter_by_verified_and_emergency(self):
        # Emergency only
        er_res = filter_hospitals_advanced(emergency_only=True)
        self.assertTrue(any(h.id == 8001 for h in er_res))
        self.assertFalse(any(h.id == 8002 for h in er_res))

        # Verified only
        ver_res = filter_hospitals_advanced(verified_only=True)
        self.assertTrue(any(h.id == 8001 for h in ver_res))
        self.assertTrue(any(h.id == 8002 for h in ver_res))
        self.assertFalse(any(h.id == 8003 for h in ver_res))

    def test_filter_by_facilities(self):
        res = filter_hospitals_advanced(facilities_filter=["Cath Lab (Cardiac)"])
        self.assertTrue(any(h.id == 8001 for h in res))
        self.assertFalse(any(h.id == 8002 for h in res))

    def test_haversine_distance_and_proximity_sorting(self):
        # User in Delhi (28.6139, 77.2090)
        user_lat, user_lng = 28.6139, 77.2090
        
        # Delhi hospital should be 0 km, Bangalore ~1740 km, Mumbai ~1150 km
        dist_delhi = calculate_haversine_distance(user_lat, user_lng, self.h1.latitude, self.h1.longitude)
        dist_mumbai = calculate_haversine_distance(user_lat, user_lng, self.h2.latitude, self.h2.longitude)
        
        self.assertLess(dist_delhi, 5.0)
        self.assertGreater(dist_mumbai, 1000.0)

        nearby_res = filter_hospitals_advanced(user_lat=user_lat, user_lng=user_lng, nearby_only=True, max_distance_km=50.0)
        self.assertTrue(any(h.id == 8001 for h in nearby_res))
        self.assertFalse(any(h.id == 8002 for h in nearby_res))


class TestAdminCategoryManagement(unittest.TestCase):
    """Tests for admin creating, editing, toggling, and safely deleting hospital types."""

    def test_add_edit_toggle_delete_category(self):
        import time
        unique_suffix = str(int(time.time() * 1000))
        name_initial = f"Sports Medicine {unique_suffix}"
        name_updated = f"Sports Arthroscopy {unique_suffix}"

        # 1. Add new hospital type
        new_cat = add_hospital_type(
            name=name_initial,
            description="Specialized in athletic injuries, orthopedics, and spine rehabilitation.",
            icon="fa-person-running",
            color="emerald",
            is_active=True
        )
        self.assertIsNotNone(new_cat)
        cat_id = new_cat.id
        self.assertEqual(new_cat.name, name_initial)

        # 2. Get by ID
        fetched = db_get_type_by_id(cat_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, name_initial)

        # 3. Update Category
        updated = update_hospital_type(
            type_id=cat_id,
            name=name_updated,
            description="Updated arthroscopy and joint surgery description.",
            icon="fa-dumbbell",
            color="teal"
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, name_updated)
        self.assertEqual(updated.icon, "fa-dumbbell")

        # 4. Toggle Active Status
        toggled = toggle_hospital_type_status(cat_id)
        self.assertFalse(toggled.is_active)
        
        toggled_back = toggle_hospital_type_status(cat_id)
        self.assertTrue(toggled_back.is_active)

        # 5. Delete category with safety check
        # Assign a mock hospital to this category
        mock_h = Hospital(id=8999, name="Sports Hospital", email="sports@test.org", password="pass", hospital_type_id=cat_id)
        TEMP_DATA['hospitals'][8999] = mock_h

        # Attempt delete without reassign -> should be blocked
        success, msg = delete_hospital_type(cat_id)
        self.assertFalse(success)
        self.assertIn("Cannot delete", msg)

        # Attempt delete with reassignment to General Hospital (ID 1) -> should succeed
        success, msg = delete_hospital_type(cat_id, safe_reassign_to_id=1)
        self.assertTrue(success)
        self.assertEqual(TEMP_DATA['hospitals'][8999].hospital_type_id, 1)

        # Cleanup
        TEMP_DATA['hospitals'].pop(8999, None)


class TestWebEndpoints(unittest.TestCase):
    """Tests for HTTP routes and templates."""

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

    def test_hospitals_discovery_page_loads(self):
        response = self.client.get('/hospitals')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Verified Hospital Network", response.data)
        self.assertIn(b"Hospital Type", response.data)

    def test_hospitals_json_api_filtering(self):
        response = self.client.get('/hospitals?format=json&type=1')
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertTrue(json_data['success'])
        self.assertIn('hospitals', json_data)
        self.assertIn('total_filtered', json_data)

    def test_hospital_register_page_renders_categories(self):
        response = self.client.get('/hospital/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Primary Hospital Classification", response.data)
        self.assertIn(b"General Hospital", response.data)
        self.assertIn(b"Multispecialty Hospital", response.data)


if __name__ == '__main__':
    unittest.main()
