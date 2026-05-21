from app.core.security import hash_password


demo_users = [
    *[(f"patient{index}", "password123", "PATIENT") for index in range(1, 11)],
    ("doctor1", "password123", "DOCTOR"),
    ("admin", "password123", "ADMIN"),
    ("auditor", "password123", "AUDITOR"),
]


for username, password, role in demo_users:
    password_hash = hash_password(password)
    print(
        "INSERT INTO users (username, password_hash, role, status) "
        f"SELECT '{username}', '{password_hash}', '{role}', 'ACTIVE' "
        f"WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = '{username}');"
    )
