from sqlalchemy import text

from app.db.session import engine


def ensure_audit_schema() -> None:
    create_doctors = """
    CREATE TABLE IF NOT EXISTS doctors (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        name VARCHAR(100) NOT NULL,
        department VARCHAR(100) NULL,
        license_no VARCHAR(50) NULL,
        note TEXT NULL,
        verified BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """

    create_consents = """
    CREATE TABLE IF NOT EXISTS consents (
        id SERIAL PRIMARY KEY,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        record_scope VARCHAR(20) NOT NULL,
        permission VARCHAR(50) NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
        request_reason TEXT NULL,
        approve_note TEXT NULL,
        consent_source VARCHAR(30) NOT NULL,
        default_scope VARCHAR(20) NULL,
        start_time TIMESTAMPTZ NULL,
        end_time TIMESTAMPTZ NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        auto_granted_at TIMESTAMPTZ NULL,
        approved_at TIMESTAMPTZ NULL,
        revoked_at TIMESTAMPTZ NULL
    )
    """

    create_access_logs = """
    CREATE TABLE IF NOT EXISTS access_logs (
        id SERIAL PRIMARY KEY,
        doctor_id INTEGER NOT NULL,
        patient_id INTEGER NOT NULL,
        consent_id INTEGER NULL,
        action VARCHAR(20) NOT NULL,
        record_scope VARCHAR(20) NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """

    create_audit_logs = """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        actor_user_id INTEGER NULL,
        actor_role VARCHAR(20) NULL,
        actor_username VARCHAR(50) NULL,
        action VARCHAR(50) NOT NULL,
        target_type VARCHAR(50) NULL,
        target_id INTEGER NULL,
        doctor_id INTEGER NULL,
        patient_id INTEGER NULL,
        consent_id INTEGER NULL,
        record_scope VARCHAR(20) NULL,
        outcome VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
        detail TEXT NULL,
        ip_address VARCHAR(64) NULL,
        user_agent TEXT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        previous_hash VARCHAR(64) NULL,
        current_hash VARCHAR(64) NOT NULL
    )
    """

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_doctors_user_id ON doctors(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_consents_patient_id ON consents(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_consents_doctor_id ON consents(doctor_id)",
        "CREATE INDEX IF NOT EXISTS idx_consents_status ON consents(status)",
        "CREATE INDEX IF NOT EXISTS idx_access_logs_doctor_id ON access_logs(doctor_id)",
        "CREATE INDEX IF NOT EXISTS idx_access_logs_patient_id ON access_logs(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_access_logs_created_at ON access_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_user_id ON audit_logs(actor_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_patient_id ON audit_logs(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_doctor_id ON audit_logs(doctor_id)",
    ]

    with engine.begin() as connection:
        connection.execute(text(create_doctors))
        has_doctor_note = connection.execute(
            text(
                "SELECT 1 FROM pg_attribute "
                "WHERE attrelid = 'doctors'::regclass "
                "AND attname = 'note' "
                "AND NOT attisdropped"
            )
        ).first()
        if has_doctor_note is None:
            connection.execute(text("ALTER TABLE doctors ADD COLUMN note TEXT NULL"))
        connection.execute(text(create_consents))
        connection.execute(
            text(
                "UPDATE consents "
                "SET end_time = COALESCE(start_time, approved_at, auto_granted_at, created_at) + interval '14 days' "
                "WHERE status = 'ACTIVE' AND end_time IS NULL"
            )
        )
        connection.execute(text(create_access_logs))
        connection.execute(text(create_audit_logs))
        for column_name, column_type in [
            ("ip_address", "VARCHAR(64) NULL"),
            ("user_agent", "TEXT NULL"),
        ]:
            has_column = connection.execute(
                text(
                    "SELECT 1 FROM pg_attribute "
                    "WHERE attrelid = 'audit_logs'::regclass "
                    "AND attname = :column_name "
                    "AND NOT attisdropped"
                ),
                {"column_name": column_name},
            ).first()
            if has_column is None:
                connection.execute(
                    text(f"ALTER TABLE audit_logs ADD COLUMN {column_name} {column_type}")
                )
        for statement in indexes:
            connection.execute(text(statement))
