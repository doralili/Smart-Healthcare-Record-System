import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use((response) => response.data);

export type ManagedRole = "DOCTOR" | "AUDITOR" | "ADMIN";
export type AccountStatus = "ACTIVE" | "DISABLED" | "PENDING";
export type DoctorStatus = "PENDING" | "APPROVED" | "DISABLED";

export interface AdminOverview {
  user_count: number;
  doctor_count: number;
  patient_count: number;
  disabled_user_count: number;
  medical_record_count: number;
  consent_count: number;
  recent_audit_log_count: number;
  hash_chain_valid: boolean;
  hash_chain_checked_count: number;
  record_access_note: string;
}

export interface AdminUser {
  id: number;
  username: string;
  role: string;
  status: AccountStatus;
  created_at: string;
  last_login_at: string | null;
  doctor_status: DoctorStatus | null;
}

export interface AdminDoctor {
  user_id: number;
  username: string;
  account_status: AccountStatus;
  doctor_status: DoctorStatus;
  department: string | null;
  license_no: string | null;
  note: string | null;
  verified: boolean;
  created_at: string;
}

export interface AdminPatient {
  id: number;
  full_name: string;
  gender: string | null;
  birth_date: string | null;
  user_id: number | null;
}

export interface CreateUserPayload {
  username: string;
  password: string;
  role: ManagedRole;
  department?: string;
  license_no?: string;
  note?: string;
}

export interface UpdateDoctorPayload {
  department?: string | null;
  license_no?: string | null;
  note?: string | null;
  verified?: boolean;
  account_status?: AccountStatus;
}

export interface AssignDoctorPayload {
  doctor_user_id: number;
  patient_id: number;
  note?: string;
}

export function getAdminOverview() {
  return api.get<unknown, AdminOverview>("/api/admin/overview");
}

export function listAdminUsers() {
  return api.get<unknown, { users: AdminUser[] }>("/api/admin/users");
}

export function createAdminUser(payload: CreateUserPayload) {
  return api.post<unknown, AdminUser>("/api/admin/users", payload);
}

export function updateAdminUserStatus(userId: number, status: AccountStatus) {
  return api.patch<unknown, { id: number; status: AccountStatus }>(
    `/api/admin/users/${userId}/status`,
    { status },
  );
}

export function resetAdminUserPassword(userId: number, password: string) {
  return api.post<unknown, { id: number; message: string }>(
    `/api/admin/users/${userId}/reset-password`,
    { password },
  );
}

export function listAdminDoctors() {
  return api.get<unknown, { doctors: AdminDoctor[] }>("/api/admin/doctors");
}

export function updateAdminDoctor(userId: number, payload: UpdateDoctorPayload) {
  return api.patch<unknown, AdminDoctor>(`/api/admin/doctors/${userId}`, payload);
}

export function listAdminPatients(q = "") {
  return api.get<unknown, { patients: AdminPatient[] }>("/api/admin/patients", {
    params: { q },
  });
}

export function assignDoctorToPatient(payload: AssignDoctorPayload) {
  return api.post<unknown, unknown>("/api/admin/assignments", payload);
}
