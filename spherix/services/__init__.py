from spherix.services.database import (
    TEMP_DATA, get_db_connection, save_data, load_data,
    auto_migrate_local_data, migrate_legacy_schema,
    cleanup_temporary_and_duplicate_data, deduplicate_entities,
    setup_admin_user, setup_hospital_user, setup_international_network,
    create_notification, get_temp_data_item, reset_factory_database
)
from spherix.services.mail_service import (
    send_notification_email, send_notification_email_async, get_premium_otp_email_html,
    send_approval_notification, get_account_approval_email_html
)
from spherix.services.payment_service import (
    verify_razorpay_signature, create_razorpay_order,
    get_razorpay_key_id, create_razorpay_payment_link, get_razorpay_client
)
from spherix.services.pdf_service import (
    SpherixClinicalPrescriptionPDF, generate_spherix_clinical_pdf, to_latin1_str
)
from spherix.services.ai_service import (
    analyze_symptoms_locally, get_cache_key, _extract_json_payload,
    SYMPTOM_CACHE, ACTIVE_SYMPTOM_REPORTS, LAST_API_CALL_TIME
)

__all__ = [
    'TEMP_DATA', 'get_db_connection', 'save_data', 'load_data',
    'auto_migrate_local_data', 'migrate_legacy_schema',
    'cleanup_temporary_and_duplicate_data', 'deduplicate_entities',
    'setup_admin_user', 'setup_hospital_user', 'setup_international_network',
    'create_notification', 'get_temp_data_item', 'reset_factory_database',
    'send_notification_email', 'send_notification_email_async', 'get_premium_otp_email_html',
    'send_approval_notification', 'get_account_approval_email_html',
    'verify_razorpay_signature', 'create_razorpay_order',
    'get_razorpay_key_id', 'create_razorpay_payment_link', 'get_razorpay_client',
    'SpherixClinicalPrescriptionPDF', 'generate_spherix_clinical_pdf', 'to_latin1_str',
    'analyze_symptoms_locally', 'get_cache_key', '_extract_json_payload',
    'SYMPTOM_CACHE', 'ACTIVE_SYMPTOM_REPORTS', 'LAST_API_CALL_TIME'
]
