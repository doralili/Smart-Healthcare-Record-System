import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000'
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

export interface PendingConsentResponse {
  pending_consents: PendingConsent[]
}

export interface AuthorizedDoctorResponse {
  doctors: AuthorizedDoctor[]
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
