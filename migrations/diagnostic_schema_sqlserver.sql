-- ============================================================================
-- Spherix Clinic — Enterprise Diagnostic & Pathology Laboratory Management Schema
-- Database: Microsoft SQL Server 2017+ / Azure SQL / AWS RDS for SQL Server
-- Script: diagnostic_schema_sqlserver.sql
-- ============================================================================

USE [spherixclinic];
GO

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

-- 1. Diagnostic Categories
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_categories' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_categories] (
        [id] VARCHAR(50) NOT NULL PRIMARY KEY,
        [name] NVARCHAR(100) NOT NULL,
        [description] NVARCHAR(MAX) NULL,
        [icon] NVARCHAR(100) DEFAULT 'fas fa-vial',
        [display_order] INT DEFAULT 0,
        [is_active] BIT DEFAULT 1,
        [created_at] DATETIME DEFAULT GETDATE()
    );
    CREATE NONCLUSTERED INDEX [IX_diag_cat_active] ON [dbo].[diagnostic_categories]([is_active]);
    PRINT 'Created table: diagnostic_categories';
END
GO

-- 2. Diagnostic Tests (Master Catalog)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_tests' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_tests] (
        [id] VARCHAR(50) NOT NULL PRIMARY KEY,
        [test_code] NVARCHAR(50) NOT NULL UNIQUE,
        [name] NVARCHAR(255) NOT NULL,
        [category_id] VARCHAR(50) NOT NULL,
        [category_name] NVARCHAR(100) NULL,
        [description] NVARCHAR(MAX) NULL,
        [specimen_type] NVARCHAR(100) NOT NULL,
        [preparation_instructions] NVARCHAR(MAX) NULL,
        [fasting_required] BIT DEFAULT 0,
        [fasting_hours] INT DEFAULT 0,
        [expected_tat_hours] INT DEFAULT 12,
        [prescription_required] BIT DEFAULT 0,
        [is_active] BIT DEFAULT 1,
        [clinical_notes] NVARCHAR(MAX) NULL,
        [base_price] DECIMAL(10,2) DEFAULT 500.0,
        [created_at] DATETIME DEFAULT GETDATE(),
        CONSTRAINT [FK_diag_test_cat] FOREIGN KEY ([category_id]) REFERENCES [dbo].[diagnostic_categories]([id])
    );
    CREATE NONCLUSTERED INDEX [IX_diag_test_code] ON [dbo].[diagnostic_tests]([test_code]);
    CREATE NONCLUSTERED INDEX [IX_diag_test_category] ON [dbo].[diagnostic_tests]([category_id]);
    PRINT 'Created table: diagnostic_tests';
END
GO

-- 3. Diagnostic Labs
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_labs' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_labs] (
        [id] VARCHAR(50) NOT NULL PRIMARY KEY,
        [legal_name] NVARCHAR(255) NOT NULL,
        [display_name] NVARCHAR(255) NOT NULL,
        [registration_number] NVARCHAR(100) NOT NULL UNIQUE,
        [lab_type] NVARCHAR(100) DEFAULT 'Independent Pathology Lab',
        [owner_name] NVARCHAR(255) NULL,
        [phone] NVARCHAR(50) NOT NULL,
        [email] NVARCHAR(255) NOT NULL UNIQUE,
        [password] NVARCHAR(255) NOT NULL,
        [address] NVARCHAR(MAX) NOT NULL,
        [city] NVARCHAR(100) NOT NULL,
        [state] NVARCHAR(100) NOT NULL,
        [pincode] NVARCHAR(20) NOT NULL,
        [latitude] FLOAT DEFAULT 0.0,
        [longitude] FLOAT DEFAULT 0.0,
        [service_radius_km] FLOAT DEFAULT 15.0,
        [license_number] NVARCHAR(100) NULL,
        [nabl_accreditation_number] NVARCHAR(100) NULL,
        [nabl_scope] NVARCHAR(MAX) NULL,
        [is_nabl_accredited] BIT DEFAULT 0,
        [home_collection_available] BIT DEFAULT 1,
        [walkin_available] BIT DEFAULT 1,
        [operating_hours] NVARCHAR(MAX) DEFAULT '07:00 AM - 09:00 PM',
        [bank_name] NVARCHAR(255) NULL,
        [account_number] NVARCHAR(100) NULL,
        [account_holder] NVARCHAR(255) NULL,
        [ifsc_code] NVARCHAR(50) NULL,
        [status] NVARCHAR(50) DEFAULT 'PENDING_VERIFICATION',
        [rejection_reason] NVARCHAR(MAX) NULL,
        [correction_request] NVARCHAR(MAX) NULL,
        [is_active] BIT DEFAULT 1,
        [created_at] DATETIME DEFAULT GETDATE(),
        [updated_at] DATETIME DEFAULT GETDATE()
    );
    CREATE NONCLUSTERED INDEX [IX_diag_lab_status] ON [dbo].[diagnostic_labs]([status], [is_active]);
    CREATE NONCLUSTERED INDEX [IX_diag_lab_pincode] ON [dbo].[diagnostic_labs]([pincode]);
    PRINT 'Created table: diagnostic_labs';
