# API Boundary for Team Members

This document defines what Member A has provided and how Members B, C, and D should connect to the authentication and RBAC foundation.

## 1. Member A Provides

Member A provides the base backend and frontend login framework:

- FastAPI backend skeleton
- Vue 3 frontend skeleton
- `users` table
- bcrypt password hashing
- JWT login
- current-user dependency
- role-based access control
- four demo accounts
- frontend login and role-based route redirection

## 2. Demo Accounts

All demo accounts use the same password:

```text
password123
```

| Username | Role | Frontend Route |
|---|---|---|
| `patient1` | `PATIENT` | `/patient` |
| `doctor1` | `DOCTOR` | `/doctor` |
| `admin` | `ADMIN` | `/admin` |
| `auditor` | `AUDITOR` | `/auditor` |

Passwords are stored as bcrypt hashes in the `users.password_hash` column. Plaintext passwords are not stored in the database.

## 3. Startup

Install backend dependencies for the first time:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Install frontend dependencies for the first time:

```powershell
cd frontend
npm.cmd install
```

Start the openGauss container first:

```powershell
docker start my_opengauss
```

Start the backend:

```powershell
cd backend
.\run_dev.ps1
```

Backend URL:

```text
http://127.0.0.1:8000
```

Swagger API docs:

```text
http://127.0.0.1:8000/docs
```

Start the frontend:

```powershell
cd frontend
.\run_dev.ps1
```

Frontend URL:

```text
http://localhost:5173
```

The frontend startup script runs Vite in the current PowerShell window and opens the frontend page after 2 seconds.

## 4. Synthea Data Generation for Member B

Synthea is stored in the project `synthea/` directory. It generates synthetic patients and medical records, so the project does not use real private medical data.

Synthea requires Java JDK 17 or newer. Check Java first:

```powershell
java -version
```

Generate a small demo dataset on Windows:

```powershell
cd synthea
.\run_synthea.bat -p 10 --exporter.fhir.export=true --exporter.csv.export=true
```

Useful options:

```text
-p 10                         Generate 10 synthetic patients
--exporter.fhir.export=true   Export FHIR JSON files
--exporter.csv.export=true    Export CSV files
```

Default output paths:

```text
synthea/output/fhir/
synthea/output/csv/
```

Recommended resources for import:

```text
Patient
Encounter
Condition
Observation
MedicationRequest
Procedure
```

Member B should convert these resources into the internal medical-record JSON format, then encrypt and store the result in `medical_records`.

Current status:

```text
Synthea generator exists.
Synthea import script is not implemented yet.
Encrypted medical-record storage is not implemented yet.
```

## 5. Authentication APIs

### Login

```text
POST /api/auth/login
```

Request body:

```json
{
  "username": "doctor1",
  "password": "password123"
}
```

Successful response:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user": {
    "id": 2,
    "username": "doctor1",
    "role": "DOCTOR",
    "status": "ACTIVE"
  }
}
```

### Current User

```text
GET /api/auth/me
```

Request header:

```text
Authorization: Bearer <access_token>
```

Response:

```json
{
  "id": 2,
  "username": "doctor1",
  "role": "DOCTOR",
  "status": "ACTIVE"
}
```

## 6. Backend Dependencies for Other Members

Other backend modules should import:

```python
from fastapi import Depends
from app.core.deps import get_current_user, require_roles
from app.models.user import User
```

Use this when an API only requires login:

```python
def some_api(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "status": current_user.status,
    }
```

The `current_user` object provides:

```text
current_user.id
current_user.username
current_user.role
current_user.status
```

## 7. Role-Based Access Control

Use `require_roles()` when an API should only allow specific roles.

Doctor-only API:

```python
@router.get("/api/doctor/my-patients")
def my_patients(current_user: User = Depends(require_roles("DOCTOR"))):
    doctor_user_id = current_user.id
    return {"doctor_user_id": doctor_user_id}
```

Patient-only API:

```python
@router.get("/api/patient/me/records")
def my_records(current_user: User = Depends(require_roles("PATIENT"))):
    patient_user_id = current_user.id
    return {"patient_user_id": patient_user_id}
```

Admin-only API:

```python
@router.get("/api/admin/users")
def list_users(current_user: User = Depends(require_roles("ADMIN"))):
    return {"message": "admin only"}
```

Auditor-only API:

```python
@router.get("/api/audit/logs")
def audit_logs(current_user: User = Depends(require_roles("AUDITOR"))):
    return {"message": "auditor only"}
```

Multiple roles:

```python
@router.get("/api/audit/verify-integrity")
def verify_integrity(
    current_user: User = Depends(require_roles("ADMIN", "AUDITOR")),
):
    return {"message": "admin or auditor only"}
```

## 8. Status Codes

| Status Code | Meaning |
|---|---|
| `200` | Request succeeded |
| `401` | Not logged in, invalid token, or expired token |
| `403` | Logged in but role is not allowed |
| `422` | Request body format is invalid |
| `500` | Backend internal error |

## 9. Interfaces Reserved for Member B

Member B is responsible for Synthea data, patients, medical records, and encryption.

Suggested APIs:

```text
POST /api/import/synthea
GET  /api/patient/me/records
GET  /api/doctor/patients/{patient_id}/records
GET  /api/doctor/patients/{patient_id}/records/{record_id}
```

Expected dependencies:

```python
current_user: User = Depends(require_roles("PATIENT"))
current_user: User = Depends(require_roles("DOCTOR"))
db: Session = Depends(get_db)
```

Implementation notes:

```text
Read from synthea/output/fhir/ or synthea/output/csv/.
Create patient rows linked to users where needed.
Convert clinical resources into internal structured JSON.
Encrypt internal JSON before inserting into medical_records.
Do not store plaintext diagnosis, labs, medications, or notes in normal database columns.
```

## 10. Interfaces Reserved for Member C

Member C is responsible for consent, default access, extra access requests, revocation, and masking.

Suggested APIs:

```text
GET  /api/doctor/my-patients
GET  /api/doctor/patients/search
POST /api/doctor/access-requests
GET  /api/patient/me/consents
GET  /api/patient/me/access-requests
POST /api/patient/consents/{id}/approve
POST /api/patient/consents/{id}/reject
POST /api/patient/consents/{id}/revoke
```

Expected role usage:

```python
require_roles("DOCTOR")
require_roles("PATIENT")
```

## 11. Interfaces Reserved for Member D

Member D is responsible for audit logs, denied access logs, hash chain verification, and demo testing materials.

Suggested APIs:

```text
GET  /api/audit/logs
POST /api/audit/verify-integrity
GET  /api/audit/suspicious-events
GET  /api/patient/me/audit-logs
```

Expected role usage:

```python
require_roles("AUDITOR")
require_roles("ADMIN", "AUDITOR")
require_roles("PATIENT")
```

## 12. Security Notes

- Never store plaintext passwords.
- Use bcrypt hashes in `users.password_hash`.
- Use JWT only as a login credential, not as a place to store sensitive data.
- Do not trust frontend route protection alone.
- Every protected backend API must use `get_current_user()` or `require_roles()`.
- RBAC only checks the user's role. Patient consent and record-level authorization must be implemented separately by later modules.
