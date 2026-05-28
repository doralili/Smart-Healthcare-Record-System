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
