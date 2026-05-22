# Smart Healthcare System with Patient-Controlled Access

## 1. Project Positioning

This project is a security-focused smart healthcare record system. The goal is not to build a complete hospital information system, but to demonstrate how computer security and data security mechanisms can protect electronic medical records.

The core idea is:

> Medical records should not be freely visible to every doctor or administrator. Patients should be able to control who can access their records, what parts can be accessed, and when access should be revoked.

The system focuses on the following security problems:

- Unauthorized doctors may try to access patient records.
- Database leakage may expose sensitive medical information.
- Doctors may continue viewing records after consent is revoked.
- Access behavior may be denied or hidden afterwards.
- Administrators may have excessive privileges.
- Different doctors may need different levels of medical information.

Therefore, the project emphasizes:

- Patient-controlled authorization with default clinical consent and later revocation
- Role-based access control
- Encrypted medical record storage
- Sensitive information masking
- Transparent access audit logs
- Tamper-evident log integrity verification
- Synthetic healthcare data generation with Synthea

## 2. Relationship with Course Requirements

The group project requires a topic relevant to computer security and data security, with a demo system, written report, oral presentation, and slides.

This project matches the assessment requirements as follows:

| Assessment Item | How This Project Addresses It |
|---|---|
| Literature survey | Healthcare data privacy, electronic health records, access control, encryption, audit logs, Synthea synthetic data |
| Project description | A patient-controlled healthcare record system with clear social value |
| Development | A runnable web demo with login, authorization, encrypted storage, masking, and audit logs |
| Testing and demonstration | Default consent, consent revocation, access denial after revocation, database ciphertext inspection, audit integrity check |
| Presentation | Clear security story: protect confidentiality, integrity, authentication, access control, and accountability |

The project can directly connect to course concepts:

- Confidentiality: encryption, authorization, data masking
- Integrity: tamper-evident audit logs, controlled modification
- Availability: authorized users can access needed medical data
- Authentication: secure login and identity verification
- Access control: RBAC plus patient consent
- Cryptography: AES-GCM encryption, password hashing, hash chain logs
- Security attacks: interception, modification, fabrication, insider misuse

## 3. Scope Control

This system should not become a full HIS. Existing HIS systems often include registration, billing, pharmacy, scheduling, inpatient management, outpatient workflow, inventory, and insurance settlement. Those functions are useful references but are too broad for this course project.

This project should only implement healthcare functions that support the security story.

### In Scope

- User login and role management
- Patient list and medical record list
- Doctor access request
- Patient approval or rejection
- Patient revocation
- Medical record encryption at rest
- Field-level data masking
- Audit log for every access attempt
- Audit log integrity verification
- Synthea data import
- Demo-ready UI pages

### Out of Scope

- Hospital billing
- Drug inventory
- Appointment scheduling
- Ward management
- Insurance claim system
- Complex clinical decision support
- Real blockchain integration
- Real biometric authentication
- Real hospital production deployment

## 4. Recommended Technology Stack

Use a simple and controllable web architecture. The project will use one fixed stack instead of keeping multiple alternatives, so the team can start implementation quickly and avoid integration overhead.

### Final Stack

- Frontend: Vue 3 + Vite + Element Plus
- Backend: FastAPI
- Database: openGauss
- ORM: SQLAlchemy 2.x or SQLModel with a PostgreSQL-compatible driver such as `psycopg2` or `psycopg`
- Authentication: JWT
- Password hashing: bcrypt
- Record encryption: AES-256-GCM with Python `cryptography`
- Audit integrity: SHA-256 hash chain
- Data generation: Synthea FHIR JSON or CSV
- API documentation: FastAPI automatic Swagger/OpenAPI
- Demo deployment: local frontend server, local backend server, and local or Docker-based openGauss

This stack is chosen because the project is a security-focused demo. FastAPI makes authentication, authorization, encryption, audit logging, and Synthea import easy to prototype, while Vue 3 and Element Plus are efficient for dashboard-style pages such as consent approval, record viewing, and audit log inspection. openGauss gives the project a distinctive database choice while still allowing the backend to use familiar PostgreSQL-style connection tooling.

