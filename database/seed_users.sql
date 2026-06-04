INSERT INTO users (username, password_hash, role, status)
SELECT 'patient1', '$2b$12$8aajshsOHGKQ5hP9kPRLB.HEekSAcJZvYjUZSpI43dQYUJmQCuPmG', 'PATIENT', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'patient1');

INSERT INTO users (username, password_hash, role, status)
SELECT 'patient2', '$2b$12$8aajshsOHGKQ5hP9kPRLB.HEekSAcJZvYjUZSpI43dQYUJmQCuPmG', 'PATIENT', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'patient2');

INSERT INTO users (username, password_hash, role, status)
SELECT 'patient3', '$2b$12$8aajshsOHGKQ5hP9kPRLB.HEekSAcJZvYjUZSpI43dQYUJmQCuPmG', 'PATIENT', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'patient3');

INSERT INTO users (username, password_hash, role, status)
SELECT 'patient4', '$2b$12$8aajshsOHGKQ5hP9kPRLB.HEekSAcJZvYjUZSpI43dQYUJmQCuPmG', 'PATIENT', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'patient4');

INSERT INTO users (username, password_hash, role, status)
SELECT 'patient5', '$2b$12$8aajshsOHGKQ5hP9kPRLB.HEekSAcJZvYjUZSpI43dQYUJmQCuPmG', 'PATIENT', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'patient5');

INSERT INTO users (username, password_hash, role, status)
SELECT 'patient6', '$2b$12$8aajshsOHGKQ5hP9kPRLB.HEekSAcJZvYjUZSpI43dQYUJmQCuPmG', 'PATIENT', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'patient6');

INSERT INTO users (username, password_hash, role, status)
SELECT 'patient7', '$2b$12$8aajshsOHGKQ5hP9kPRLB.HEekSAcJZvYjUZSpI43dQYUJmQCuPmG', 'PATIENT', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'patient7');

INSERT INTO users (username, password_hash, role, status)
SELECT 'patient8', '$2b$12$8aajshsOHGKQ5hP9kPRLB.HEekSAcJZvYjUZSpI43dQYUJmQCuPmG', 'PATIENT', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'patient8');

INSERT INTO users (username, password_hash, role, status)
SELECT 'patient9', '$2b$12$8aajshsOHGKQ5hP9kPRLB.HEekSAcJZvYjUZSpI43dQYUJmQCuPmG', 'PATIENT', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'patient9');

INSERT INTO users (username, password_hash, role, status)
SELECT 'patient10', '$2b$12$8aajshsOHGKQ5hP9kPRLB.HEekSAcJZvYjUZSpI43dQYUJmQCuPmG', 'PATIENT', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'patient10');

INSERT INTO users (username, password_hash, role, status)
SELECT 'doctor1', '$2b$12$kR6LqRD9qZIsfwjY3.uQM.1qEvYejZYrNE7x2A1YIiVQrzur3KT9C', 'DOCTOR', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'doctor1');

INSERT INTO users (username, password_hash, role, status)
SELECT 'doctor2', '$2b$12$kR6LqRD9qZIsfwjY3.uQM.1qEvYejZYrNE7x2A1YIiVQrzur3KT9C', 'DOCTOR', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'doctor2');

INSERT INTO users (username, password_hash, role, status)
SELECT 'doctor3', '$2b$12$kR6LqRD9qZIsfwjY3.uQM.1qEvYejZYrNE7x2A1YIiVQrzur3KT9C', 'DOCTOR', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'doctor3');

INSERT INTO users (username, password_hash, role, status)
SELECT 'doctor4', '$2b$12$kR6LqRD9qZIsfwjY3.uQM.1qEvYejZYrNE7x2A1YIiVQrzur3KT9C', 'DOCTOR', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'doctor4');

INSERT INTO users (username, password_hash, role, status)
SELECT 'doctor5', '$2b$12$kR6LqRD9qZIsfwjY3.uQM.1qEvYejZYrNE7x2A1YIiVQrzur3KT9C', 'DOCTOR', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'doctor5');

INSERT INTO users (username, password_hash, role, status)
SELECT 'doctor6', '$2b$12$kR6LqRD9qZIsfwjY3.uQM.1qEvYejZYrNE7x2A1YIiVQrzur3KT9C', 'DOCTOR', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'doctor6');

INSERT INTO users (username, password_hash, role, status)
SELECT 'doctor7', '$2b$12$kR6LqRD9qZIsfwjY3.uQM.1qEvYejZYrNE7x2A1YIiVQrzur3KT9C', 'DOCTOR', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'doctor7');

INSERT INTO users (username, password_hash, role, status)
SELECT 'doctor8', '$2b$12$kR6LqRD9qZIsfwjY3.uQM.1qEvYejZYrNE7x2A1YIiVQrzur3KT9C', 'DOCTOR', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'doctor8');

INSERT INTO users (username, password_hash, role, status)
SELECT 'admin', '$2b$12$.aG2Y5EkdL2e2Yb3.QT3oOs5BMVviJEuZyxWLXi8yQEvvqsV4bcPi', 'ADMIN', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');

INSERT INTO users (username, password_hash, role, status)
SELECT 'auditor', '$2b$12$epf.tUJvnaTGP624FQEYheTvPBrumSxdu5sYBOh2Xfz0UdT58XUZ6', 'AUDITOR', 'ACTIVE'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'auditor');
