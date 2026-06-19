import { api } from './client'

export interface PendingConsent {
  consent_id: number
  doctor_name: string
  record_scope: string
  request_reason: string
  created_at: string
}

export interface AuthorizedDoctor {
  consent_id: number
  doctor_name: string
  record_scope: string
  granted_at: string
}

export interface AvailableDoctor {
  doctor_user_id: number
  username: string
  name: string
  department: string | null
  license_no: string | null
  default_consent_status: string
  default_consent_id: number | null
  default_consent_end_time: string | null
  access_status: string
  access_scope: string | null
  access_consent_id: number | null
  access_end_time: string | null
  can_select_default: boolean
}

export interface PendingConsentResponse {
  pending_consents: PendingConsent[]
}

export interface AuthorizedDoctorResponse {
  doctors: AuthorizedDoctor[]
}

export interface AvailableDoctorsResponse {
  doctors: AvailableDoctor[]
}

// 鑾峰彇寰呭鎵圭敵璇?
export function getPendingConsents(token: string) {
  return api.get<unknown, PendingConsentResponse>('/api/patient/me/records/pending-consents', {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 鎵瑰噯鐢宠
export function approveConsent(token: string, consentId: number) {
  return api.post(`/api/patient/me/records/consents/${consentId}/approve`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 鎷掔粷鐢宠
export function rejectConsent(token: string, consentId: number) {
  return api.post(`/api/patient/me/records/consents/${consentId}/reject`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 鑾峰彇宸叉巿鏉冨尰鐢熷垪琛?
export function getMyDoctors(token: string) {
  return api.get<unknown, AuthorizedDoctorResponse>('/api/patient/me/records/my-doctors', {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 鎾ら攢鎺堟潈
export function revokeConsent(token: string, consentId: number) {
  return api.post(`/api/patient/me/records/consents/${consentId}/revoke`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 鑾峰彇鍙€夊尰鐢燂紝鏀寔鎸夌瀹よ繃婊?
export function getAvailableDoctors(token: string, department = '') {
  return api.get<unknown, AvailableDoctorsResponse>('/api/patient/me/records/available-doctors', {
    params: department.trim() ? { department: department.trim() } : undefined,
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 閹綀鈧懘鈧瀚ㄦ妯款吇閸栬崵鏁?
export function selectDefaultDoctor(token: string, doctorUserId: number) {
  return api.post('/api/patient/me/records/default-doctors', {
    doctor_user_id: doctorUserId
  }, {
    headers: { Authorization: `Bearer ${token}` }
  })
}