## 5. System Roles

The system contains four roles.

| Role | Main Permission | Security Boundary |
|---|---|---|
| Patient | View own records, manage consent, revoke doctor access, view access logs | Owns revocation and access transparency |
| Doctor | View related patient list, access default-authorized records, request extra access | Record readability depends on active default consent or explicit consent |
| Admin | Manage users, verify doctor accounts | Cannot directly view decrypted medical records |
| Auditor | View audit logs and integrity check results | Cannot view medical record content |

The key design principle is least privilege. Each role only receives the permissions necessary for its task.

## 6. Main User Stories

### 6.1 Patient

- As a patient, I can log in and view my own medical records.
- As a patient, I can see which doctors currently have default access to my records.
- As a patient, I can keep the default clinical consent created by the doctor-patient relationship.
- As a patient, I can approve extra access requests if a doctor needs broader scope.
- As a patient, I can revoke a doctor's access at any time.
- As a patient, I can view who accessed my records, when, and for what reason.

### 6.2 Doctor

- As a doctor, I can open my dashboard and see my related patient list.
- As a doctor, I can see patients grouped by access status: default authorized, extra access pending, expired, or revoked.
- As a doctor, I can click a patient in my list and view default-authorized medical information immediately.
- As a doctor, I can search for new patients outside my current list.
- As a doctor, I cannot view a patient's record after the patient revokes access.
- As a doctor, I can submit an extra access request if I need a broader record scope.
- As a doctor, I can view only the authorized parts of a patient's record.
- As a doctor, I lose access immediately after the patient revokes consent.

### 6.3 Admin

- As an admin, I can create and manage user accounts.
- As an admin, I can verify doctor identity and department information.
- As an admin, I cannot read decrypted patient records by default.

### 6.4 Auditor

- As an auditor, I can review access logs.
- As an auditor, I can detect failed or suspicious access attempts.
- As an auditor, I can verify whether logs have been modified.

## 7. Core Security Design

## 7.1 Authentication

Users must log in before using the system.

Recommended implementation:

1. User enters username and password.
2. Backend checks whether the user exists.
3. Backend verifies password hash with bcrypt.
4. Backend issues a short-lived JWT access token.
5. Frontend stores the token in memory or secure storage.
6. Every protected API requires the token.
7. Backend extracts `user_id` and `role` from the token.

Password storage rule:

```text
Never store plaintext passwords.
Store only password_hash.
Use bcrypt with salt.
```

Example user table:

```text
users
- id
- username
- password_hash
- role
- status
- created_at
- last_login_at
```

## 7.2 Role-Based Access Control

RBAC controls what each type of user can do.

Example permission matrix:

| API | Patient | Doctor | Admin | Auditor |
|---|---:|---:|---:|---:|
| View own record | Yes | No | No | No |
| Request record access | No | Yes | No | No |
| Approve consent | Yes | No | No | No |
| Revoke consent | Yes | No | No | No |
| View authorized record | No | Yes | No | No |
| Manage users | No | No | Yes | No |
| View audit logs | Own logs only | Own logs only | Limited | Yes |
| Verify log integrity | No | No | Yes | Yes |

RBAC alone is not enough. A doctor role only means the user is a doctor. It does not mean the doctor can view every patient's record. Patient consent is still required.

## 7.3 Patient-Controlled Consent

Consent is the most important feature of the project. To make the demo faster and closer to real clinical systems, the system uses default clinical consent for patients in a doctor's related patient list. This is similar to many applications where users accept necessary service authorization when starting to use a service. The patient can still revoke the doctor's access later.

The consent design should answer five questions:

```text
Who grants access?       patient_id
Who receives access?     doctor_id
What can be accessed?    record_scope
What action is allowed?  permission
How long is it valid?    start_time, end_time
```

Recommended consent table:

