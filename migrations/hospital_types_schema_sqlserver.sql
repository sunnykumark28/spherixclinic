-- ============================================================================
-- Spherix Clinic — Production Hospital Classification & Advanced Filtering Schema
-- Database: Microsoft SQL Server 2017+ / Azure SQL / AWS RDS for SQL Server
-- Script: hospital_types_schema_sqlserver.sql
-- ============================================================================

USE [spherixclinic];
GO

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

-- 1. Hospital Types Master Table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='hospital_types' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[hospital_types] (
        [id] INT NOT NULL PRIMARY KEY,
        [name] NVARCHAR(255) NOT NULL UNIQUE,
        [slug] VARCHAR(100) NOT NULL UNIQUE,
        [description] NVARCHAR(MAX) NULL,
        [icon] NVARCHAR(100) DEFAULT 'fa-solid fa-hospital',
        [color] NVARCHAR(50) DEFAULT 'emerald',
        [badge_bg] NVARCHAR(50) DEFAULT 'bg-emerald-50',
        [badge_text] NVARCHAR(50) DEFAULT 'text-emerald-700',
        [badge_border] NVARCHAR(50) DEFAULT 'border-emerald-200',
        [is_active] BIT DEFAULT 1,
        [created_at] DATETIME DEFAULT GETDATE()
    );
    CREATE NONCLUSTERED INDEX [IX_hospital_types_active] ON [dbo].[hospital_types]([is_active]);
    CREATE NONCLUSTERED INDEX [IX_hospital_types_slug] ON [dbo].[hospital_types]([slug]);
    PRINT 'Created table: hospital_types';
END
GO

-- 2. Hospital Type Multi-Classification Mappings Table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='hospital_type_mappings' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[hospital_type_mappings] (
        [id] INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        [hospital_id] VARCHAR(50) NOT NULL,
        [hospital_type_id] INT NOT NULL,
        [is_primary] BIT DEFAULT 0,
        [created_at] DATETIME DEFAULT GETDATE(),
        CONSTRAINT [FK_hosp_map_type] FOREIGN KEY ([hospital_type_id]) REFERENCES [dbo].[hospital_types]([id]) ON DELETE CASCADE
    );
    CREATE NONCLUSTERED INDEX [IX_hosp_map_hospital] ON [dbo].[hospital_type_mappings]([hospital_id]);
    CREATE NONCLUSTERED INDEX [IX_hosp_map_type_id] ON [dbo].[hospital_type_mappings]([hospital_type_id]);
    PRINT 'Created table: hospital_type_mappings';
END
GO

-- 3. Add Classification & Telemetry Columns to Existing Hospitals Table
IF OBJECT_ID('dbo.hospitals', 'U') IS NOT NULL
BEGIN
    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.hospitals') AND name = 'hospital_type_id')
    BEGIN
        ALTER TABLE [dbo].[hospitals] ADD [hospital_type_id] INT NULL;
        PRINT 'Added column hospital_type_id to hospitals';
    END

    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.hospitals') AND name = 'hospital_type')
    BEGIN
        ALTER TABLE [dbo].[hospitals] ADD [hospital_type] NVARCHAR(255) NULL;
        PRINT 'Added column hospital_type to hospitals';
    END

    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.hospitals') AND name = 'specialties')
    BEGIN
        ALTER TABLE [dbo].[hospitals] ADD [specialties] NVARCHAR(MAX) NULL;
        PRINT 'Added column specialties to hospitals';
    END

    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.hospitals') AND name = 'facilities')
    BEGIN
        ALTER TABLE [dbo].[hospitals] ADD [facilities] NVARCHAR(MAX) NULL;
        PRINT 'Added column facilities to hospitals';
    END

    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.hospitals') AND name = 'emergency_services')
    BEGIN
        ALTER TABLE [dbo].[hospitals] ADD [emergency_services] BIT DEFAULT 1;
        PRINT 'Added column emergency_services to hospitals';
    END

    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.hospitals') AND name = 'about')
    BEGIN
        ALTER TABLE [dbo].[hospitals] ADD [about] NVARCHAR(MAX) NULL;
        PRINT 'Added column about to hospitals';
    END

    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.hospitals') AND name = 'latitude')
    BEGIN
        ALTER TABLE [dbo].[hospitals] ADD [latitude] FLOAT NULL;
        PRINT 'Added column latitude to hospitals';
    END

    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.hospitals') AND name = 'longitude')
    BEGIN
        ALTER TABLE [dbo].[hospitals] ADD [longitude] FLOAT NULL;
        PRINT 'Added column longitude to hospitals';
    END

    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.hospitals') AND name = 'emergency_phone')
    BEGIN
        ALTER TABLE [dbo].[hospitals] ADD [emergency_phone] NVARCHAR(50) NULL;
        PRINT 'Added column emergency_phone to hospitals';
    END

    IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('dbo.hospitals') AND name = 'ambulance_phone')
    BEGIN
        ALTER TABLE [dbo].[hospitals] ADD [ambulance_phone] NVARCHAR(50) NULL;
        PRINT 'Added column ambulance_phone to hospitals';
    END
