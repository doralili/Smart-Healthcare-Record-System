import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000'
})

// 请求拦截器（自动带 token）
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：直接返回 data
api.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

// 获取医生个人信息
export function getDoctorProfile() {
  return api.get('/api/doctor/me')
}

// 获取我的患者
export function getMyPatients() {
  return api.get('/api/doctor/my-patients')
}

// 提交授权申请
export function submitAccessRequest(data: any) {
  return api.post('/api/doctor/access-requests', data)
}

// 获取脱敏病历
export function getPatientRecord(patientId: number) {
  return api.get(`/api/doctor/patients/${patientId}/records`)
}

// 更新病历记录（覆盖已有记录）
export function updatePatientRecord(patientId: number, recordId: number, record: any) {
  return api.put(`/api/doctor/patients/${patientId}/records/${recordId}`, { record })
}

// 新增病历记录（追加新记录）
export function addPatientRecord(patientId: number, record: any) {
  return api.post(`/api/doctor/patients/${patientId}/records`, { record })
}