```text
consents
- id
- patient_id
- doctor_id
- record_scope
- permission
- status
- request_reason
- approve_note
- consent_source
- default_scope
- start_time
- end_time
- created_at
- auto_granted_at
- approved_at
- revoked_at
```

Recommended status values:

```text
PENDING
ACTIVE
REJECTED
REVOKED
EXPIRED
```

Recommended consent source values:

```text
DEFAULT_CLINICAL
EXPLICIT_REQUEST
```

Recommended scope values:

```text
BASIC
DIAGNOSIS
LAB
MEDICATION
FULL
```

Access decision algorithm:

```text
Input: doctor_id, patient_id, requested_scope

1. Check whether current user is authenticated.
2. Check whether current user role is DOCTOR.
3. Check whether doctor account is active and verified.
4. Find consent where:
   - consent.patient_id = patient_id
   - consent.doctor_id = doctor_id
   - consent.status = ACTIVE
   - current_time is between start_time and end_time
5. Check whether requested_scope is included in consent.record_scope or default_scope.
6. If all checks pass:
   - decrypt record
   - apply masking according to scope
   - return result
   - write ALLOW audit log
7. Otherwise:
   - return 403 Forbidden
   - write DENY audit log
```

## 7.4 Encrypted Medical Record Storage

Medical records should be encrypted before being saved to the database. This protects confidentiality even if the database is leaked.

Recommended algorithm:

- Use AES-256-GCM for record encryption.
- Use random IV for every encryption.
- Use authentication tag from GCM to detect tampering.
- Use envelope encryption to protect data keys.

Envelope encryption design:

```text
master_key: stored in environment variable, not in database
data_key: randomly generated for each record

record_plaintext --AES-GCM(data_key)--> ciphertext
data_key --AES-GCM(master_key)--> encrypted_data_key
```

Recommended medical record table:

```text
medical_records
- id
- patient_id
- record_type
- encrypted_data_key
- iv
- auth_tag
- ciphertext
- created_by
- created_at
- updated_at
```

Important rules:

- Do not store plaintext diagnosis, medication, lab result, or clinical notes in normal columns.
- Do not hardcode the master key in source code.
- Load the master key from `.env` or system environment variables.
- Use a different IV for every encryption operation.
- Re-encrypt data if the encryption format changes.

Demo evidence:

1. Open database table.
2. Show that record content is ciphertext.
3. Access through valid doctor authorization.
4. Show decrypted content in frontend.
5. Revoke authorization.
6. Show that doctor can no longer decrypt through the API.

## 7.5 Sensitive Information Masking

Encryption protects stored data. Masking protects displayed data.

Different users should see different levels of detail.

Recommended masking rules:

| Field | BASIC | DIAGNOSIS | LAB | FULL |
|---|---|---|---|---|
| Name | Visible | Visible | Visible | Visible |
| Phone | Masked | Masked | Masked | Visible |
| Address | City only | City only | City only | Full |
| Diagnosis summary | Hidden | Visible | Hidden | Visible |
| Lab result | Hidden | Hidden | Visible | Visible |
| Medication | Hidden | Hidden | Hidden | Visible |
| Doctor note | Hidden | Partial | Hidden | Visible |
| High-sensitive label | Hidden | Masked | Masked | Visible |

Example masking:

```text
Phone: 13812345678 -> 138****5678
ID number: 440101200001011234 -> 440***********1234
Address: Guangdong Guangzhou Tianhe... -> Guangzhou
High-sensitive diagnosis: HIV infection -> [Sensitive diagnosis hidden]
```

Implementation steps:

1. Decrypt the medical record after access control passes.
2. Parse the record as structured JSON.
3. Apply masking policy based on authorized scope.
4. Return the masked JSON to frontend.

Do not mask by simple string replacement on raw text if structured fields are available.

## 7.6 Audit Logging

Every important action should be logged.

Recommended logged actions:

```text
LOGIN_SUCCESS
LOGIN_FAILED
REQUEST_ACCESS
APPROVE_CONSENT
REJECT_CONSENT
REVOKE_CONSENT
VIEW_RECORD
DENIED_RECORD_ACCESS
EXPORT_RECORD
VERIFY_AUDIT_LOG
```

