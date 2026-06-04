INSERT INTO doctors (user_id, name, department, license_no, note, verified)
SELECT id, 'Dr. General Medicine', 'General Medicine', 'DOC-GEN-001', 'demo general medicine doctor', TRUE
FROM users
WHERE username = 'doctor1'
AND NOT EXISTS (
    SELECT 1 FROM doctors WHERE user_id = users.id
);

UPDATE doctors
SET
    name = 'Dr. General Medicine',
    department = 'General Medicine',
    license_no = 'DOC-GEN-001',
    note = 'demo general medicine doctor',
    verified = TRUE
WHERE user_id = (
    SELECT id FROM users WHERE username = 'doctor1'
);

INSERT INTO doctors (user_id, name, department, license_no, note, verified)
SELECT u.id, spec.name, spec.department, spec.license_no, spec.note, TRUE
FROM users u
JOIN (
    VALUES
        ('doctor2', 'Dr. Internal Medicine', 'Internal Medicine', 'DOC-INT-001', 'demo internal medicine doctor'),
        ('doctor3', 'Dr. Surgery', 'Surgery', 'DOC-SURG-001', 'demo surgery doctor'),
        ('doctor4', 'Dr. Pediatrics', 'Pediatrics', 'DOC-PED-001', 'demo pediatrics doctor'),
        ('doctor5', 'Dr. Obstetrics and Gynecology', 'Obstetrics and Gynecology', 'DOC-OBGYN-001', 'demo obstetrics and gynecology doctor'),
        ('doctor6', 'Dr. Rehabilitation and Preventive Care', 'Rehabilitation and Preventive Care', 'DOC-REHAB-001', 'demo rehabilitation and preventive care doctor'),
        ('doctor7', 'Dr. Dentistry', 'Dentistry', 'DOC-DENT-001', 'demo dentistry doctor'),
        ('doctor8', 'Dr. Mental Health', 'Mental Health', 'DOC-MENTAL-001', 'demo mental health doctor')
) AS spec(username, name, department, license_no, note)
ON spec.username = u.username
WHERE NOT EXISTS (
    SELECT 1 FROM doctors d WHERE d.user_id = u.id
);

UPDATE doctors
SET
    name = spec.name,
    department = spec.department,
    license_no = spec.license_no,
    note = spec.note,
    verified = TRUE
FROM (
    VALUES
        ('doctor2', 'Dr. Internal Medicine', 'Internal Medicine', 'DOC-INT-001', 'demo internal medicine doctor'),
        ('doctor3', 'Dr. Surgery', 'Surgery', 'DOC-SURG-001', 'demo surgery doctor'),
        ('doctor4', 'Dr. Pediatrics', 'Pediatrics', 'DOC-PED-001', 'demo pediatrics doctor'),
        ('doctor5', 'Dr. Obstetrics and Gynecology', 'Obstetrics and Gynecology', 'DOC-OBGYN-001', 'demo obstetrics and gynecology doctor'),
        ('doctor6', 'Dr. Rehabilitation and Preventive Care', 'Rehabilitation and Preventive Care', 'DOC-REHAB-001', 'demo rehabilitation and preventive care doctor'),
        ('doctor7', 'Dr. Dentistry', 'Dentistry', 'DOC-DENT-001', 'demo dentistry doctor'),
        ('doctor8', 'Dr. Mental Health', 'Mental Health', 'DOC-MENTAL-001', 'demo mental health doctor')
) AS spec(username, name, department, license_no, note)
JOIN users u ON u.username = spec.username
WHERE doctors.user_id = u.id;

INSERT INTO consents (
    patient_id,
    doctor_id,
    record_scope,
    permission,
    status,
    consent_source,
    default_scope,
    start_time,
    end_time,
    created_at,
    auto_granted_at
)
SELECT
    p.id,
    u.id,
    'DEFAULT',
    'READ',
    'ACTIVE',
    'DEFAULT_CLINICAL',
    'DEFAULT_CLINICAL',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP + interval '14 days',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM patients p
CROSS JOIN users u
WHERE p.user_id = (
    SELECT id FROM users WHERE username = 'patient1'
)
AND u.username = 'doctor1'
AND NOT EXISTS (
    SELECT 1
    FROM consents c
    WHERE c.patient_id = p.id
    AND c.doctor_id = u.id
    AND c.record_scope = 'DEFAULT'
);

UPDATE consents
SET
    permission = 'READ',
    status = 'ACTIVE',
    consent_source = 'DEFAULT_CLINICAL',
    default_scope = 'DEFAULT_CLINICAL',
    start_time = COALESCE(start_time, CURRENT_TIMESTAMP),
    end_time = CURRENT_TIMESTAMP + interval '14 days',
    revoked_at = NULL,
    auto_granted_at = COALESCE(auto_granted_at, CURRENT_TIMESTAMP)
WHERE patient_id = (
    SELECT p.id
    FROM patients p
    JOIN users u ON u.id = p.user_id
    WHERE u.username = 'patient1'
)
AND doctor_id = (
    SELECT id FROM users WHERE username = 'doctor1'
)
AND record_scope = 'DEFAULT';
