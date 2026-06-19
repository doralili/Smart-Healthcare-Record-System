import { api } from "./client";

export interface PatientRecordSummary {
  id: number;
  patient_id: number;
  source: string;
  record_type: string;
  created_at: string;
}

export interface MedicalRecordPayload {
  encounters: unknown[];
  conditions: unknown[];
  observations: unknown[];
  medications: unknown[];
  procedures: unknown[];
}

export interface PatientProfile {
  id: number;
  synthea_patient_id: string;
  full_name: string;
  gender: string | null;
  birth_date: string | null;
  phone: string | null;
  address: string | null;
  created_at: string;
}

export interface PatientRecordDetail extends PatientRecordSummary {
  record_count?: number;
  latest_record_id?: number | null;
  latest_record_created_at?: string | null;
  patient: PatientProfile;
  record: MedicalRecordPayload;
}

export function listMyRecords() {
  return api.get<unknown, PatientRecordSummary[]>("/api/patient/me/records");
}

export function getMyRecordDetail(recordId: number) {
  return api.get<unknown, PatientRecordDetail>(`/api/patient/me/records/${recordId}`);
}

export function getMyCombinedRecord() {
  return api.get<unknown, PatientRecordDetail>("/api/patient/me/records/combined");
}
