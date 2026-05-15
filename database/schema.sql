CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP NULL,

    CONSTRAINT chk_users_role CHECK (
        role IN ('PATIENT', 'DOCTOR', 'ADMIN', 'AUDITOR')
    ),

    CONSTRAINT chk_users_status CHECK (
        status IN ('ACTIVE', 'DISABLED', 'PENDING')
    )
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
