import { api } from './client'

export function getDoctorProfile() {
  return api.get<unknown, any>('/api/doctor/me')
}

export function getMyPatients() {
  return api.get<unknown, any>('/api/doctor/my-patients')
}

export function submitAccessRequest(data: any) {
  return api.post<unknown, any>('/api/doctor/access-requests', data)
}

export function getPatientRecord(patientId: number) {
  return api.get<unknown, any>(`/api/doctor/patients/${patientId}/records`)
}

export function searchPatients(q: string) {
  return api.get<unknown, any>('/api/doctor/search-patients', {
    params: { q },
  })
}

export function addPatientRecord(patientId: number, record: any) {
  return api.post<unknown, any>(`/api/doctor/patients/${patientId}/records`, { record })
}