Recommended audit table:

```text
audit_logs
- id
- actor_id
- actor_role
- patient_id
- record_id
- action
- decision
- reason
- ip_address
- user_agent
- timestamp
- prev_hash
- log_hash
```

Log content should include enough information to answer:

```text
Who did what, to whose record, when, from where, and was it allowed?
```

## 7.7 Tamper-Evident Audit Hash Chain

To show integrity protection, each audit log can include a hash of the previous log.

Hash calculation:

```text
log_hash = SHA256(prev_hash + actor_id + action + patient_id + record_id + decision + timestamp)
```

Verification:

```text
1. Read audit logs in timestamp order.
2. For the first log, use a fixed genesis prev_hash.
3. Recalculate each log_hash.
4. Compare recalculated hash with stored log_hash.
5. Check whether each log's prev_hash equals the previous log's log_hash.
6. If any mismatch occurs, mark the chain as tampered.
```

Demo scenario:

1. Generate normal access logs.
2. Manually modify one old log in the database.
3. Run audit verification.
4. System reports which log breaks the chain.

This strongly demonstrates integrity and non-repudiation.

## 8. Data Design

## 8.1 Main Tables

### users

```text
id
username
password_hash
role
status
created_at
last_login_at
```

### patients

```text
id
user_id
synthea_patient_id
name
gender
birth_date
phone
address
created_at
```

### doctors

```text
id
user_id
name
department
license_no
verified
created_at
```

### medical_records

```text
id
patient_id
record_type
encrypted_data_key
iv
auth_tag
ciphertext
created_by
created_at
updated_at
```

### consents

```text
id
patient_id
doctor_id
record_scope
permission
status
request_reason
approve_note
consent_source
default_scope
start_time
end_time
created_at
auto_granted_at
approved_at
revoked_at
```

### audit_logs

```text
id
actor_id
actor_role
patient_id
record_id
action
decision
reason
ip_address
user_agent
timestamp
prev_hash
log_hash
```

## 8.2 Medical Record JSON Format

Store decrypted medical record content as structured JSON before encryption.

Example:

```json
{
  "basic": {
    "name": "Alice Chen",
    "gender": "F",
    "birthDate": "1988-04-12",
    "phone": "13812345678",
    "address": "Guangzhou, Guangdong"
  },
  "diagnosis": [
    {
      "date": "2026-05-01",
      "code": "E11",
      "description": "Type 2 diabetes mellitus",
      "sensitivity": "NORMAL"
    }
  ],
  "lab": [
    {
      "date": "2026-05-02",
      "item": "Blood glucose",
      "value": "8.2",
      "unit": "mmol/L"
    }
  ],
  "medication": [
    {
      "name": "Metformin",
      "dose": "500mg",
      "frequency": "twice daily"
    }
  ],
  "notes": [
    {
      "date": "2026-05-03",
      "author": "Dr. Wang",
      "content": "Patient should monitor glucose level regularly."
    }
  ]
}
```

## 9. Synthea Data Generation and Import Plan

Synthea is used to generate synthetic patient records. This avoids privacy risks from real patient data.

## 9.1 Generate Data

In the Synthea directory:

```bash
cd "Smart Healthcare Record System/synthea"
./run_synthea -p 100 --exporter.fhir.export=true --exporter.csv.export=true
```

On Windows:

```powershell
cd "Smart Healthcare Record System\synthea"
.\run_synthea.bat -p 100 --exporter.fhir.export=true --exporter.csv.export=true
```

Expected output:

```text
synthea/output/fhir/
synthea/output/csv/
```

## 9.2 Import Only Useful Data

Recommended imported resources:

- Patient
- Encounter
- Condition
- Observation
- MedicationRequest
- Procedure

Recommended import pipeline:

```text
1. Read Synthea FHIR JSON or CSV.
2. Extract patient identity and demographics.
3. Extract conditions, lab observations, medications, procedures.
4. Convert each patient's clinical data into the system's medical record JSON.
5. Encrypt the medical record JSON.
6. Insert encrypted record into medical_records.
7. Create patient user accounts for demo patients.
```

