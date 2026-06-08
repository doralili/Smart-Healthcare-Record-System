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

export interface AuditSummary {
  total_logs: number;
  denied_logs: number;
  latest_log_at: string | null;
  action_counts: Array<{
    action: string;
    count: number;
  }>;
}

export interface AuditLog {
  id: number;
  actor_user_id: number | null;
  actor_role: string | null;
  actor_username: string | null;
  action: string;
  target_type: string | null;
  target_id: number | null;
  doctor_id: number | null;
  doctor_username: string | null;
  doctor_name: string | null;
  patient_id: number | null;
  patient_name: string | null;
  consent_id: number | null;
  record_scope: string | null;
  outcome: string;
  detail: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  previous_hash: string | null;
  current_hash: string;
}

export interface AuditLogResponse {
  logs: AuditLog[];
}

export interface VerifyResult {
  valid: boolean;
  checked_count: number;
  broken_log_id: number | null;
  reason: string | null;
  expected_previous_hash?: string | null;
  actual_previous_hash?: string | null;
  expected_current_hash?: string;
  actual_current_hash?: string;
}

export interface RecordWatermarkSummary {
  total_records: number;
  valid: number;
  invalid: number;
  missing: number;
  decryption_failed: number;
}

export interface RecordWatermark {
  record_id: number;
  patient_id: number;
  patient_name: string | null;
  doctor_id: number | null;
  doctor_username: string | null;
  doctor_name: string | null;
  source: string;
  record_type: string;
  created_at: string;
  updated_at: string | null;
  watermark_status: "VALID" | "INVALID" | "MISSING" | "DECRYPTION_FAILED";
  watermark_message: string;
  watermark_issued_at: string | null;
  watermark_record_hash: string | null;
}

export interface RecordWatermarkResponse {
  summary: RecordWatermarkSummary;
  records: RecordWatermark[];
}

export function getAuditSummary() {
  return api.get<unknown, AuditSummary>("/api/auditor/summary");
}

export function listAuditLogs(limit = 100) {
  return api.get<unknown, AuditLogResponse>("/api/auditor/audit-logs", {
    params: { limit },
  });
}

export function verifyAuditHashChain() {
  return api.get<unknown, VerifyResult>("/api/auditor/verify-hash-chain");
}

export function listRecordWatermarks() {
  return api.get<unknown, RecordWatermarkResponse>("/api/auditor/record-watermarks");
}