END
GO

-- 4. Diagnostic Lab Documents
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_lab_documents' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_lab_documents] (
        [id] INT IDENTITY(1,1) PRIMARY KEY,
        [lab_id] VARCHAR(50) NOT NULL,
        [document_type] NVARCHAR(100) NOT NULL,
        [document_name] NVARCHAR(255) NOT NULL,
        [file_path] NVARCHAR(500) NOT NULL,
        [uploaded_at] DATETIME DEFAULT GETDATE(),
        CONSTRAINT [FK_diag_doc_lab] FOREIGN KEY ([lab_id]) REFERENCES [dbo].[diagnostic_labs]([id]) ON DELETE CASCADE
    );
    PRINT 'Created table: diagnostic_lab_documents';
END
GO

-- 5. Diagnostic Lab Services (Lab-Specific Pricing and Offering)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_lab_services' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_lab_services] (
        [id] INT IDENTITY(1,1) PRIMARY KEY,
        [lab_id] VARCHAR(50) NOT NULL,
        [test_id] VARCHAR(50) NOT NULL,
        [price] DECIMAL(10,2) NOT NULL,
        [mrp] DECIMAL(10,2) NOT NULL,
        [home_collection_fee] DECIMAL(10,2) DEFAULT 0.0,
        [home_collection_available] BIT DEFAULT 1,
        [processing_available] BIT DEFAULT 1,
        [custom_tat_hours] INT NULL,
        [is_available] BIT DEFAULT 1,
        [created_at] DATETIME DEFAULT GETDATE(),
        [updated_at] DATETIME DEFAULT GETDATE(),
        CONSTRAINT [UQ_lab_service] UNIQUE ([lab_id], [test_id]),
        CONSTRAINT [FK_diag_service_lab] FOREIGN KEY ([lab_id]) REFERENCES [dbo].[diagnostic_labs]([id]) ON DELETE CASCADE,
        CONSTRAINT [FK_diag_service_test] FOREIGN KEY ([test_id]) REFERENCES [dbo].[diagnostic_tests]([id])
    );
    CREATE NONCLUSTERED INDEX [IX_diag_service_lookup] ON [dbo].[diagnostic_lab_services]([lab_id], [test_id], [is_available]);
    PRINT 'Created table: diagnostic_lab_services';
END
GO

-- 6. Diagnostic Bookings
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_bookings' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_bookings] (
        [id] VARCHAR(50) NOT NULL PRIMARY KEY,
        [booking_source] NVARCHAR(50) DEFAULT 'PATIENT_DIRECT',
        [referral_id] VARCHAR(50) NULL,
        [patient_id] VARCHAR(50) NOT NULL,
        [patient_name] NVARCHAR(255) NOT NULL,
        [patient_phone] NVARCHAR(50) NULL,
        [patient_email] NVARCHAR(255) NULL,
        [doctor_id] VARCHAR(50) NULL,
        [lab_id] VARCHAR(50) NOT NULL,
        [collection_type] NVARCHAR(50) DEFAULT 'HOME_COLLECTION',
        [collection_address] NVARCHAR(MAX) NULL,
        [collection_city] NVARCHAR(100) NULL,
        [collection_pincode] NVARCHAR(20) NULL,
        [collection_latitude] FLOAT NULL,
        [collection_longitude] FLOAT NULL,
        [scheduled_date] DATE NOT NULL,
        [scheduled_slot] NVARCHAR(100) NOT NULL,
        [subtotal] DECIMAL(10,2) NOT NULL,
        [collection_fee] DECIMAL(10,2) DEFAULT 0.0,
        [platform_fee] DECIMAL(10,2) DEFAULT 0.0,
        [total_amount] DECIMAL(10,2) NOT NULL,
        [lab_commission_rate] DECIMAL(5,2) DEFAULT 10.0,
        [lab_payout_amount] DECIMAL(10,2) NOT NULL,
        [status] NVARCHAR(50) NOT NULL DEFAULT 'REQUESTED',
        [decline_reason] NVARCHAR(MAX) NULL,
        [cancellation_reason] NVARCHAR(MAX) NULL,
        [patient_notes] NVARCHAR(MAX) NULL,
        [prescription_file] NVARCHAR(500) NULL,
        [idempotency_key] NVARCHAR(100) UNIQUE NULL,
        [created_at] DATETIME DEFAULT GETDATE(),
        [updated_at] DATETIME DEFAULT GETDATE(),
        CONSTRAINT [FK_diag_bk_lab] FOREIGN KEY ([lab_id]) REFERENCES [dbo].[diagnostic_labs]([id])
    );
    CREATE NONCLUSTERED INDEX [IX_diag_bk_patient] ON [dbo].[diagnostic_bookings]([patient_id]);
    CREATE NONCLUSTERED INDEX [IX_diag_bk_lab] ON [dbo].[diagnostic_bookings]([lab_id], [status]);
    CREATE NONCLUSTERED INDEX [IX_diag_bk_date] ON [dbo].[diagnostic_bookings]([scheduled_date]);
    PRINT 'Created table: diagnostic_bookings';