## 9.3 Demo Dataset

For the final demo, prepare a small fixed dataset:

```text
Patients:
- Alice Chen
- Bob Li
- Carol Zhang

Doctors:
- Dr. Wang, Cardiology
- Dr. Liu, General Medicine
- Dr. Zhao, Laboratory Medicine

Admin:
- admin

Auditor:
- auditor
```

This makes the presentation stable and easy to rehearse.

## 10. API Design

## 10.1 Authentication

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

Public registration is limited to patient accounts. New registered users are created as `PATIENT` with `ACTIVE` status. Doctor, admin, and auditor accounts are issued through administrator-controlled setup or seed data rather than public self-registration.

## 10.2 Patient APIs

```text
GET  /api/patient/me/records
GET  /api/patient/me/consents
GET  /api/patient/me/access-requests
GET  /api/patient/me/doctor-access
POST /api/patient/consents/{id}/approve
POST /api/patient/consents/{id}/reject
POST /api/patient/consents/{id}/revoke
GET  /api/patient/me/audit-logs
```

## 10.3 Doctor APIs

```text
GET  /api/doctor/my-patients
GET  /api/doctor/patients/search
POST /api/doctor/access-requests
GET  /api/doctor/authorized-patients
GET  /api/doctor/patients/{patient_id}/records
GET  /api/doctor/patients/{patient_id}/records/{record_id}
```

`GET /api/doctor/my-patients` returns patients related to the current doctor, grouped by consent status:

```text
DEFAULT_AUTHORIZED
EXTRA_ACCESS_PENDING
PENDING
EXPIRED
REVOKED
```

For patients with `DEFAULT_AUTHORIZED` status, the doctor can open default-scope records immediately. Every record detail API must still check that the default or explicit consent is active, not expired, not revoked, and includes the requested scope before decryption.

## 10.4 Admin APIs

```text
GET  /api/admin/users
POST /api/admin/users
PATCH /api/admin/users/{id}/status
PATCH /api/admin/doctors/{id}/verify
```

## 10.5 Auditor APIs

```text
GET  /api/audit/logs
POST /api/audit/verify-integrity
GET  /api/audit/suspicious-events
```

## 11. Frontend Page Design

## 11.1 Login Page

Functions:

- Login as patient, doctor, admin, or auditor.
- Show login failure for wrong password.
- Route user to role-specific dashboard.

## 11.2 Patient Dashboard

Functions:

- View own records.
- View pending doctor requests.
- Approve request with scope and expiration time.
- Reject request.
- Revoke active consent.
- View access history.

Key UI components:

- Record list
- Pending access request table
- Active authorization table
- Audit timeline

## 11.3 Doctor Dashboard

Functions:

- View "My Patients" as the first screen.
- See patient access status: default authorized, extra access pending, expired, or revoked.
- Click a default-authorized patient and view the default medical record scope immediately.
- Submit or resubmit extra access requests for broader scope or revoked patients.
- Search new patients when they are not already in the doctor's related patient list.
- View authorized medical records only after active consent passes backend validation.
- See masked or full data depending on scope.

Key UI components:

- My patients table
- Access status tabs or filters
- Patient search bar
- Access request form
- Medical record detail panel

## 11.4 Admin Dashboard

Functions:

- Create user accounts.
- Disable suspicious users.
- Verify doctor accounts.
- View system status.

Important limitation:

- Admin should not have a button to view decrypted medical records.

## 11.5 Auditor Dashboard

Functions:

- View all access logs.
- Filter by patient, doctor, action, decision, and time.
- Run integrity verification.
- Highlight failed access attempts.

## 12. Detailed Implementation Plan

## 12.1 Phase 1: Project Initialization

Operations:

1. Create backend project.
2. Create frontend project.
3. Configure database.
4. Create `.env` file for secrets.
5. Add initial database migration.

Important environment variables:

