"""
Compatibility alias module for diagnostic catalog.
"""
from spherix.services.diagnostic_catalog import (
    DIAGNOSTIC_MASTER_CATEGORIES,
    MASTER_TESTS_CATALOG,
    MASTER_PACKAGES_CATALOG,
    get_category_by_code,
    get_test_by_code,
    get_package_by_code
)

LAB_TEST_CATALOG = MASTER_TESTS_CATALOG
LAB_CATEGORIES = DIAGNOSTIC_MASTER_CATEGORIES
LAB_PACKAGES = MASTER_PACKAGES_CATALOG