END
GO

-- 7. Diagnostic Booking Items
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_booking_items' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_booking_items] (
        [id] INT IDENTITY(1,1) PRIMARY KEY,
        [booking_id] VARCHAR(50) NOT NULL,
        [test_id] VARCHAR(50) NOT NULL,
        [test_name] NVARCHAR(255) NOT NULL,
        [test_code] NVARCHAR(50) NULL,
        [price] DECIMAL(10,2) NOT NULL,
        [specimen_type] NVARCHAR(100) NULL,
        [fasting_required] BIT DEFAULT 0,
        CONSTRAINT [FK_diag_bki_bk] FOREIGN KEY ([booking_id]) REFERENCES [dbo].[diagnostic_bookings]([id]) ON DELETE CASCADE
    );
    PRINT 'Created table: diagnostic_booking_items';
END
GO

-- 8. Diagnostic Referrals
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_referrals' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_referrals] (
        [id] VARCHAR(50) NOT NULL PRIMARY KEY,
        [referral_number] NVARCHAR(100) NOT NULL UNIQUE,
        [doctor_id] VARCHAR(50) NOT NULL,
        [doctor_name] NVARCHAR(255) NULL,
        [patient_id] VARCHAR(50) NOT NULL,
        [patient_name] NVARCHAR(255) NULL,
        [selected_lab_id] VARCHAR(50) NULL,
        [priority] NVARCHAR(50) DEFAULT 'ROUTINE',
        [clinical_indication] NVARCHAR(MAX) NOT NULL,
        [doctor_instructions] NVARCHAR(MAX) NULL,
        [patient_location] NVARCHAR(MAX) NULL,
        [status] NVARCHAR(50) DEFAULT 'ISSUED',
        [booking_id] VARCHAR(50) NULL,
        [created_at] DATETIME DEFAULT GETDATE(),
        [updated_at] DATETIME DEFAULT GETDATE()
    );
    CREATE NONCLUSTERED INDEX [IX_diag_ref_doc] ON [dbo].[diagnostic_referrals]([doctor_id]);
    CREATE NONCLUSTERED INDEX [IX_diag_ref_patient] ON [dbo].[diagnostic_referrals]([patient_id]);
    PRINT 'Created table: diagnostic_referrals';
END
GO

-- 9. Diagnostic Referral Items
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_referral_items' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_referral_items] (
        [id] INT IDENTITY(1,1) PRIMARY KEY,
        [referral_id] VARCHAR(50) NOT NULL,
        [test_id] VARCHAR(50) NOT NULL,
        [test_name] NVARCHAR(255) NOT NULL,
        [test_code] NVARCHAR(50) NULL,
        CONSTRAINT [FK_diag_refi_ref] FOREIGN KEY ([referral_id]) REFERENCES [dbo].[diagnostic_referrals]([id]) ON DELETE CASCADE
    );
    PRINT 'Created table: diagnostic_referral_items';
END
GO