```text
DATABASE_URL=
JWT_SECRET=
MASTER_KEY=
ACCESS_TOKEN_EXPIRE_MINUTES=
```

`MASTER_KEY` should be randomly generated and kept outside source code.

## 12.2 Phase 2: Authentication and User Roles

Operations:

1. Implement user registration or seed demo users.
2. Hash passwords with bcrypt.
3. Implement login API.
4. Generate JWT token after successful login.
5. Implement authentication middleware.
6. Implement role-checking middleware.
7. Add frontend login page.
8. Test login for patient, doctor, admin, and auditor.

Expected result:

```text
Unauthenticated users cannot access protected APIs.
Logged-in users can only access APIs allowed by their role.
```

## 12.3 Phase 3: Synthea Import

Operations:

1. Generate 100 synthetic patients with Synthea.
2. Choose FHIR JSON or CSV import path.
3. Write an import script.
4. Extract patient demographics.
5. Extract clinical records.
6. Convert records to internal JSON format.
7. Encrypt records before database insertion.
8. Seed demo accounts linked to selected patients.

Expected result:

```text
The database has patients and encrypted medical records.
The plaintext record should not appear in the database.
```

## 12.4 Phase 4: Encryption Module

Operations:

1. Implement `generate_data_key()`.
2. Implement `encrypt_record(plaintext_json)`.
3. Implement `decrypt_record(record_id)`.
4. Use AES-GCM for encryption and decryption.
5. Store `ciphertext`, `iv`, `auth_tag`, and `encrypted_data_key`.
6. Add unit tests for encryption and decryption.
7. Add a test for tampered ciphertext.

Expected result:

```text
Valid ciphertext can be decrypted only by backend code with MASTER_KEY.
Modified ciphertext fails authentication.
Database does not contain plaintext medical data.
```

## 12.5 Phase 5: Consent Workflow

Operations:

1. System creates a `DEFAULT_CLINICAL` and `ACTIVE` consent record when a patient is assigned to a doctor for the demo.
2. Doctor opens the "My Patients" dashboard.
3. Doctor clicks a default-authorized patient and accesses default-scope records through authorization middleware.
4. Patient views current doctor access.
5. Patient revokes consent.
6. System changes consent to `REVOKED`.
7. Doctor tries again and receives `403 Forbidden`.
8. If broader access is needed, doctor submits an extra access request and the patient can approve or reject it.

Expected result:

```text
Doctor can access default-scope records for related patients by default.
Doctor can access only active and authorized scope during valid time.
Doctor cannot access after revocation.
```

## 12.6 Phase 6: Masking Module

Operations:

1. Define field-level masking policies.
2. Implement `mask_basic_info()`.
3. Implement `filter_record_by_scope()`.
4. Apply masking after decryption and before API response.
5. Test each scope: BASIC, DIAGNOSIS, LAB, MEDICATION, FULL.

Expected result:

```text
Doctors with limited consent receive limited and masked data.
Doctors with FULL consent receive complete data.
```

## 12.7 Phase 7: Audit Log Module

Operations:

1. Create audit log table.
2. Add audit logging service.
3. Log successful access.
4. Log denied access.
5. Log consent approval, rejection, and revocation.
6. Log login failures.
7. Add frontend audit log table for patients and auditors.

Expected result:

```text
Every important security-related action appears in audit logs.
Patients can see who accessed their records.
Auditors can review system-wide behavior.
```

## 12.8 Phase 8: Hash Chain Integrity Verification

Operations:

1. When writing a new audit log, read previous log hash.
2. Calculate current log hash.
3. Store `prev_hash` and `log_hash`.
4. Implement verification API.
5. Create auditor page button: "Verify Log Integrity".
6. For demo, manually change an old log row.
7. Run verification and show tampering detected.

Expected result:

```text
Normal logs pass verification.
Modified logs fail verification.
The system can identify the broken log position.
```

## 12.9 Phase 9: Security Testing

Prepare the following test cases:

