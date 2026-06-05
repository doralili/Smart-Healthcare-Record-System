import axios from 'axios'

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000'
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  response => response.data,
  error => Promise.reject(error)
)

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

// 获取待审批申请
export function getPendingConsents(token: string) {
  return api.get<unknown, PendingConsentResponse>('/api/patient/me/records/pending-consents', {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 批准申请
export function approveConsent(token: string, consentId: number) {
  return api.post(`/api/patient/me/records/consents/${consentId}/approve`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 拒绝申请
export function rejectConsent(token: string, consentId: number) {
  return api.post(`/api/patient/me/records/consents/${consentId}/reject`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 获取已授权医生列表
export function getMyDoctors(token: string) {
  return api.get<unknown, AuthorizedDoctorResponse>('/api/patient/me/records/my-doctors', {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 撤销授权
export function revokeConsent(token: string, consentId: number) {
  return api.post(`/api/patient/me/records/consents/${consentId}/revoke`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 获取可选医生，支持按科室过滤
export function getAvailableDoctors(token: string, department = '') {
  return api.get<unknown, AvailableDoctorsResponse>('/api/patient/me/records/available-doctors', {
    params: department.trim() ? { department: department.trim() } : undefined,
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 鎮ｈ€呴€夋嫨榛樿鍖荤敓
export function selectDefaultDoctor(token: string, doctorUserId: number) {
  return api.post('/api/patient/me/records/default-doctors', {
    doctor_user_id: doctorUserId
  }, {
    headers: { Authorization: `Bearer ${token}` }
  })
}