-- 10. Diagnostic Sample Collections & Tracking
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_sample_collections' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_sample_collections] (
        [id] INT IDENTITY(1,1) PRIMARY KEY,
        [booking_id] VARCHAR(50) NOT NULL,
        [collection_type] NVARCHAR(50) NOT NULL,
        [collector_name] NVARCHAR(255) NULL,
        [collector_phone] NVARCHAR(50) NULL,
        [collection_address] NVARCHAR(MAX) NULL,
        [scheduled_date] DATE NOT NULL,
        [scheduled_slot] NVARCHAR(100) NOT NULL,
        [collection_status] NVARCHAR(50) DEFAULT 'SCHEDULED',
        [collection_notes] NVARCHAR(MAX) NULL,
        [collected_at] DATETIME NULL,
        [received_at_lab_at] DATETIME NULL,
        CONSTRAINT [FK_diag_coll_bk] FOREIGN KEY ([booking_id]) REFERENCES [dbo].[diagnostic_bookings]([id]) ON DELETE CASCADE
    );
    PRINT 'Created table: diagnostic_sample_collections';
END
GO

-- 11. Diagnostic Samples
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_samples' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_samples] (
        [id] VARCHAR(50) NOT NULL PRIMARY KEY,
        [booking_id] VARCHAR(50) NOT NULL,
        [test_id] VARCHAR(50) NOT NULL,
        [test_name] NVARCHAR(255) NULL,
        [sample_identifier] NVARCHAR(100) NOT NULL UNIQUE,
        [specimen_type] NVARCHAR(100) NOT NULL,
        [collected_at] DATETIME NULL,
        [status] NVARCHAR(50) DEFAULT 'COLLECTED',
        [rejection_reason] NVARCHAR(MAX) NULL,
        [notes] NVARCHAR(MAX) NULL,
        [created_at] DATETIME DEFAULT GETDATE(),
        CONSTRAINT [FK_diag_smp_bk] FOREIGN KEY ([booking_id]) REFERENCES [dbo].[diagnostic_bookings]([id]) ON DELETE CASCADE
    );
    CREATE NONCLUSTERED INDEX [IX_diag_smp_ident] ON [dbo].[diagnostic_samples]([sample_identifier]);
    PRINT 'Created table: diagnostic_samples';
END
GO

-- 12. Diagnostic Reports
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_reports' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_reports] (
        [id] VARCHAR(50) NOT NULL PRIMARY KEY,
        [booking_id] VARCHAR(50) NOT NULL,
        [patient_id] VARCHAR(50) NOT NULL,
        [doctor_id] VARCHAR(50) NULL,
        [lab_id] VARCHAR(50) NOT NULL,
        [test_id] VARCHAR(50) NOT NULL,
        [test_name] NVARCHAR(255) NULL,
        [report_number] NVARCHAR(100) NOT NULL UNIQUE,
        [file_path] NVARCHAR(500) NOT NULL,
        [file_name] NVARCHAR(255) NOT NULL,
        [file_size] INT DEFAULT 0,
        [mime_type] NVARCHAR(100) DEFAULT 'application/pdf',
        [status] NVARCHAR(50) DEFAULT 'DRAFT',
        [verified_by] NVARCHAR(255) NULL,
        [verified_at] DATETIME NULL,
        [published_at] DATETIME NULL,
        [version] INT DEFAULT 1,
        [amendment_reason] NVARCHAR(MAX) NULL,
        [clinical_summary] NVARCHAR(MAX) NULL,
        [parameters_json] NVARCHAR(MAX) NULL,
        [created_at] DATETIME DEFAULT GETDATE(),
        [updated_at] DATETIME DEFAULT GETDATE(),
        CONSTRAINT [FK_diag_rep_bk] FOREIGN KEY ([booking_id]) REFERENCES [dbo].[diagnostic_bookings]([id]),
        CONSTRAINT [FK_diag_rep_lab] FOREIGN KEY ([lab_id]) REFERENCES [dbo].[diagnostic_labs]([id])
    );
    CREATE NONCLUSTERED INDEX [IX_diag_rep_pat] ON [dbo].[diagnostic_reports]([patient_id]);
    CREATE NONCLUSTERED INDEX [IX_diag_rep_lab] ON [dbo].[diagnostic_reports]([lab_id], [status]);
    PRINT 'Created table: diagnostic_reports';
END
GO

-- 13. Diagnostic Report Versions
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_report_versions' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_report_versions] (
        [id] INT IDENTITY(1,1) PRIMARY KEY,
        [report_id] VARCHAR(50) NOT NULL,
        [version] INT NOT NULL,
        [file_path] NVARCHAR(500) NOT NULL,
        [amended_by] NVARCHAR(255) NOT NULL,
        [amendment_reason] NVARCHAR(MAX) NOT NULL,
        [amended_at] DATETIME DEFAULT GETDATE(),
        CONSTRAINT [FK_diag_repv_rep] FOREIGN KEY ([report_id]) REFERENCES [dbo].[diagnostic_reports]([id]) ON DELETE CASCADE
    );
    PRINT 'Created table: diagnostic_report_versions';