| Test Case | Expected Result |
|---|---|
| Doctor accesses default-authorized patient record | 200 OK |
| Doctor accesses record after patient revocation | 403 Forbidden |
| Doctor accesses unauthorized scope | 403 Forbidden or masked response |
| Doctor accesses after revocation | 403 Forbidden |
| Patient views own access logs | Logs visible |
| Admin attempts to view decrypted record | Denied |
| Database inspected directly | Only ciphertext visible |
| Audit log modified manually | Integrity verification fails |
| Wrong password login | Login failed and logged |

## 13. Demonstration Script

Use a fixed demo script for presentation.

### Step 1: Database Security

1. Open the database table `medical_records`.
2. Show that medical data is stored as ciphertext.
3. Explain that AES-GCM protects confidentiality and detects tampering.

### Step 2: Default Clinical Access

1. Login as Dr. Wang.
2. Open the "My Patients" dashboard.
3. Click Alice Chen in the patient list.
4. System shows Alice's default-authorized diagnosis or basic clinical information.
5. Auditor page records `VIEW_RECORD`.

### Step 3: Patient Revocation

1. Login as Alice.
2. View current doctor access.
3. Revoke Dr. Wang's default clinical consent.
4. Login as Dr. Wang again.
5. Open the "My Patients" dashboard and click Alice Chen.
6. System returns `403 Forbidden`.
7. Audit log records the denied attempt.

### Step 4: Extra Access Request

1. Login as Dr. Wang.
2. Submit an extra access request for `LAB` or `FULL` scope.
3. Login as Alice.
4. Approve or reject the extra request.
5. Show that the returned record scope changes only after approval.

### Step 5: Audit Integrity

1. Login as auditor.
2. Run audit integrity verification.
3. Show normal result.
4. Manually modify one old log in the database.
5. Run verification again.
6. Show tampering detected.

## 14. Report Writing Logic

The final written report can follow this structure:

1. Introduction
   - Why healthcare data security matters
   - Why patient-controlled access is valuable
2. Literature and Background
   - Electronic health records
   - Access control
   - Encryption at rest
   - Audit logs
   - Synthetic medical data
3. Project Objectives
   - Protect medical record confidentiality
   - Let patients control doctor access
   - Provide transparent and tamper-evident access records
4. System Design
   - Architecture diagram
   - Role model
   - Database design
   - Consent workflow
5. Security Design
   - Authentication
   - RBAC
   - Patient consent
   - AES-GCM encryption
   - Data masking
   - Hash chain audit logs
6. Implementation
   - Technology stack
   - Main modules
   - Synthea import
7. Testing and Demo
   - Test cases
   - Screenshots
   - Demo scenarios
8. Conclusion
   - Achievements
   - Limitations
   - Future work

## 15. Future Extensions

If time allows, the following features can be added:

- Emergency break-glass access with stronger audit requirements
- Two-factor authentication for doctors
- Doctor department-based access policy
- Exportable patient consent report
- Risk score for suspicious access behavior
- Encrypted file upload for medical reports
- Public-key encryption for sharing record keys
- Blockchain-like external anchoring of daily audit hash

These are optional. The required high-quality version should first complete consent, encryption, masking, and audit logging.

## 16. Minimum Viable Demo Checklist

The project is demo-ready only when all items below are complete:

- [ ] Patient, doctor, admin, and auditor can log in.
- [ ] Synthea data is imported.
- [ ] Medical records are encrypted in the database.
- [ ] Doctor dashboard shows related patients grouped by consent status.
- [ ] Related patients have default clinical consent for limited-scope access.
- [ ] Patient can view and revoke doctor access.
- [ ] Doctor can submit an extra access request for broader scope.
- [ ] Patient can approve extra access with scope and time limit.
- [ ] Doctor can view only authorized and masked data.
- [ ] Patient can revoke access.
- [ ] Revoked doctor access is immediately denied.
- [ ] Every access attempt is recorded in audit logs.
- [ ] Patient can view own access logs.
- [ ] Auditor can view system logs.
- [ ] Audit log hash chain can be verified.
- [ ] Manual log tampering can be detected.
