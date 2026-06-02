CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMPTZ NULL,

    CONSTRAINT chk_users_role CHECK (
        role IN ('PATIENT', 'DOCTOR', 'ADMIN', 'AUDITOR')
    ),

    CONSTRAINT chk_users_status CHECK (
        status IN ('ACTIVE', 'DISABLED', 'PENDING')
    )
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);


CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NULL,
    synthea_patient_id VARCHAR(100) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    gender VARCHAR(20) NULL,
    birth_date DATE NULL,
    phone VARCHAR(50) NULL,
    address TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_patients_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_patients_user_id ON patients(user_id);
CREATE INDEX IF NOT EXISTS idx_patients_synthea_patient_id ON patients(synthea_patient_id);

CREATE TABLE IF NOT EXISTS medical_records (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    source VARCHAR(30) NOT NULL DEFAULT 'SYNTHEA',
    record_type VARCHAR(50) NOT NULL DEFAULT 'FHIR_SUMMARY',
    encrypted_data TEXT NOT NULL,
    nonce VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_medical_records_patient
        FOREIGN KEY (patient_id)
        REFERENCES patients(id)
);

CREATE INDEX IF NOT EXISTS idx_medical_records_patient_id ON medical_records(patient_id);
CREATE INDEX IF NOT EXISTS idx_medical_records_source ON medical_records(source);

CREATE TABLE IF NOT EXISTS doctors (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(100) NULL,
    license_no VARCHAR(50) NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_doctors_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_doctors_user_id ON doctors(user_id);

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
    revoked_at TIMESTAMPTZ NULL,

    CONSTRAINT fk_consents_patient
        FOREIGN KEY (patient_id)
        REFERENCES patients(id),
    CONSTRAINT fk_consents_doctor
        FOREIGN KEY (doctor_id)
        REFERENCES users(id),
    CONSTRAINT chk_consents_status CHECK (
        status IN ('ACTIVE', 'PENDING', 'REJECTED', 'REVOKED')
    ),
    CONSTRAINT chk_consents_record_scope CHECK (
        record_scope IN ('DEFAULT', 'EXTRA')
    )
);

CREATE INDEX IF NOT EXISTS idx_consents_patient_id ON consents(patient_id);
CREATE INDEX IF NOT EXISTS idx_consents_doctor_id ON consents(doctor_id);
CREATE INDEX IF NOT EXISTS idx_consents_status ON consents(status);

CREATE TABLE IF NOT EXISTS access_logs (
    id SERIAL PRIMARY KEY,
    doctor_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    consent_id INTEGER NULL,
    action VARCHAR(20) NOT NULL,
    record_scope VARCHAR(20) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_access_logs_doctor
        FOREIGN KEY (doctor_id)
        REFERENCES users(id),
    CONSTRAINT fk_access_logs_patient
        FOREIGN KEY (patient_id)
        REFERENCES patients(id),
    CONSTRAINT fk_access_logs_consent
        FOREIGN KEY (consent_id)
        REFERENCES consents(id)
);

CREATE INDEX IF NOT EXISTS idx_access_logs_doctor_id ON access_logs(doctor_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_patient_id ON access_logs(patient_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_created_at ON access_logs(created_at);

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
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    previous_hash VARCHAR(64) NULL,
    current_hash VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_user_id ON audit_logs(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_patient_id ON audit_logs(patient_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_doctor_id ON audit_logs(doctor_id);