END
GO

-- 14. Diagnostic Payments
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_payments' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_payments] (
        [id] VARCHAR(50) NOT NULL PRIMARY KEY,
        [booking_id] VARCHAR(50) NOT NULL,
        [patient_id] VARCHAR(50) NOT NULL,
        [amount] DECIMAL(10,2) NOT NULL,
        [currency] NVARCHAR(10) DEFAULT 'INR',
        [payment_method] NVARCHAR(50) DEFAULT 'RAZORPAY',
        [payment_gateway_order_id] NVARCHAR(255) NULL,
        [payment_gateway_payment_id] NVARCHAR(255) NULL,
        [payment_gateway_signature] NVARCHAR(255) NULL,
        [status] NVARCHAR(50) DEFAULT 'PENDING',
        [idempotency_key] NVARCHAR(100) UNIQUE NULL,
        [created_at] DATETIME DEFAULT GETDATE(),
        [updated_at] DATETIME DEFAULT GETDATE(),
        CONSTRAINT [FK_diag_pay_bk] FOREIGN KEY ([booking_id]) REFERENCES [dbo].[diagnostic_bookings]([id])
    );
    PRINT 'Created table: diagnostic_payments';
END
GO

-- 15. Diagnostic Refunds
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_refunds' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_refunds] (
        [id] VARCHAR(50) NOT NULL PRIMARY KEY,
        [booking_id] VARCHAR(50) NOT NULL,
        [payment_id] VARCHAR(50) NULL,
        [patient_id] VARCHAR(50) NOT NULL,
        [refund_amount] DECIMAL(10,2) NOT NULL,
        [reason] NVARCHAR(MAX) NOT NULL,
        [status] NVARCHAR(50) DEFAULT 'PENDING',
        [gateway_refund_id] NVARCHAR(255) NULL,
        [processed_at] DATETIME NULL,
        [created_at] DATETIME DEFAULT GETDATE()
    );
    PRINT 'Created table: diagnostic_refunds';
END
GO

-- 16. Diagnostic Settlements
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_settlements' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_settlements] (
        [id] VARCHAR(50) NOT NULL PRIMARY KEY,
        [lab_id] VARCHAR(50) NOT NULL,
        [period_start] DATE NOT NULL,
        [period_end] DATE NOT NULL,
        [gross_amount] DECIMAL(10,2) NOT NULL,
        [commission_amount] DECIMAL(10,2) NOT NULL,
        [net_payout_amount] DECIMAL(10,2) NOT NULL,
        [status] NVARCHAR(50) DEFAULT 'PENDING',
        [utr_number] NVARCHAR(100) NULL,
        [settled_at] DATETIME NULL,
        [created_at] DATETIME DEFAULT GETDATE(),
        CONSTRAINT [FK_diag_set_lab] FOREIGN KEY ([lab_id]) REFERENCES [dbo].[diagnostic_labs]([id])
    );
    PRINT 'Created table: diagnostic_settlements';
END
GO

-- 17. Diagnostic Notifications
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_notifications' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_notifications] (
        [id] INT IDENTITY(1,1) PRIMARY KEY,
        [recipient_type] NVARCHAR(50) NOT NULL,
        [recipient_id] VARCHAR(50) NOT NULL,
        [booking_id] VARCHAR(50) NULL,
        [title] NVARCHAR(255) NOT NULL,
        [message] NVARCHAR(MAX) NOT NULL,
        [link] NVARCHAR(500) NULL,
        [is_read] BIT DEFAULT 0,
        [created_at] DATETIME DEFAULT GETDATE()
    );
    PRINT 'Created table: diagnostic_notifications';
END
GO

-- 18. Diagnostic Audit Logs
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='diagnostic_audit_logs' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[diagnostic_audit_logs] (
        [id] INT IDENTITY(1,1) PRIMARY KEY,
        [actor_type] NVARCHAR(50) NOT NULL,
        [actor_id] VARCHAR(50) NOT NULL,
        [action] NVARCHAR(100) NOT NULL,
        [resource_type] NVARCHAR(100) NOT NULL,
        [resource_id] VARCHAR(50) NOT NULL,
        [details] NVARCHAR(MAX) NULL,
        [ip_address] NVARCHAR(50) NULL,
        [timestamp] DATETIME DEFAULT GETDATE()
    );
    PRINT 'Created table: diagnostic_audit_logs';
END
GO

PRINT '🎉 Diagnostic & Pathology Laboratory Management Schema deployed successfully.';
GO
