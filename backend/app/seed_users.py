from app.core.security import hash_password


demo_users = [
    ("patient1", "password123", "PATIENT"),
    ("doctor1", "password123", "DOCTOR"),
    ("admin", "password123", "ADMIN"),
    ("auditor", "password123", "AUDITOR"),
]


for username, password, role in demo_users:
    password_hash = hash_password(password)
    print(
        "INSERT INTO users (username, password_hash, role, status) "
        f"VALUES ('{username}', '{password_hash}', '{role}', 'ACTIVE');"
    )
