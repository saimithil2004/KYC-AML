"""
Schema Helper — Phase 10
========================
Provides dynamic schema verification and auto-migration helper
to ensure regulations and policy_rules have extended columns and
the regulation_versions table exists.
Supports both PostgreSQL and SQLite dialects.
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def ensure_phase10_schema(db: AsyncSession):
    """Executes DDL statements to ensure all Phase 10 columns and tables exist."""
    try:
        bind = db.bind
        dialect_name = bind.dialect.name
        
        # 1. REGULATIONS Table Extension
        reg_cols = [
            ("description", "TEXT"),
            ("country", "VARCHAR(100)"),
            ("jurisdiction", "VARCHAR(100)"),
            ("regulator", "VARCHAR(100)"),
            ("regulation_type", "VARCHAR(100)"),
            ("version", "VARCHAR(50) DEFAULT '1.0.0'"),
            ("effective_date", "DATE"),
            ("expiry_date", "DATE"),
            ("status", "VARCHAR(50) DEFAULT 'active'"),
            ("extracted_text", "TEXT"),
            ("document_metadata", "JSONB" if dialect_name == "postgresql" else "TEXT")
        ]
        
        for col_name, col_type in reg_cols:
            try:
                if dialect_name == "sqlite":
                    await db.execute(text(f"ALTER TABLE regulations ADD COLUMN {col_name} {col_type}"))
                else:
                    await db.execute(text(f"ALTER TABLE regulations ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
            except Exception as e:
                # Alter column might already exist, which is fine
                pass

        # 2. POLICY_RULES Table Extension
        rule_cols = [
            ("severity", "VARCHAR(50) DEFAULT 'medium'"),
            ("description", "TEXT"),
            ("expression", "TEXT"),
            ("threshold", "NUMERIC(15,4)"),
            ("country", "VARCHAR(100)"),
            ("version", "VARCHAR(50) DEFAULT '1.0.0'")
        ]
        
        for col_name, col_type in rule_cols:
            try:
                if dialect_name == "sqlite":
                    await db.execute(text(f"ALTER TABLE policy_rules ADD COLUMN {col_name} {col_type}"))
                else:
                    await db.execute(text(f"ALTER TABLE policy_rules ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
            except Exception as e:
                pass

        # 3. REGULATION_VERSIONS Table Creation
        if dialect_name == "postgresql":
            create_versions_table = """
            CREATE TABLE IF NOT EXISTS regulation_versions (
                id UUID PRIMARY KEY,
                regulation_id UUID NOT NULL REFERENCES regulations(id) ON DELETE CASCADE,
                version VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                extracted_text TEXT NOT NULL,
                rules_snapshot JSONB NOT NULL,
                change_description TEXT,
                author_id UUID REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_versions_table = """
            CREATE TABLE IF NOT EXISTS regulation_versions (
                id VARCHAR(36) PRIMARY KEY,
                regulation_id VARCHAR(36) NOT NULL,
                version VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                extracted_text TEXT NOT NULL,
                rules_snapshot TEXT NOT NULL,
                change_description TEXT,
                author_id VARCHAR(36),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        await db.execute(text(create_versions_table))
        await db.commit()
    except Exception as exc:
        logger.error(f"Error ensuring Phase 10 schema: {exc}")
        # Rollback in case of errors
        await db.rollback()


async def ensure_phase11_schema(db: AsyncSession):
    """Executes DDL statements to ensure all Phase 11 monitoring tables exist."""
    try:
        bind = db.bind
        dialect_name = bind.dialect.name

        # 1. MONITORING_JOBS Table Creation
        if dialect_name == "postgresql":
            create_jobs_table = """
            CREATE TABLE IF NOT EXISTS monitoring_jobs (
                id UUID PRIMARY KEY,
                customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                status VARCHAR(50) NOT NULL DEFAULT 'queued',
                trigger_reason VARCHAR(100) NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0,
                execution_time_ms INTEGER,
                worker_name VARCHAR(100),
                error_message TEXT,
                case_id UUID REFERENCES cases(id) ON DELETE SET NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_jobs_table = """
            CREATE TABLE IF NOT EXISTS monitoring_jobs (
                id VARCHAR(36) PRIMARY KEY,
                customer_id VARCHAR(36) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'queued',
                trigger_reason VARCHAR(100) NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0,
                execution_time_ms INTEGER,
                worker_name VARCHAR(100),
                error_message TEXT,
                case_id VARCHAR(36),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        # 2. MONITORING_HISTORY Table Creation
        if dialect_name == "postgresql":
            create_history_table = """
            CREATE TABLE IF NOT EXISTS monitoring_history (
                id UUID PRIMARY KEY,
                customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                screening_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                trigger_reason VARCHAR(100) NOT NULL,
                old_score NUMERIC(5, 2) NOT NULL,
                new_score NUMERIC(5, 2) NOT NULL,
                old_decision VARCHAR(50) NOT NULL,
                new_decision VARCHAR(50) NOT NULL,
                risk_delta NUMERIC(5, 2) NOT NULL,
                new_alerts_count INTEGER NOT NULL DEFAULT 0,
                resolved_alerts_count INTEGER NOT NULL DEFAULT 0,
                risk_trend VARCHAR(50) NOT NULL DEFAULT 'stable',
                agents_executed JSONB NOT NULL,
                execution_time_ms INTEGER NOT NULL DEFAULT 0,
                case_id UUID REFERENCES cases(id) ON DELETE SET NULL,
                risk_score_id UUID REFERENCES risk_scores(id) ON DELETE SET NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_history_table = """
            CREATE TABLE IF NOT EXISTS monitoring_history (
                id VARCHAR(36) PRIMARY KEY,
                customer_id VARCHAR(36) NOT NULL,
                screening_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trigger_reason VARCHAR(100) NOT NULL,
                old_score NUMERIC(5, 2) NOT NULL,
                new_score NUMERIC(5, 2) NOT NULL,
                old_decision VARCHAR(50) NOT NULL,
                new_decision VARCHAR(50) NOT NULL,
                risk_delta NUMERIC(5, 2) NOT NULL,
                new_alerts_count INTEGER NOT NULL DEFAULT 0,
                resolved_alerts_count INTEGER NOT NULL DEFAULT 0,
                risk_trend VARCHAR(50) NOT NULL DEFAULT 'stable',
                agents_executed TEXT NOT NULL,
                execution_time_ms INTEGER NOT NULL DEFAULT 0,
                case_id VARCHAR(36),
                risk_score_id VARCHAR(36),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        await db.execute(text(create_jobs_table))
        await db.execute(text(create_history_table))
        await db.commit()
    except Exception as exc:
        logger.error(f"Error ensuring Phase 11 schema: {exc}")
        await db.rollback()


async def ensure_phase12_schema(db: AsyncSession):
    """Executes DDL statements to ensure all Phase 12 investigation tables exist."""
    try:
        bind = db.bind
        dialect_name = bind.dialect.name

        # 1. INVESTIGATIONS Table Creation
        if dialect_name == "postgresql":
            create_investigations = """
            CREATE TABLE IF NOT EXISTS investigations (
                id UUID PRIMARY KEY,
                case_id UUID NOT NULL UNIQUE REFERENCES cases(id) ON DELETE CASCADE,
                customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
                assigned_supervisor_id UUID REFERENCES users(id) ON DELETE SET NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'open',
                risk_level VARCHAR(50) NOT NULL DEFAULT 'medium',
                ai_summary JSONB,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_investigations = """
            CREATE TABLE IF NOT EXISTS investigations (
                id VARCHAR(36) PRIMARY KEY,
                case_id VARCHAR(36) NOT NULL UNIQUE,
                customer_id VARCHAR(36) NOT NULL,
                assigned_to VARCHAR(36),
                assigned_supervisor_id VARCHAR(36),
                status VARCHAR(50) NOT NULL DEFAULT 'open',
                risk_level VARCHAR(50) NOT NULL DEFAULT 'medium',
                ai_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        # 2. EVIDENCES Table Creation
        if dialect_name == "postgresql":
            create_evidences = """
            CREATE TABLE IF NOT EXISTS evidences (
                id UUID PRIMARY KEY,
                investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
                file_name VARCHAR(255) NOT NULL,
                evidence_type VARCHAR(50) NOT NULL,
                file_path TEXT NOT NULL,
                description TEXT,
                uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
                timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                file_hash VARCHAR(64) NOT NULL
            );
            """
        else:
            create_evidences = """
            CREATE TABLE IF NOT EXISTS evidences (
                id VARCHAR(36) PRIMARY KEY,
                investigation_id VARCHAR(36) NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
                file_name VARCHAR(255) NOT NULL,
                evidence_type VARCHAR(50) NOT NULL,
                file_path TEXT NOT NULL,
                description TEXT,
                uploaded_by VARCHAR(36),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_hash VARCHAR(64) NOT NULL
            );
            """

        # 3. CASE_NOTES Table Creation
        if dialect_name == "postgresql":
            create_case_notes = """
            CREATE TABLE IF NOT EXISTS case_notes (
                id UUID PRIMARY KEY,
                investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
                author_id UUID REFERENCES users(id) ON DELETE SET NULL,
                note_text TEXT NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_case_notes = """
            CREATE TABLE IF NOT EXISTS case_notes (
                id VARCHAR(36) PRIMARY KEY,
                investigation_id VARCHAR(36) NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
                author_id VARCHAR(36),
                note_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        # 4. SARS Table Creation
        if dialect_name == "postgresql":
            create_sars = """
            CREATE TABLE IF NOT EXISTS sars (
                id UUID PRIMARY KEY,
                investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
                sar_number VARCHAR(50) NOT NULL UNIQUE,
                narrative TEXT NOT NULL,
                reason TEXT NOT NULL,
                risk_indicators JSONB NOT NULL,
                recommendation TEXT NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'draft',
                created_by UUID REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_sars = """
            CREATE TABLE IF NOT EXISTS sars (
                id VARCHAR(36) PRIMARY KEY,
                investigation_id VARCHAR(36) NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
                sar_number VARCHAR(50) NOT NULL UNIQUE,
                narrative TEXT NOT NULL,
                reason TEXT NOT NULL,
                risk_indicators TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'draft',
                created_by VARCHAR(36),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        # 5. TIMELINE_EVENTS Table Creation
        if dialect_name == "postgresql":
            create_timeline_events = """
            CREATE TABLE IF NOT EXISTS timeline_events (
                id UUID PRIMARY KEY,
                investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
                event_type VARCHAR(100) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
                timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_timeline_events = """
            CREATE TABLE IF NOT EXISTS timeline_events (
                id VARCHAR(36) PRIMARY KEY,
                investigation_id VARCHAR(36) NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
                event_type VARCHAR(100) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                actor_id VARCHAR(36),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        # 6. ASSIGNMENTS Table Creation
        if dialect_name == "postgresql":
            create_assignments = """
            CREATE TABLE IF NOT EXISTS assignments (
                id UUID PRIMARY KEY,
                investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
                assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
                assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'investigator',
                assigned_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_assignments = """
            CREATE TABLE IF NOT EXISTS assignments (
                id VARCHAR(36) PRIMARY KEY,
                investigation_id VARCHAR(36) NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
                assigned_by VARCHAR(36),
                assigned_to VARCHAR(36),
                role VARCHAR(50) NOT NULL DEFAULT 'investigator',
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        await db.execute(text(create_investigations))
        await db.execute(text(create_evidences))
        await db.execute(text(create_case_notes))
        await db.execute(text(create_sars))
        await db.execute(text(create_timeline_events))
        await db.execute(text(create_assignments))
        await db.commit()
    except Exception as exc:
        logger.error(f"Error ensuring Phase 12 schema: {exc}")
        await db.rollback()


async def ensure_phase13_schema(db: AsyncSession):
    """Executes DDL statements to ensure all Phase 13 tables exist."""
    try:
        bind = db.bind
        dialect_name = bind.dialect.name

        # 1. REPORT_TEMPLATES Table Creation
        if dialect_name == "postgresql":
            create_report_templates = """
            CREATE TABLE IF NOT EXISTS report_templates (
                id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                config JSONB NOT NULL,
                created_by UUID REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_report_templates = """
            CREATE TABLE IF NOT EXISTS report_templates (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                config TEXT NOT NULL,
                created_by VARCHAR(36),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        # 2. REPORTS Table Creation
        if dialect_name == "postgresql":
            create_reports = """
            CREATE TABLE IF NOT EXISTS reports (
                id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                template_id UUID REFERENCES report_templates(id) ON DELETE SET NULL,
                generated_by UUID REFERENCES users(id) ON DELETE SET NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                format VARCHAR(20) NOT NULL DEFAULT 'pdf',
                file_path VARCHAR(500),
                filters JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_reports = """
            CREATE TABLE IF NOT EXISTS reports (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                template_id VARCHAR(36) REFERENCES report_templates(id) ON DELETE SET NULL,
                generated_by VARCHAR(36),
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                format VARCHAR(20) NOT NULL DEFAULT 'pdf',
                file_path VARCHAR(500),
                filters TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        # 3. SCHEDULED_REPORTS Table Creation
        if dialect_name == "postgresql":
            create_scheduled_reports = """
            CREATE TABLE IF NOT EXISTS scheduled_reports (
                id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                template_id UUID NOT NULL REFERENCES report_templates(id) ON DELETE CASCADE,
                cron_expression VARCHAR(100) NOT NULL,
                next_run TIMESTAMP NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                created_by UUID REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_scheduled_reports = """
            CREATE TABLE IF NOT EXISTS scheduled_reports (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                template_id VARCHAR(36) NOT NULL REFERENCES report_templates(id) ON DELETE CASCADE,
                cron_expression VARCHAR(100) NOT NULL,
                next_run TIMESTAMP NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                created_by VARCHAR(36),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        # 4. REPORT_EXECUTIONS Table Creation
        if dialect_name == "postgresql":
            create_report_executions = """
            CREATE TABLE IF NOT EXISTS report_executions (
                id UUID PRIMARY KEY,
                schedule_id UUID NOT NULL REFERENCES scheduled_reports(id) ON DELETE CASCADE,
                report_id UUID REFERENCES reports(id) ON DELETE SET NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'success',
                error_message TEXT,
                executed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_report_executions = """
            CREATE TABLE IF NOT EXISTS report_executions (
                id VARCHAR(36) PRIMARY KEY,
                schedule_id VARCHAR(36) NOT NULL REFERENCES scheduled_reports(id) ON DELETE CASCADE,
                report_id VARCHAR(36) REFERENCES reports(id) ON DELETE SET NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'success',
                error_message TEXT,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        # 5. DASHBOARD_LAYOUTS Table Creation
        if dialect_name == "postgresql":
            create_dashboard_layouts = """
            CREATE TABLE IF NOT EXISTS dashboard_layouts (
                id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                is_default BOOLEAN DEFAULT FALSE,
                config JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            """
        else:
            create_dashboard_layouts = """
            CREATE TABLE IF NOT EXISTS dashboard_layouts (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                user_id VARCHAR(36),
                is_default BOOLEAN DEFAULT 0,
                config TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

        # 6. DASHBOARD_WIDGETS Table Creation
        if dialect_name == "postgresql":
            create_dashboard_widgets = """
            CREATE TABLE IF NOT EXISTS dashboard_widgets (
                id UUID PRIMARY KEY,
                layout_id UUID NOT NULL REFERENCES dashboard_layouts(id) ON DELETE CASCADE,
                widget_type VARCHAR(100) NOT NULL,
                title VARCHAR(255) NOT NULL,
                config JSONB NOT NULL,
                position_x INTEGER DEFAULT 0,
                position_y INTEGER DEFAULT 0,
                width INTEGER DEFAULT 3,
                height INTEGER DEFAULT 2
            );
            """
        else:
            create_dashboard_widgets = """
            CREATE TABLE IF NOT EXISTS dashboard_widgets (
                id VARCHAR(36) PRIMARY KEY,
                layout_id VARCHAR(36) NOT NULL REFERENCES dashboard_layouts(id) ON DELETE CASCADE,
                widget_type VARCHAR(100) NOT NULL,
                title VARCHAR(255) NOT NULL,
                config TEXT NOT NULL,
                position_x INTEGER DEFAULT 0,
                position_y INTEGER DEFAULT 0,
                width INTEGER DEFAULT 3,
                height INTEGER DEFAULT 2
            );
            """

        await db.execute(text(create_report_templates))
        await db.execute(text(create_reports))
        await db.execute(text(create_scheduled_reports))
        await db.execute(text(create_report_executions))
        await db.execute(text(create_dashboard_layouts))
        await db.execute(text(create_dashboard_widgets))
        await db.commit()
    except Exception as exc:
        logger.error(f"Error ensuring Phase 13 schema: {exc}")
        await db.rollback()


async def ensure_phase14_schema(db: AsyncSession):
    """Executes DDL statements to ensure all Phase 14 external integration tables exist."""
    try:
        bind = db.bind
        dialect_name = bind.dialect.name
        pg = (dialect_name == "postgresql")
        uuid_type = "UUID" if pg else "VARCHAR(36)"
        json_type = "JSONB" if pg else "TEXT"
        ts_type = "TIMESTAMP WITHOUT TIME ZONE" if pg else "TIMESTAMP"
        now_expr = "NOW()" if pg else "CURRENT_TIMESTAMP"

        create_integration_settings = f"""
        CREATE TABLE IF NOT EXISTS integration_settings (
            id {uuid_type} PRIMARY KEY,
            provider_name VARCHAR(100) NOT NULL UNIQUE,
            provider_type VARCHAR(50) NOT NULL,
            base_url VARCHAR(500),
            api_key TEXT,
            api_secret TEXT,
            enabled BOOLEAN DEFAULT TRUE,
            timeout INTEGER DEFAULT 30,
            configuration {json_type} DEFAULT '{{}}',
            created_at {ts_type} DEFAULT {now_expr},
            updated_at {ts_type} DEFAULT {now_expr}
        );
        """

        create_sync_history = f"""
        CREATE TABLE IF NOT EXISTS sync_history (
            id {uuid_type} PRIMARY KEY,
            provider VARCHAR(100) NOT NULL,
            sync_type VARCHAR(50) NOT NULL,
            started_at {ts_type} DEFAULT {now_expr},
            completed_at {ts_type},
            records_processed INTEGER DEFAULT 0,
            records_added INTEGER DEFAULT 0,
            records_updated INTEGER DEFAULT 0,
            records_failed INTEGER DEFAULT 0,
            status VARCHAR(50) DEFAULT 'started',
            error_message TEXT
        );
        """

        create_notification_templates = f"""
        CREATE TABLE IF NOT EXISTS notification_templates (
            id {uuid_type} PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            event_type VARCHAR(100) NOT NULL,
            channel VARCHAR(50) NOT NULL,
            subject VARCHAR(500),
            body TEXT NOT NULL,
            variables {json_type} DEFAULT '[]',
            active BOOLEAN DEFAULT TRUE,
            created_at {ts_type} DEFAULT {now_expr},
            updated_at {ts_type} DEFAULT {now_expr}
        );
        """

        if pg:
            create_notifications = f"""
            CREATE TABLE IF NOT EXISTS notifications (
                id {uuid_type} PRIMARY KEY,
                user_id {uuid_type} REFERENCES users(id) ON DELETE SET NULL,
                template_id {uuid_type} REFERENCES notification_templates(id) ON DELETE SET NULL,
                channel VARCHAR(50) NOT NULL,
                title VARCHAR(500) NOT NULL,
                message TEXT NOT NULL,
                priority VARCHAR(20) DEFAULT 'medium',
                status VARCHAR(50) DEFAULT 'pending',
                sent_at {ts_type},
                retry_count INTEGER DEFAULT 0,
                metadata {json_type} DEFAULT '{{}}',
                created_at {ts_type} DEFAULT {now_expr}
            );
            """
        else:
            create_notifications = f"""
            CREATE TABLE IF NOT EXISTS notifications (
                id {uuid_type} PRIMARY KEY,
                user_id {uuid_type},
                template_id {uuid_type},
                channel VARCHAR(50) NOT NULL,
                title VARCHAR(500) NOT NULL,
                message TEXT NOT NULL,
                priority VARCHAR(20) DEFAULT 'medium',
                status VARCHAR(50) DEFAULT 'pending',
                sent_at {ts_type},
                retry_count INTEGER DEFAULT 0,
                metadata {json_type} DEFAULT '{{}}',
                created_at {ts_type} DEFAULT {now_expr}
            );
            """

        create_webhook_endpoints = f"""
        CREATE TABLE IF NOT EXISTS webhook_endpoints (
            id {uuid_type} PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            url VARCHAR(1000) NOT NULL,
            secret VARCHAR(500) NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            events {json_type} DEFAULT '[]',
            retries INTEGER DEFAULT 3,
            created_at {ts_type} DEFAULT {now_expr},
            updated_at {ts_type} DEFAULT {now_expr}
        );
        """

        if pg:
            create_webhook_logs = f"""
            CREATE TABLE IF NOT EXISTS webhook_logs (
                id {uuid_type} PRIMARY KEY,
                endpoint_id {uuid_type} NOT NULL REFERENCES webhook_endpoints(id) ON DELETE CASCADE,
                event VARCHAR(100) NOT NULL,
                payload {json_type} DEFAULT '{{}}',
                signature VARCHAR(256),
                response_code INTEGER,
                response_body TEXT,
                status VARCHAR(50) DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """
        else:
            create_webhook_logs = f"""
            CREATE TABLE IF NOT EXISTS webhook_logs (
                id {uuid_type} PRIMARY KEY,
                endpoint_id {uuid_type} NOT NULL,
                event VARCHAR(100) NOT NULL,
                payload {json_type} DEFAULT '{{}}',
                signature VARCHAR(256),
                response_code INTEGER,
                response_body TEXT,
                status VARCHAR(50) DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """

        await db.execute(text(create_integration_settings))
        await db.execute(text(create_sync_history))
        await db.execute(text(create_notification_templates))
        await db.execute(text(create_notifications))
        await db.execute(text(create_webhook_endpoints))
        await db.execute(text(create_webhook_logs))
        await db.commit()
        logger.info("Phase 14 schema verified/created successfully.")
    except Exception as exc:
        logger.error(f"Error ensuring Phase 14 schema: {exc}")
        await db.rollback()


async def ensure_phase15_schema(db: AsyncSession):
    """Executes DDL statements to ensure all Phase 15 security, observability, and caching tables exist."""
    try:
        bind = db.bind
        dialect_name = bind.dialect.name
        pg = (dialect_name == "postgresql")
        uuid_type = "UUID" if pg else "VARCHAR(36)"
        json_type = "JSONB" if pg else "TEXT"
        ts_type = "TIMESTAMP WITHOUT TIME ZONE" if pg else "TIMESTAMP"
        now_expr = "NOW()" if pg else "CURRENT_TIMESTAMP"

        # 1. Add User security columns
        user_cols = [
            ("failed_login_count", "INTEGER DEFAULT 0"),
            ("locked_until", ts_type),
            ("password_changed_at", f"{ts_type} DEFAULT {now_expr}"),
            ("last_login_at", ts_type),
            ("mfa_secret", "VARCHAR(500)")
        ]
        for col_name, col_type in user_cols:
            try:
                if pg:
                    await db.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                else:
                    await db.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
            except Exception:
                pass

        # 2. Login History Table
        create_login_history = f"""
        CREATE TABLE IF NOT EXISTS login_history (
            id {uuid_type} PRIMARY KEY,
            user_id {uuid_type},
            email VARCHAR(255),
            ip_address VARCHAR(45),
            user_agent VARCHAR(500),
            device_fingerprint VARCHAR(255),
            success BOOLEAN DEFAULT FALSE,
            failure_reason VARCHAR(200),
            country VARCHAR(100),
            created_at {ts_type} DEFAULT {now_expr}
        );
        """

        # 3. Revoked Tokens Table
        create_revoked_tokens = f"""
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            id {uuid_type} PRIMARY KEY,
            jti VARCHAR(255) NOT NULL UNIQUE,
            user_id {uuid_type},
            token_type VARCHAR(20) DEFAULT 'access',
            reason VARCHAR(200),
            revoked_at {ts_type} DEFAULT {now_expr},
            expires_at {ts_type}
        );
        """

        # 4. Password History Table
        create_password_history = f"""
        CREATE TABLE IF NOT EXISTS password_history (
            id {uuid_type} PRIMARY KEY,
            user_id {uuid_type} NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at {ts_type} DEFAULT {now_expr}
        );
        """

        # 5. MFA Settings Table
        create_mfa_settings = f"""
        CREATE TABLE IF NOT EXISTS mfa_settings (
            id {uuid_type} PRIMARY KEY,
            user_id {uuid_type} NOT NULL UNIQUE,
            enabled BOOLEAN DEFAULT FALSE,
            secret VARCHAR(500),
            backup_codes TEXT,
            setup_completed BOOLEAN DEFAULT FALSE,
            last_used_at {ts_type},
            created_at {ts_type} DEFAULT {now_expr},
            updated_at {ts_type} DEFAULT {now_expr}
        );
        """

        # 6. Security Events Table
        create_security_events = f"""
        CREATE TABLE IF NOT EXISTS security_events (
            id {uuid_type} PRIMARY KEY,
            event_type VARCHAR(100) NOT NULL,
            severity VARCHAR(20) DEFAULT 'medium',
            user_id {uuid_type},
            ip_address VARCHAR(45),
            description TEXT NOT NULL,
            metadata {json_type} DEFAULT '{{}}',
            resolved BOOLEAN DEFAULT FALSE,
            resolved_at {ts_type},
            created_at {ts_type} DEFAULT {now_expr}
        );
        """

        # 7. System Metrics Table
        create_system_metrics = f"""
        CREATE TABLE IF NOT EXISTS system_metrics (
            id {uuid_type} PRIMARY KEY,
            metric_name VARCHAR(100) NOT NULL,
            metric_value NUMERIC(20, 6) NOT NULL,
            unit VARCHAR(50),
            tags {json_type} DEFAULT '{{}}',
            timestamp {ts_type} DEFAULT {now_expr}
        );
        """

        # 8. Backup Records Table
        create_backup_records = f"""
        CREATE TABLE IF NOT EXISTS backup_records (
            id {uuid_type} PRIMARY KEY,
            backup_type VARCHAR(50) NOT NULL,
            file_path VARCHAR(1000) NOT NULL,
            file_name VARCHAR(500) NOT NULL,
            file_size_bytes INTEGER,
            sha256_checksum VARCHAR(64),
            status VARCHAR(50) DEFAULT 'pending',
            triggered_by VARCHAR(50) DEFAULT 'scheduled',
            error_message TEXT,
            compressed BOOLEAN DEFAULT TRUE,
            expires_at {ts_type},
            created_at {ts_type} DEFAULT {now_expr},
            completed_at {ts_type}
        );
        """

        # 9. Cache Statistics Table
        create_cache_statistics = f"""
        CREATE TABLE IF NOT EXISTS cache_statistics (
            id {uuid_type} PRIMARY KEY,
            backend VARCHAR(20) DEFAULT 'redis',
            hits INTEGER DEFAULT 0,
            misses INTEGER DEFAULT 0,
            sets INTEGER DEFAULT 0,
            deletes INTEGER DEFAULT 0,
            hit_rate NUMERIC(5, 2),
            recorded_at {ts_type} DEFAULT {now_expr}
        );
        """

        await db.execute(text(create_login_history))
        await db.execute(text(create_revoked_tokens))
        await db.execute(text(create_password_history))
        await db.execute(text(create_mfa_settings))
        await db.execute(text(create_security_events))
        await db.execute(text(create_system_metrics))
        await db.execute(text(create_backup_records))
        await db.execute(text(create_cache_statistics))
        await db.commit()
        logger.info("Phase 15 schema verified/created successfully.")
    except Exception as exc:
        logger.error(f"Error ensuring Phase 15 schema: {exc}")
        await db.rollback()


async def ensure_phase17_schema(db: AsyncSession):
    """Executes DDL statements to ensure all Phase 17 AI Governance & Explainability tables exist."""
    try:
        bind = db.bind
        dialect_name = bind.dialect.name
        pg = (dialect_name == "postgresql")
        uuid_type = "UUID" if pg else "VARCHAR(36)"
        json_type = "JSONB" if pg else "TEXT"
        ts_type = "TIMESTAMP WITHOUT TIME ZONE" if pg else "TIMESTAMP"
        now_expr = "NOW()" if pg else "CURRENT_TIMESTAMP"

        # 1. AI_MODELS
        create_ai_models = f"""
        CREATE TABLE IF NOT EXISTS ai_models (
            id {uuid_type} PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            provider VARCHAR(50) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at {ts_type} DEFAULT {now_expr},
            updated_at {ts_type} DEFAULT {now_expr}
        );
        """

        # 2. MODEL_VERSIONS
        if pg:
            create_model_versions = f"""
            CREATE TABLE IF NOT EXISTS model_versions (
                id {uuid_type} PRIMARY KEY,
                model_id {uuid_type} NOT NULL REFERENCES ai_models(id) ON DELETE CASCADE,
                version VARCHAR(50) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                metadata_json {json_type} DEFAULT '{{}}',
                created_at {ts_type} DEFAULT {now_expr}
            );
            """
        else:
            create_model_versions = f"""
            CREATE TABLE IF NOT EXISTS model_versions (
                id {uuid_type} PRIMARY KEY,
                model_id {uuid_type} NOT NULL,
                version VARCHAR(50) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                metadata_json {json_type} DEFAULT '{{}}',
                created_at {ts_type} DEFAULT {now_expr}
            );
            """

        # 3. PROMPT_TEMPLATES
        create_prompt_templates = f"""
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id {uuid_type} PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            created_at {ts_type} DEFAULT {now_expr},
            updated_at {ts_type} DEFAULT {now_expr}
        );
        """

        # 4. PROMPT_VERSIONS
        if pg:
            create_prompt_versions = f"""
            CREATE TABLE IF NOT EXISTS prompt_versions (
                id {uuid_type} PRIMARY KEY,
                template_id {uuid_type} NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
                version VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                is_active BOOLEAN DEFAULT FALSE,
                approved_status VARCHAR(50) DEFAULT 'pending',
                created_at {ts_type} DEFAULT {now_expr},
                updated_at {ts_type} DEFAULT {now_expr}
            );
            """
        else:
            create_prompt_versions = f"""
            CREATE TABLE IF NOT EXISTS prompt_versions (
                id {uuid_type} PRIMARY KEY,
                template_id {uuid_type} NOT NULL,
                version VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                is_active BOOLEAN DEFAULT FALSE,
                approved_status VARCHAR(50) DEFAULT 'pending',
                created_at {ts_type} DEFAULT {now_expr},
                updated_at {ts_type} DEFAULT {now_expr}
            );
            """

        # 5. AI_EXECUTIONS
        if pg:
            create_ai_executions = f"""
            CREATE TABLE IF NOT EXISTS ai_executions (
                id {uuid_type} PRIMARY KEY,
                model_version_id {uuid_type} REFERENCES model_versions(id) ON DELETE SET NULL,
                prompt_version_id {uuid_type} REFERENCES prompt_versions(id) ON DELETE SET NULL,
                customer_id {uuid_type} REFERENCES customers(id) ON DELETE SET NULL,
                case_id {uuid_type} REFERENCES cases(id) ON DELETE SET NULL,
                investigation_id {uuid_type} REFERENCES investigations(id) ON DELETE SET NULL,
                sar_id {uuid_type} REFERENCES sars(id) ON DELETE SET NULL,
                risk_score_id {uuid_type} REFERENCES risk_scores(id) ON DELETE SET NULL,
                monitoring_job_id {uuid_type} REFERENCES monitoring_jobs(id) ON DELETE SET NULL,
                report_id {uuid_type} REFERENCES reports(id) ON DELETE SET NULL,
                audit_log_id {uuid_type} REFERENCES audit_logs(id) ON DELETE SET NULL,
                prompt_content TEXT,
                response_content TEXT,
                cost NUMERIC(10, 6) DEFAULT 0.0,
                latency_ms INTEGER DEFAULT 0,
                tokens_used INTEGER DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """
        else:
            create_ai_executions = f"""
            CREATE TABLE IF NOT EXISTS ai_executions (
                id {uuid_type} PRIMARY KEY,
                model_version_id {uuid_type},
                prompt_version_id {uuid_type},
                customer_id {uuid_type},
                case_id {uuid_type},
                investigation_id {uuid_type},
                sar_id {uuid_type},
                risk_score_id {uuid_type},
                monitoring_job_id {uuid_type},
                report_id {uuid_type},
                audit_log_id {uuid_type},
                prompt_content TEXT,
                response_content TEXT,
                cost NUMERIC(10, 6) DEFAULT 0.0,
                latency_ms INTEGER DEFAULT 0,
                tokens_used INTEGER DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """

        # 6. AI_FEEDBACKS
        if pg:
            create_ai_feedbacks = f"""
            CREATE TABLE IF NOT EXISTS ai_feedbacks (
                id {uuid_type} PRIMARY KEY,
                execution_id {uuid_type} NOT NULL REFERENCES ai_executions(id) ON DELETE CASCADE,
                user_id {uuid_type} REFERENCES users(id) ON DELETE SET NULL,
                rating INTEGER DEFAULT 0,
                is_correct BOOLEAN DEFAULT TRUE,
                is_helpful BOOLEAN DEFAULT TRUE,
                comments TEXT,
                decision_override VARCHAR(50),
                escalation_reason TEXT,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """
        else:
            create_ai_feedbacks = f"""
            CREATE TABLE IF NOT EXISTS ai_feedbacks (
                id {uuid_type} PRIMARY KEY,
                execution_id {uuid_type} NOT NULL REFERENCES ai_executions(id) ON DELETE CASCADE,
                user_id {uuid_type},
                rating INTEGER DEFAULT 0,
                is_correct BOOLEAN DEFAULT TRUE,
                is_helpful BOOLEAN DEFAULT TRUE,
                comments TEXT,
                decision_override VARCHAR(50),
                escalation_reason TEXT,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """

        # 7. AI_EXPLANATIONS
        if pg:
            create_ai_explanations = f"""
            CREATE TABLE IF NOT EXISTS ai_explanations (
                id {uuid_type} PRIMARY KEY,
                execution_id {uuid_type} NOT NULL REFERENCES ai_executions(id) ON DELETE CASCADE,
                decision_summary TEXT NOT NULL,
                reasoning_tree {json_type} DEFAULT '{{}}',
                confidence NUMERIC(5, 2) DEFAULT 0.0,
                supporting_evidence TEXT,
                matched_rules TEXT,
                matched_entities TEXT,
                missing_evidence TEXT,
                recommended_actions TEXT,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """
        else:
            create_ai_explanations = f"""
            CREATE TABLE IF NOT EXISTS ai_explanations (
                id {uuid_type} PRIMARY KEY,
                execution_id {uuid_type} NOT NULL REFERENCES ai_executions(id) ON DELETE CASCADE,
                decision_summary TEXT NOT NULL,
                reasoning_tree {json_type} DEFAULT '{{}}',
                confidence NUMERIC(5, 2) DEFAULT 0.0,
                supporting_evidence TEXT,
                matched_rules TEXT,
                matched_entities TEXT,
                missing_evidence TEXT,
                recommended_actions TEXT,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """

        # 8. MODEL_EVALUATIONS
        if pg:
            create_model_evaluations = f"""
            CREATE TABLE IF NOT EXISTS model_evaluations (
                id {uuid_type} PRIMARY KEY,
                model_version_id {uuid_type} NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
                evaluator_name VARCHAR(100) NOT NULL,
                metrics_json {json_type} DEFAULT '{{}}',
                created_at {ts_type} DEFAULT {now_expr}
            );
            """
        else:
            create_model_evaluations = f"""
            CREATE TABLE IF NOT EXISTS model_evaluations (
                id {uuid_type} PRIMARY KEY,
                model_version_id {uuid_type} NOT NULL,
                evaluator_name VARCHAR(100) NOT NULL,
                metrics_json {json_type} DEFAULT '{{}}',
                created_at {ts_type} DEFAULT {now_expr}
            );
            """

        # 9. PROMPT_TESTS
        if pg:
            create_prompt_tests = f"""
            CREATE TABLE IF NOT EXISTS prompt_tests (
                id {uuid_type} PRIMARY KEY,
                prompt_version_id {uuid_type} NOT NULL REFERENCES prompt_versions(id) ON DELETE CASCADE,
                test_input TEXT NOT NULL,
                expected_output TEXT NOT NULL,
                actual_output TEXT,
                is_passed BOOLEAN DEFAULT FALSE,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """
        else:
            create_prompt_tests = f"""
            CREATE TABLE IF NOT EXISTS prompt_tests (
                id {uuid_type} PRIMARY KEY,
                prompt_version_id {uuid_type} NOT NULL,
                test_input TEXT NOT NULL,
                expected_output TEXT NOT NULL,
                actual_output TEXT,
                is_passed BOOLEAN DEFAULT FALSE,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """

        # 10. AI_POLICIES
        create_ai_policies = f"""
        CREATE TABLE IF NOT EXISTS ai_policies (
            id {uuid_type} PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            rules_json {json_type} DEFAULT '{{}}',
            is_active BOOLEAN DEFAULT TRUE,
            created_at {ts_type} DEFAULT {now_expr}
        );
        """

        # 11. AI_APPROVALS
        if pg:
            create_ai_approvals = f"""
            CREATE TABLE IF NOT EXISTS ai_approvals (
                id {uuid_type} PRIMARY KEY,
                prompt_version_id {uuid_type} NOT NULL REFERENCES prompt_versions(id) ON DELETE CASCADE,
                reviewer_id {uuid_type} REFERENCES users(id) ON DELETE SET NULL,
                status VARCHAR(50) NOT NULL,
                comments TEXT,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """
        else:
            create_ai_approvals = f"""
            CREATE TABLE IF NOT EXISTS ai_approvals (
                id {uuid_type} PRIMARY KEY,
                prompt_version_id {uuid_type} NOT NULL,
                reviewer_id {uuid_type},
                status VARCHAR(50) NOT NULL,
                comments TEXT,
                created_at {ts_type} DEFAULT {now_expr}
            );
            """

        # 12. AI_USAGE_STATISTICS
        create_ai_usage_statistics = f"""
        CREATE TABLE IF NOT EXISTS ai_usage_statistics (
            id {uuid_type} PRIMARY KEY,
            date DATE NOT NULL,
            model_name VARCHAR(100) NOT NULL,
            total_calls INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            total_cost NUMERIC(10, 6) DEFAULT 0.0,
            average_latency_ms NUMERIC(10, 2) DEFAULT 0.0
        );
        """

        # Run creation queries
        await db.execute(text(create_ai_models))
        await db.execute(text(create_model_versions))
        await db.execute(text(create_prompt_templates))
        await db.execute(text(create_prompt_versions))
        await db.execute(text(create_ai_executions))
        await db.execute(text(create_ai_feedbacks))
        await db.execute(text(create_ai_explanations))
        await db.execute(text(create_model_evaluations))
        await db.execute(text(create_prompt_tests))
        await db.execute(text(create_ai_policies))
        await db.execute(text(create_ai_approvals))
        await db.execute(text(create_ai_usage_statistics))
        await db.commit()
        logger.info("Phase 17 schema verified/created successfully.")
    except Exception as exc:
        logger.error(f"Error ensuring Phase 17 schema: {exc}")
        await db.rollback()