END
GO

-- 4. Seed Standard 18 Hospital Categories + Other Category
IF EXISTS (SELECT * FROM sysobjects WHERE name='hospital_types' AND xtype='U')
BEGIN
    MERGE INTO [dbo].[hospital_types] AS Target
    USING (VALUES
        (1, N'General Hospital', 'general-hospital', N'Provides treatment for common medical conditions', 'fa-solid fa-hospital', 'emerald', 'bg-emerald-50', 'text-emerald-700', 'border-emerald-200', 1),
        (2, N'Multispecialty Hospital', 'multispecialty-hospital', N'Offers multiple medical departments', 'fa-solid fa-square-h', 'teal', 'bg-teal-50', 'text-teal-700', 'border-teal-200', 1),
        (3, N'Super Specialty Hospital', 'super-specialty-hospital', N'Focuses on advanced specialized treatments', 'fa-solid fa-star-of-life', 'blue', 'bg-blue-50', 'text-blue-700', 'border-blue-200', 1),
        (4, N'Cardiology Hospital', 'cardiology-hospital', N'Heart and cardiovascular treatment', 'fa-solid fa-heart-pulse', 'rose', 'bg-rose-50', 'text-rose-700', 'border-rose-200', 1),
        (5, N'Oncology Hospital', 'oncology-hospital', N'Cancer diagnosis and treatment', 'fa-solid fa-ribbon', 'purple', 'bg-purple-50', 'text-purple-700', 'border-purple-200', 1),
        (6, N'Neurology Hospital', 'neurology-hospital', N'Brain and nervous system treatment', 'fa-solid fa-brain', 'indigo', 'bg-indigo-50', 'text-indigo-700', 'border-indigo-200', 1),
        (7, N'Orthopedic Hospital', 'orthopedic-hospital', N'Bone, joint, and spine treatment', 'fa-solid fa-bone', 'amber', 'bg-amber-50', 'text-amber-800', 'border-amber-200', 1),
        (8, N'Maternity Hospital', 'maternity-hospital', N'Pregnancy, childbirth, and women''s care', 'fa-solid fa-person-pregnant', 'pink', 'bg-pink-50', 'text-pink-700', 'border-pink-200', 1),
        (9, N'Pediatric Hospital', 'pediatric-hospital', N'Medical care for infants and children', 'fa-solid fa-baby', 'cyan', 'bg-cyan-50', 'text-cyan-800', 'border-cyan-200', 1),
        (10, N'Psychiatric Hospital', 'psychiatric-hospital', N'Mental health treatment', 'fa-solid fa-head-side-virus', 'violet', 'bg-violet-50', 'text-violet-700', 'border-violet-200', 1),
        (11, N'Eye Hospital', 'eye-hospital', N'Ophthalmology and vision care', 'fa-solid fa-eye', 'sky', 'bg-sky-50', 'text-sky-700', 'border-sky-200', 1),
        (12, N'Dental Hospital', 'dental-hospital', N'Oral and dental treatment', 'fa-solid fa-tooth', 'emerald', 'bg-emerald-50', 'text-emerald-700', 'border-emerald-200', 1),
        (13, N'ENT Hospital', 'ent-hospital', N'Ear, nose, and throat treatment', 'fa-solid fa-ear-listen', 'teal', 'bg-teal-50', 'text-teal-700', 'border-teal-200', 1),
        (14, N'Nephrology Hospital', 'nephrology-hospital', N'Kidney-related treatment', 'fa-solid fa-shield-virus', 'orange', 'bg-orange-50', 'text-orange-800', 'border-orange-200', 1),
        (15, N'Rehabilitation Hospital', 'rehabilitation-hospital', N'Physical recovery and rehabilitation', 'fa-solid fa-wheelchair', 'green', 'bg-green-50', 'text-green-800', 'border-green-200', 1),
        (16, N'Infectious Disease Hospital', 'infectious-disease-hospital', N'Treatment of infectious diseases', 'fa-solid fa-virus-covid', 'red', 'bg-red-50', 'text-red-700', 'border-red-200', 1),
        (17, N'Burns and Plastic Surgery Hospital', 'burns-plastic-surgery-hospital', N'Burn care and reconstructive surgery', 'fa-solid fa-fire-flame-curved', 'amber', 'bg-amber-50', 'text-amber-800', 'border-amber-200', 1),
        (18, N'Emergency and Trauma Hospital', 'emergency-trauma-hospital', N'Emergency injuries and critical care', 'fa-solid fa-truck-medical', 'red', 'bg-red-50', 'text-red-700', 'border-red-200', 1),
        (19, N'Other', 'other', N'Specialized or custom medical facility', 'fa-solid fa-clinic-medical', 'slate', 'bg-slate-100', 'text-slate-700', 'border-slate-300', 1)
    ) AS Source ([id], [name], [slug], [description], [icon], [color], [badge_bg], [badge_text], [badge_border], [is_active])
    ON Target.[id] = Source.[id]
    WHEN MATCHED THEN
        UPDATE SET
            Target.[name] = Source.[name],
            Target.[slug] = Source.[slug],
            Target.[description] = Source.[description],
            Target.[icon] = Source.[icon],
            Target.[color] = Source.[color],
            Target.[badge_bg] = Source.[badge_bg],
            Target.[badge_text] = Source.[badge_text],
            Target.[badge_border] = Source.[badge_border],
            Target.[is_active] = Source.[is_active]
    WHEN NOT MATCHED THEN
        INSERT ([id], [name], [slug], [description], [icon], [color], [badge_bg], [badge_text], [badge_border], [is_active], [created_at])
        VALUES (Source.[id], Source.[name], Source.[slug], Source.[description], Source.[icon], Source.[color], Source.[badge_bg], Source.[badge_text], Source.[badge_border], Source.[is_active], GETDATE());
    
    PRINT 'Seeded / updated 19 master hospital types';
END
GO

-- 5. Assign Default Hospital Types to Existing Records
IF OBJECT_ID('dbo.hospitals', 'U') IS NOT NULL
BEGIN
    UPDATE [dbo].[hospitals]
    SET [hospital_type_id] = 2, [hospital_type] = N'Multispecialty Hospital'
    WHERE [hospital_type_id] IS NULL AND ([name] LIKE '%Super%' OR [name] LIKE '%Multi%' OR [name] LIKE '%Apollo%' OR [name] LIKE '%Fortis%' OR [name] LIKE '%Max%' OR [name] LIKE '%Memorial%');

    UPDATE [dbo].[hospitals]
    SET [hospital_type_id] = 4, [hospital_type] = N'Cardiology Hospital'
    WHERE [hospital_type_id] IS NULL AND ([name] LIKE '%Cardio%' OR [name] LIKE '%Heart%');

    UPDATE [dbo].[hospitals]
    SET [hospital_type_id] = 5, [hospital_type] = N'Oncology Hospital'
    WHERE [hospital_type_id] IS NULL AND ([name] LIKE '%Cancer%' OR [name] LIKE '%Onco%');

    UPDATE [dbo].[hospitals]
    SET [hospital_type_id] = 1, [hospital_type] = N'General Hospital'
    WHERE [hospital_type_id] IS NULL;

    UPDATE [dbo].[hospitals]
    SET [emergency_services] = 1
    WHERE [emergency_services] IS NULL;

    PRINT 'Updated existing hospital classifications';
END
GO

-- 6. Create Performance Indexes
IF OBJECT_ID('dbo.hospitals', 'U') IS NOT NULL
BEGIN
    IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_hospitals_type_id' AND object_id = OBJECT_ID('dbo.hospitals'))
    BEGIN
        CREATE NONCLUSTERED INDEX [IX_hospitals_type_id] ON [dbo].[hospitals]([hospital_type_id]);
        PRINT 'Created index IX_hospitals_type_id';
    END

    IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_hospitals_city_state' AND object_id = OBJECT_ID('dbo.hospitals'))
    BEGIN
        CREATE NONCLUSTERED INDEX [IX_hospitals_city_state] ON [dbo].[hospitals]([city], [state]);
        PRINT 'Created index IX_hospitals_city_state';
    END

    IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_hospitals_verified_emergency' AND object_id = OBJECT_ID('dbo.hospitals'))
    BEGIN
        CREATE NONCLUSTERED INDEX [IX_hospitals_verified_emergency] ON [dbo].[hospitals]([is_verified], [emergency_services]);
        PRINT 'Created index IX_hospitals_verified_emergency';
    END
END
GO

PRINT 'Hospital classification migration completed successfully.';
GO
