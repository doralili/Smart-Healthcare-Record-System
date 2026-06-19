<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import DashboardLayout from "../layouts/DashboardLayout.vue"
import { getMyPatients, getDoctorProfile, submitAccessRequest, getPatientRecord, addPatientRecord, searchPatients as searchPatientsApi } from '../api/doctor'
import { ElMessage } from '../utils/message'

const activeTab = ref('patients')
const searchKeyword = ref('')
const searchResults = ref<any[]>([])
const patients = ref<any[]>([])
const VISIT_TYPE_FALLBACK = 'General Clinical Visit'
const VISIT_CLASS_FALLBACK = 'GENERAL'
const showSignInAlert = ref(true)
const doctorProfile = ref<any>(null)
const dashboardTitle = computed(() =>
  doctorProfile.value?.name ? `${doctorProfile.value.name} Dashboard` : 'Doctor Dashboard',
)

// 弹窗相关
const recordDialogVisible = ref(false)
const currentRecord = ref<any>(null)
const currentPatient = ref<any>(null)
const editDialogVisible = ref(false)
const savingRecord = ref(false)
const applyDialogVisible = ref(false)
const applyForm = ref({
  patient_id: 0,
  patient_name: '',
  record_scope: 'EXTRA',
  reason: ''
})

// 诊断详情弹窗
const visitDetailVisible = ref(false)
const selectedVisit = ref<any>(null)
const diagnosisDateQuery = ref('')
const visitDetailKeywordQuery = ref('')
const visitDetailDepartmentFilter = ref('')

// 新增病历表单
const newRecordForm = ref<{
  encounters: any[]
  conditions: any[]
  observations: any[]
  medications: any[]
  procedures: any[]
}>({
  encounters: [],
  conditions: [],
  observations: [],
  medications: [],
  procedures: []
})

// 全局科室和医生信息
const globalDepartment = ref('')
const doctorName = ref('')

const getBeijingDateTimeValue = (date = new Date()) => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23'
  }).formatToParts(date)

  const valueByType = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${valueByType.year}-${valueByType.month}-${valueByType.day}T${valueByType.hour}:${valueByType.minute}:${valueByType.second}`
}

// 日期格式化函数
const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  return String(dateStr).split(/[T ]/)[0]
}

// 格式化日期时间（用于详情弹窗）
const formatDateTime = (dateStr: string) => {
  if (!dateStr) return 'Not recorded'
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 获取诊断相关的就诊记录（按日期匹配）
const getDateKey = (value: any) => {
  if (!value) return ''
  const text = String(value)
  if (text.length >= 16 && ['T', ' '].includes(text[10])) {
    return text.slice(0, 16)
  }
  return text.slice(0, 10)
}

const getEncounterId = (record: any, allowOwnId = false) => {
  if (!record) return ''
  if (record.encounter_id) return String(record.encounter_id)
  if (allowOwnId && record.id) return String(record.id)
  const reference = record.encounter?.reference
  return reference ? String(reference).split('/').pop() || '' : ''
}

const getClinicalDateKey = (record: any) =>
  getDateKey(
    record?.recorded_date ||
    record?.effective_datetime ||
    record?.authored_on ||
    record?.performed_datetime ||
    record?.start ||
    record?.date
  )

const joinUnique = (values: any[], fallback = 'Not recorded') => {
  const unique = values
    .map((value) => String(value || '').trim())
    .filter((value) => hasRecordedText(value))
    .filter((value, index, array) => array.indexOf(value) === index)
  return unique.length ? unique.join('; ') : fallback
}

const getDoctorDisplayName = (record: any) =>
  hasRecordedText(record?.doctor_name) ? record.doctor_name : record?.doctor

const cleanMedicalText = (value: any) => {
  if (!hasRecordedText(value)) return ''
  return String(value)
    .replace(/\s*\((finding|disorder|procedure|observable entity|regime\/therapy)\)\s*$/i, '')
    .trim()
}

const normalizeVisitClass = (value: any) => {
  const text = String(value || '').trim()
  if (!text) return ''
  const key = text.toLowerCase().replace(/[-_\s]/g, '')
  const classMap: Record<string, string> = {
    amb: 'AMB',
    ambulatory: 'AMB',
    outpatient: 'AMB',
    emer: 'EMER',
    emergency: 'EMER',
    er: 'EMER',
    imp: 'IMP',
    inpatient: 'IMP',
    inpatientencounter: 'IMP',
    hh: 'HH',
    home: 'HH',
    vr: 'VR',
    virtual: 'VR',
  }
  return classMap[key] || (text.length <= 6 ? text.toUpperCase() : text)
}

const normalizeSearchText = (value: any) =>
  String(value ?? '')
    .toLowerCase()
    .replace(/[./]/g, '-')
    .replace(/\s+/g, '')

const formatPrimaryDepartment = (value: any) =>
  String(value || '')
    .split(';')
    .map((item) => item.trim())
    .filter(Boolean)[0] || ''

const collectVisitDepartments = (visit: any) => {
  const values = visit.diagnoses.map((item: any) => item.department)
  return joinUnique(values, '')
}

const diagnosisMatchesKeyword = (diagnosis: any, query: string) => {
  const searchable = normalizeSearchText([
    diagnosis.department,
    diagnosis.name,
    diagnosis.status,
    diagnosis.date,
    diagnosis.recorded_date,
  ].join(' '))
  return searchable.includes(query)
}

const selectedVisitDepartmentOptions = computed(() => {
  if (!selectedVisit.value) return []
  const departments = selectedVisit.value.diagnoses
    .map((diagnosis: any) => String(diagnosis.department || '').trim())
    .filter(Boolean)
  return Array.from(new Set(departments)).sort()
})

const filteredSelectedDiagnoses = computed(() => {
  if (!selectedVisit.value) return []
  const query = normalizeSearchText(visitDetailKeywordQuery.value)
  const department = normalizeSearchText(visitDetailDepartmentFilter.value)
  return selectedVisit.value.diagnoses.filter((diagnosis: any) =>
    (!department || normalizeSearchText(diagnosis.department) === department) &&
    (!query || diagnosisMatchesKeyword(diagnosis, query))
  )
})

const dedupeById = (rows: any[]) => {
  const seen = new Set<string>()
  return rows.filter((row) => {
    const key = String(row?.id || JSON.stringify(row))
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const hasRecordedText = (value: any) => {
  const text = String(value ?? '').trim().toLowerCase()
  return Boolean(text && !['not recorded', 'norecord', 'unknown', 'none', 'null'].includes(text))
}

const filterRecordedMedications = (rows: any[]) =>
  rows.filter((row) => hasRecordedText(row?.medication))

const selectedVisitMedications = computed(() =>
  filterRecordedMedications(
    dedupeById(filteredSelectedDiagnoses.value.flatMap((diagnosis: any) =>
      diagnosis.related_medications || []
    ))
  )
)

const selectedVisitObservations = computed(() =>
  dedupeById(filteredSelectedDiagnoses.value.flatMap((diagnosis: any) =>
    diagnosis.related_observations || []
  ))
)

const selectedVisitProcedures = computed(() =>
  dedupeById(filteredSelectedDiagnoses.value.flatMap((diagnosis: any) =>
    diagnosis.related_procedures || []
  ))
)

const resolveVisitGroupKey = (
  grouped: Map<string, any>,
  encounterId: string,
  dateKey: string,
  fallback: string,
) => {
  if (encounterId) {
    return `encounter:${encounterId}`
  }
  if (dateKey) {
    const sameDayVisit = Array.from(grouped.values()).find((visit) => visit.dateKey === dateKey)
    if (sameDayVisit) {
      return sameDayVisit.key
    }
    return `date:${dateKey}`
  }
  return fallback
}

const dedupeRecords = (rows: any[]) => {
  const seen = new Set<string>()
  return rows.filter((row) => {
    const key = String(row?.id || [
      row?.code,
      row?.medication,
      row?.value,
      row?.authored_on,
      row?.effective_datetime,
      row?.performed_datetime,
      row?.start,
    ].join('|'))
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const diagnosisSourceRows = computed(() => {
  const rawConditions = currentRecord.value?.raw_record?.conditions
  if (currentPatient.value?.scope === 'EXTRA' && Array.isArray(rawConditions)) {
    return rawConditions.map((condition: any, index: number) => ({
      ...condition,
      name: condition.code || '',
      department: formatPrimaryDepartment(condition.department) || 'Not Classified',
      status: condition.clinical_status || 'active',
      date: condition.recorded_date || '',
      recorded_date: condition.recorded_date || '',
      _fallbackKey: `diagnosis:${index}`,
    }))
  }

  return (currentRecord.value?.diagnosis_list || []).map((diagnosis: any, index: number) => ({
    ...diagnosis,
    department: formatPrimaryDepartment(diagnosis.department) || 'Not Classified',
    _fallbackKey: `diagnosis:${index}`,
  }))
})

const visitRows = computed(() => {
  const diagnoses = diagnosisSourceRows.value
  const grouped = new Map<string, any>()

  for (const diagnosis of diagnoses) {
    const encounters = Array.isArray(diagnosis.related_encounters) ? diagnosis.related_encounters : []
    const medications = filterRecordedMedications(
      Array.isArray(diagnosis.related_medications) ? diagnosis.related_medications : []
    )
    const observations = Array.isArray(diagnosis.related_observations) ? diagnosis.related_observations : []
    const procedures = Array.isArray(diagnosis.related_procedures) ? diagnosis.related_procedures : []
    const firstEncounter = encounters[0]
    const diagnosisEncounterId = getEncounterId(diagnosis)
    const diagnosisDateKey = getClinicalDateKey(diagnosis)
    const firstEncounterId = getEncounterId(firstEncounter, true)
    const firstEncounterDateKey = getDateKey(firstEncounter?.start)
    const key = resolveVisitGroupKey(
      grouped,
      firstEncounterId || diagnosisEncounterId,
      firstEncounterDateKey || diagnosisDateKey,
      diagnosis._fallbackKey || `diagnosis:${diagnosis.name || ''}`,
    )
    const date = firstEncounter?.start || diagnosis.date || diagnosis.recorded_date
    const existing = grouped.get(key)

    if (existing) {
      existing.diagnoses.push(diagnosis)
      existing.encounters = dedupeRecords([...existing.encounters, ...encounters])
      existing.medications = dedupeRecords([...existing.medications, ...medications])
      existing.observations = dedupeRecords([...existing.observations, ...observations])
      existing.procedures = dedupeRecords([...existing.procedures, ...procedures])
      existing.department = collectVisitDepartments(existing)
      existing.visitType = joinUnique(existing.encounters.map((item: any) => cleanMedicalText(item.type)), VISIT_TYPE_FALLBACK)
      existing.class = joinUnique(existing.encounters.map((item: any) => normalizeVisitClass(item.class)), VISIT_CLASS_FALLBACK)
      existing.status = joinUnique(existing.encounters.map((item: any) => item.status))
      existing.doctorName = joinUnique([
        ...existing.encounters.map((item: any) => getDoctorDisplayName(item)),
        ...existing.diagnoses.map((item: any) => getDoctorDisplayName(item)),
      ], 'Unknown')
      existing.dateKey = existing.dateKey || firstEncounterDateKey || diagnosisDateKey
      continue
    }

    grouped.set(key, {
      key,
      dateKey: firstEncounterDateKey || diagnosisDateKey,
      date,
      department: diagnosis.department || '',
      visitType: joinUnique(encounters.map((item: any) => cleanMedicalText(item.type)), VISIT_TYPE_FALLBACK),
      class: joinUnique(encounters.map((item: any) => normalizeVisitClass(item.class)), VISIT_CLASS_FALLBACK),
      status: joinUnique(encounters.map((item: any) => item.status)),
      doctorName: joinUnique([
        ...encounters.map((item: any) => getDoctorDisplayName(item)),
        getDoctorDisplayName(diagnosis),
      ], 'Unknown'),
      diagnoses: [diagnosis],
      encounters,
      medications,
      observations,
      procedures,
    })

    const createdVisit = grouped.get(key)
    if (createdVisit) {
      createdVisit.department = collectVisitDepartments(createdVisit)
    }
  }

  return Array.from(grouped.values()).filter((visit) =>
    visit.diagnoses.length > 0
  ).sort((first, second) => {
    const firstTime = new Date(first.date || '').getTime()
    const secondTime = new Date(second.date || '').getTime()
    if (Number.isNaN(firstTime) && Number.isNaN(secondTime)) return 0
    if (Number.isNaN(firstTime)) return 1
    if (Number.isNaN(secondTime)) return -1
    return secondTime - firstTime
  })
})

const filteredVisitRows = computed(() => {
  const dateQuery = normalizeSearchText(diagnosisDateQuery.value)
  if (!dateQuery) return visitRows.value

  return visitRows.value.filter((item) => {
    const dateSearchable = normalizeSearchText([
      item.visitType,
      item.date,
      item.dateKey,
      formatDate(item.date),
      item.diagnoses.map((diagnosis: any) => diagnosis.date).join(' '),
      item.diagnoses.map((diagnosis: any) => diagnosis.recorded_date).join(' '),
    ].join(' '))

    return dateSearchable.includes(dateQuery)
  })
})

// 按状态和范围分组
const fullAccessPatients = computed(() => 
  patients.value.filter(p => p.consent_status === 'ACTIVE' && p.scope === 'EXTRA')
)

const defaultAccessPatients = computed(() => 
  patients.value.filter(p => p.consent_status === 'ACTIVE' && p.scope === 'DEFAULT')
)

const pendingPatients = computed(() => 
  patients.value.filter(p => p.consent_status === 'PENDING')
)

const rejectedPatients = computed(() => 
  patients.value.filter(p => p.consent_status === 'REJECTED')
)

const revokedPatients = computed(() => 
  patients.value.filter(p => p.consent_status === 'REVOKED')
)

const expiredPatients = computed(() =>
  patients.value.filter(p => p.consent_status === 'EXPIRED')
)

// 获取患者列表
const loadPatients = async () => {
  try {
    const res: any = await getMyPatients()
    if (res && res.patient_list) {
      patients.value = res.patient_list
    }
  } catch (err) {
    console.error('Failed to load patients:', err)
    ElMessage.error('Failed to load patients')
  }
}

// 搜索患者
const searchPatients = async () => {
  if (!searchKeyword.value.trim()) {
    searchResults.value = []
    return
  }
  
  try {
    const data = await searchPatientsApi(searchKeyword.value)
    searchResults.value = data.patients || []
  } catch (err) {
    console.error('Search failed:', err)
    ElMessage.error('Search failed')
  }
}

// 查看病历
const openRecord = async (patient: any) => {
  try {
    const res: any = await getPatientRecord(patient.id)
    currentPatient.value = patient
    currentRecord.value = res.medical_record
    diagnosisDateQuery.value = ''
    selectedVisit.value = null
    visitDetailVisible.value = false
    recordDialogVisible.value = true
  } catch (err) {
    ElMessage.error('Failed to load medical record')
  }
}

const viewVisitDetail = (visit: any) => {
  selectedVisit.value = visit
  visitDetailKeywordQuery.value = ''
  visitDetailDepartmentFilter.value = ''
  visitDetailVisible.value = true
}

const loadDoctorProfile = async () => {
  try {
    doctorProfile.value = await getDoctorProfile()
    if (doctorProfile.value) {
      doctorName.value = doctorProfile.value.name || doctorProfile.value.username
      globalDepartment.value = doctorProfile.value.department || ''
    }
  } catch (err) {
    console.error('Failed to load doctor profile:', err)
  }
}

// 新增病历表单操作
const addEncounter = () => {
  newRecordForm.value.encounters.push({
    type: '',
    class: '',
    status: 'finished',
    start: getBeijingDateTimeValue(),
    doctor_name: doctorName.value,
    doctor_department: globalDepartment.value
  })
}

const removeEncounter = (index: number) => {
  newRecordForm.value.encounters.splice(index, 1)
}

const addCondition = () => {
  newRecordForm.value.conditions.push({
    code: '',
    clinical_status: 'active',
    recorded_date: getBeijingDateTimeValue(),
    doctor_name: doctorName.value,
    doctor_department: globalDepartment.value
  })
}

const removeCondition = (index: number) => {
  newRecordForm.value.conditions.splice(index, 1)
}

const addObservation = () => {
  newRecordForm.value.observations.push({
    code: '',
    value: '',
    status: 'final',
    effective_datetime: getBeijingDateTimeValue(),
    doctor_name: doctorName.value,
    doctor_department: globalDepartment.value
  })
}

const removeObservation = (index: number) => {
  newRecordForm.value.observations.splice(index, 1)
}

const addMedication = () => {
  newRecordForm.value.medications.push({
    medication: '',
    status: 'active',
    authored_on: getBeijingDateTimeValue(),
    stop_date: '',
    doctor_name: doctorName.value,
    doctor_department: globalDepartment.value
  })
}

const removeMedication = (index: number) => {
  newRecordForm.value.medications.splice(index, 1)
}

const addProcedure = () => {
  newRecordForm.value.procedures.push({
    code: '',
    status: 'completed',
    performed_datetime: getBeijingDateTimeValue(),
    doctor_name: doctorName.value,
    doctor_department: globalDepartment.value
  })
}

const removeProcedure = (index: number) => {
  newRecordForm.value.procedures.splice(index, 1)
}

const resetNewRecordForm = () => {
  newRecordForm.value = {
    encounters: [],
    conditions: [],
    observations: [],
    medications: [],
    procedures: []
  }
  // 重置科室和医生名为当前医生信息
  globalDepartment.value = doctorProfile.value?.department || ''
  doctorName.value = doctorProfile.value?.name || doctorProfile.value?.username || ''
}

// 打开新增病历弹窗
const openAddRecord = () => {
  resetNewRecordForm()
  // 自动填充医生的科室和姓名
  if (doctorProfile.value) {
    globalDepartment.value = doctorProfile.value.department || ''
    doctorName.value = doctorProfile.value.name || doctorProfile.value.username || ''
  }
  addEncounter()
  editDialogVisible.value = true
}

// 保存新记录
const saveNewRecord = async () => {
  if (!currentPatient.value) {
    ElMessage.error('No patient selected')
    return
  }

  if (!globalDepartment.value.trim()) {
    ElMessage.warning('Please enter a department for this record')
    return
  }

  // 为所有记录设置 department 和 doctor_name
  const recordTime = Date.now()
  for (const [index, encounter] of newRecordForm.value.encounters.entries()) {
    encounter.id = encounter.id || `doctor-encounter-${recordTime}-${index + 1}`
    delete encounter.department
    encounter.doctor_name = doctorName.value
    encounter.doctor_department = globalDepartment.value
  }

  const primaryEncounterId = newRecordForm.value.encounters[0]?.id || ''
  const applyConditionMetadata = (items: any[]) => {
    for (const item of items) {
      item.department = globalDepartment.value
      item.doctor_name = doctorName.value
      if (primaryEncounterId && !item.encounter_id) {
        item.encounter_id = primaryEncounterId
      }
    }
  }

  const applyVisitLink = (items: any[]) => {
    for (const item of items) {
      delete item.department
      item.doctor_name = doctorName.value
      if (primaryEncounterId && !item.encounter_id) {
        item.encounter_id = primaryEncounterId
      }
    }
  }

  applyConditionMetadata(newRecordForm.value.conditions)
  applyVisitLink(newRecordForm.value.observations)
  applyVisitLink(newRecordForm.value.medications)
  applyVisitLink(newRecordForm.value.procedures)

  const hasData = 
    newRecordForm.value.encounters.length > 0 ||
    newRecordForm.value.conditions.length > 0 ||
    newRecordForm.value.observations.length > 0 ||
    newRecordForm.value.medications.length > 0 ||
    newRecordForm.value.procedures.length > 0

  if (!hasData) {
    ElMessage.warning('Please add at least one medical record item')
    return
  }

  savingRecord.value = true
  try {
    await addPatientRecord(currentPatient.value.id, newRecordForm.value)
    ElMessage.success('New medical record added successfully')
    editDialogVisible.value = false
    resetNewRecordForm()
    await openRecord(currentPatient.value)
  } catch (err: any) {
    const errorMsg = err.response?.data?.detail || 'Failed to add medical record'
    ElMessage.error(errorMsg)
  } finally {
    savingRecord.value = false
  }
}

// 打开申请弹窗
const openApplyDialog = (patient: any, scope: string = 'EXTRA') => {
  applyForm.value.patient_id = patient.id
  applyForm.value.patient_name = patient.full_name
  applyForm.value.record_scope = scope
  applyForm.value.reason = ''
  applyDialogVisible.value = true
}

// 提交申请
const submitApply = async () => {
  if (!applyForm.value.reason.trim()) {
    ElMessage.warning('Please provide a reason for your request')
    return
  }
  
  try {
    await submitAccessRequest({
      patient_id: applyForm.value.patient_id,
      record_scope: applyForm.value.record_scope,
      reason: applyForm.value.reason
    })
    ElMessage.success('Access request submitted, waiting for patient approval')
    applyDialogVisible.value = false
    await loadPatients()
  } catch (err: any) {
    const errorMsg = err.response?.data?.detail || 'Failed to submit request'
    ElMessage.error(errorMsg)
  }
}

// 辅助函数
const getScopeText = (scope: string) => {
  if (!scope) return 'Default'
  const map: Record<string, string> = {
    'DEFAULT': 'Default',
    'EXTRA': 'Full Access'
  }
  return map[scope] || 'Default'
}

onMounted(() => {
  loadDoctorProfile()
  loadPatients()
  window.setTimeout(() => {
    showSignInAlert.value = false
  }, 2000)
})
</script>

<template>
  <DashboardLayout :title="dashboardTitle" :display-name="doctorProfile?.name">
    <Transition name="dashboard-alert-fade">
      <el-alert
        v-if="showSignInAlert"
        title="Doctor account signed in successfully."
        type="success"
        show-icon
        :closable="false"
        class="mb-4"
      />
    </Transition>

    <el-card v-if="doctorProfile" class="doctor-profile-card" shadow="never">
      <strong>{{ doctorProfile.name || doctorProfile.username }}</strong>
      <span>{{ doctorProfile.department || 'No department' }}</span>
      <span>{{ doctorProfile.license_no || 'No license number' }}</span>
    </el-card>

    <el-tabs v-model="activeTab">
      <!-- 我的病人列表 Tab -->
      <el-tab-pane label="My Patients" name="patients">
        <!-- Full Access 分组 -->
        <div class="mb-6">
          <h3 class="mb-2">
            Full Access 
            <el-tag type="success" size="small">{{ fullAccessPatients.length }}</el-tag>
          </h3>
          <el-table :data="fullAccessPatients" border stripe>
            <el-table-column prop="full_name" label="Patient Name" min-width="200" />
            <el-table-column prop="gender" label="Gender" width="80" />
            <el-table-column label="Birth Date" width="120">
              <template #default="{ row }">
                {{ formatDate(row.birth_date) }}
              </template>
            </el-table-column>
            <el-table-column label="Scope" width="120">
              <template #default="{ row }">
                <el-tag type="success" size="small">
                  {{ getScopeText(row.scope) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Action" min-width="280">
              <template #default="{ row }">
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                  <el-button
                    type="primary"
                    size="small"
                    @click="openRecord(row)"
                  >
                    View Record
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- Default Access 分组 -->
        <div class="mb-6">
          <h3 class="mb-2">
            Default Access 
            <el-tag type="info" size="small">{{ defaultAccessPatients.length }}</el-tag>
          </h3>
          <el-table :data="defaultAccessPatients" border stripe>
            <el-table-column prop="full_name" label="Patient Name" min-width="200" />
            <el-table-column prop="gender" label="Gender" width="80" />
            <el-table-column label="Birth Date" width="120">
              <template #default="{ row }">
                {{ formatDate(row.birth_date) }}
              </template>
            </el-table-column>
            <el-table-column label="Scope" width="120">
              <template #default="{ row }">
                <el-tag type="info" size="small">
                  {{ getScopeText(row.scope) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Action" min-width="280">
              <template #default="{ row }">
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                  <el-button
                    type="primary"
                    size="small"
                    @click="openRecord(row)"
                  >
                    View Record
                  </el-button>
                  <el-button
                    type="success"
                    size="small"
                    @click="openApplyDialog(row, 'EXTRA')"
                  >
                    Apply Full Access
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- Pending Approval 分组 -->
        <div class="mb-6">
          <h3 class="mb-2">
            Pending Approval 
            <el-tag type="warning" size="small">{{ pendingPatients.length }}</el-tag>
          </h3>
          <el-table :data="pendingPatients" border stripe>
            <el-table-column prop="full_name" label="Patient Name" min-width="200" />
            <el-table-column prop="gender" label="Gender" width="80" />
            <el-table-column label="Birth Date" width="120">
              <template #default="{ row }">
                {{ formatDate(row.birth_date) }}
              </template>
            </el-table-column>
            <el-table-column label="Scope" width="120">
              <template #default="{ row }">
                <el-tag type="warning" size="small">
                  {{ getScopeText(row.scope) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Action" min-width="280">
              <template #default>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                  <el-button
                    type="primary"
                    size="small"
                    disabled
                  >
                    View Record
                  </el-button>
                  <el-button
                    type="success"
                    size="small"
                    disabled
                  >
                    Apply Full Access
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- Rejected 分组 -->
        <div class="mb-6">
          <h3 class="mb-2">
            Rejected 
            <el-tag type="danger" size="small">{{ rejectedPatients.length }}</el-tag>
          </h3>
          <el-table :data="rejectedPatients" border stripe>
            <el-table-column prop="full_name" label="Patient Name" min-width="200" />
            <el-table-column prop="gender" label="Gender" width="80" />
            <el-table-column label="Birth Date" width="120">
              <template #default="{ row }">
                {{ formatDate(row.birth_date) }}
              </template>
            </el-table-column>
            <el-table-column label="Scope" width="120">
              <template #default>
                <el-tag type="danger" size="small">
                  Rejected
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Action" min-width="280">
              <template #default="{ row }">
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                  <el-button
                    type="primary"
                    size="small"
                    @click="openApplyDialog(row, 'DEFAULT')"
                  >
                    Re-apply Default
                  </el-button>
                  <el-button
                    type="success"
                    size="small"
                    @click="openApplyDialog(row, 'EXTRA')"
                  >
                    Re-apply Full Access
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- Revoked 分组 -->
        <div class="mb-6">
          <h3 class="mb-2">
            Revoked 
            <el-tag type="danger" size="small">{{ revokedPatients.length }}</el-tag>
          </h3>
          <el-table :data="revokedPatients" border stripe>
            <el-table-column prop="full_name" label="Patient Name" min-width="200" />
            <el-table-column prop="gender" label="Gender" width="80" />
            <el-table-column label="Birth Date" width="120">
              <template #default="{ row }">
                {{ formatDate(row.birth_date) }}
              </template>
            </el-table-column>
            <el-table-column label="Scope" width="120">
              <template #default>
                <el-tag type="danger" size="small">
                  Revoked
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Action" min-width="280">
              <template #default>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                  <el-button
                    type="primary"
                    size="small"
                    disabled
                  >
                    View Record
                  </el-button>
                  <el-button
                    type="success"
                    size="small"
                    disabled
                  >
                    Apply Full Access
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- Expired 分组 -->
        <div class="mb-6">
          <h3 class="mb-2">
            Expired Access
            <el-tag type="warning" size="small">{{ expiredPatients.length }}</el-tag>
          </h3>
          <el-table :data="expiredPatients" border stripe>
            <el-table-column prop="full_name" label="Patient Name" min-width="200" />
            <el-table-column prop="gender" label="Gender" width="80" />
            <el-table-column label="Birth Date" width="120">
              <template #default="{ row }">
                {{ formatDate(row.birth_date) }}
              </template>
            </el-table-column>
            <el-table-column label="Scope" width="120">
              <template #default="{ row }">
                <el-tag type="warning" size="small">
                  {{ getScopeText(row.scope) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Action" min-width="280">
              <template #default="{ row }">
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                  <el-button
                    type="primary"
                    size="small"
                    @click="openApplyDialog(row, 'DEFAULT')"
                  >
                    Re-apply Default
                  </el-button>
                  <el-button
                    type="success"
                    size="small"
                    @click="openApplyDialog(row, 'EXTRA')"
                  >
                    Re-apply Full Access
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 搜索新患者 Tab -->
      <el-tab-pane label="Search Patients" name="search">
        <div class="mb-4">
          <el-input
            v-model="searchKeyword"
            placeholder="Search by patient name"
            style="width: 300px; margin-right: 10px"
            @input="searchPatients"
            @keyup.enter="searchPatients"
          />
          <el-button type="primary" @click="searchPatients">Search</el-button>
        </div>

        <el-table :data="searchResults" border stripe>
          <el-table-column prop="full_name" label="Patient Name" />
          <el-table-column prop="gender" label="Gender" width="70" />
          <el-table-column label="Birth Date" width="120">
            <template #default="{ row }">
              {{ formatDate(row.birth_date) }}
            </template>
          </el-table-column>
          <el-table-column label="Status" width="150">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'ACTIVE' && row.scope === 'EXTRA'" type="success" size="small">
                Full Access Granted
              </el-tag>
              <el-tag v-else-if="row.status === 'ACTIVE' && row.scope === 'DEFAULT'" type="info" size="small">
                Default Access
              </el-tag>
              <el-tag v-else-if="row.status === 'PENDING'" type="warning" size="small">
                Pending
              </el-tag>
              <el-tag v-else-if="row.status === 'REJECTED'" type="danger" size="small">
                Rejected
              </el-tag>
              <el-tag v-else-if="row.status === 'EXPIRED'" type="warning" size="small">
                Expired
              </el-tag>
              <el-tag v-else type="info" size="small">
                No Access
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="Action" width="300">
            <template #default="{ row }">
              <span v-if="row.status === 'ACTIVE' && row.scope === 'EXTRA'" class="text-muted">
                ✓ Full Access Already Granted
              </span>
              <div v-else-if="row.status === 'ACTIVE' && row.scope === 'DEFAULT'" style="display: flex; gap: 8px;">
                <el-button type="success" size="small" @click="openApplyDialog(row, 'EXTRA')">
                  Apply Full Access
                </el-button>
              </div>
              <span v-else-if="row.status === 'PENDING'" class="text-muted">
                Request Pending
              </span>
              <div v-else-if="row.status === 'REJECTED'" style="display: flex; gap: 8px;">
                <el-button type="primary" size="small" @click="openApplyDialog(row, 'DEFAULT')">
                  Re-apply Default
                </el-button>
                <el-button type="success" size="small" @click="openApplyDialog(row, 'EXTRA')">
                  Re-apply Full Access
                </el-button>
              </div>
              <div v-else-if="row.status === 'EXPIRED'" style="display: flex; gap: 8px;">
                <el-button type="primary" size="small" @click="openApplyDialog(row, 'DEFAULT')">
                  Re-apply Default
                </el-button>
                <el-button type="success" size="small" @click="openApplyDialog(row, 'EXTRA')">
                  Re-apply Full Access
                </el-button>
              </div>
              <div v-else style="display: flex; gap: 8px;">
                <el-button type="primary" size="small" @click="openApplyDialog(row, 'DEFAULT')">
                  Apply Default Access
                </el-button>
                <el-button type="success" size="small" @click="openApplyDialog(row, 'EXTRA')">
                  Apply Full Access
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- View Record Dialog -->
    <el-dialog v-model="recordDialogVisible" title="Patient Medical Record" width="80%">
      <div v-if="currentRecord">
        <div class="record-dialog-actions">
          <div class="record-trace">
            <span>Record ID: {{ currentRecord.record_id || 'None' }}</span>
            <span v-if="currentRecord.updated_at">
              Last updated: {{ formatDate(currentRecord.updated_at) }}
            </span>
            <span v-if="currentRecord.updated_by_doctor_id">
              Updated by doctor user ID: {{ currentRecord.updated_by_doctor_id }}
            </span>
          </div>
          <el-button type="warning" @click="openAddRecord">
            Add New Record
          </el-button>
        </div>

        <el-descriptions title="Basic Info" border :column="2" class="mb-4">
          <el-descriptions-item label="Name">{{ currentRecord.name }}</el-descriptions-item>
          <el-descriptions-item label="Gender">{{ currentRecord.gender }}</el-descriptions-item>
          <el-descriptions-item label="Phone">{{ currentRecord.phone }}</el-descriptions-item>
          <el-descriptions-item label="Address">{{ currentRecord.address }}</el-descriptions-item>
          <el-descriptions-item label="Birth Date">{{ formatDate(currentRecord.birth_date) }}</el-descriptions-item>
        </el-descriptions>

        <el-descriptions title="Summary" border :column="2" class="mb-4">
          <el-descriptions-item label="Visits">{{ visitRows.length }}</el-descriptions-item>
          <el-descriptions-item label="Diagnoses">{{ currentRecord.diagnoses }}</el-descriptions-item>
          <el-descriptions-item label="Lab / Vital Count">{{ currentRecord.lab_results?.length || 0 }}</el-descriptions-item>
          <el-descriptions-item label="Medications Count">{{ currentRecord.medications?.length || 0 }}</el-descriptions-item>
          <el-descriptions-item label="Procedures Count">{{ currentRecord.procedures?.length || 0 }}</el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="currentPatient?.scope === 'DEFAULT'"
          title="Default access only shows medical records from the last year."
          type="info"
          show-icon
          :closable="false"
          class="mb-4"
        />

        <div class="record-section-header mb-2">
          <h3 class="font-bold">Visits</h3>
          <el-input
            v-model="diagnosisDateQuery"
            clearable
            class="record-filter"
            placeholder="Search by time, e.g. 2024, 2024-05-20, 2024-05-20 14:30"
          />
        </div>
        <el-table :data="filteredVisitRows" border>
          <el-table-column prop="doctorName" label="Doctor" width="150" />
          <el-table-column prop="department" label="Department" width="150" />
          <el-table-column prop="visitType" label="Visit Type" min-width="220" />
          <el-table-column prop="class" label="Class" width="120" />
          <el-table-column label="Date" width="160">
            <template #default="{ row }">
              {{ formatDateTime(row.date) }}
            </template>
          </el-table-column>
          <el-table-column label="Diagnoses" width="100">
            <template #default="{ row }">
              {{ row.diagnoses.length }}
            </template>
          </el-table-column>
          <el-table-column label="Lab / Vital" width="100">
            <template #default="{ row }">
              {{ row.observations.length }}
            </template>
          </el-table-column>
          <el-table-column label="Medications" width="110">
            <template #default="{ row }">
              {{ row.medications.length }}
            </template>
          </el-table-column>
          <el-table-column label="Procedures" width="100">
            <template #default="{ row }">
              {{ row.procedures.length }}
            </template>
          </el-table-column>
          <el-table-column label="Detail" width="80">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="viewVisitDetail(row)">
                View
              </el-button>
            </template>
          </el-table-column>
        </el-table>

      </div>
    </el-dialog>

    <!-- 诊断详情弹窗 -->
    <el-dialog v-model="visitDetailVisible" :title="selectedVisit?.visitType || 'Visit Detail'" width="70%">
      <div v-if="selectedVisit">
        <el-descriptions title="Visit Information" border :column="2" class="mb-4">
          <el-descriptions-item label="Doctor">{{ selectedVisit.doctorName || 'Unknown' }}</el-descriptions-item>
          <el-descriptions-item label="Visit Type">{{ selectedVisit.visitType }}</el-descriptions-item>
          <el-descriptions-item label="Department">{{ selectedVisit.department }}</el-descriptions-item>
          <el-descriptions-item label="Class">{{ selectedVisit.class }}</el-descriptions-item>
          <el-descriptions-item label="Status">{{ selectedVisit.status }}</el-descriptions-item>
          <el-descriptions-item label="Date">{{ formatDateTime(selectedVisit.date) }}</el-descriptions-item>
        </el-descriptions>

        <div class="visit-detail-filters mb-4">
          <el-select
            v-model="visitDetailDepartmentFilter"
            clearable
            filterable
            placeholder="Department"
          >
            <el-option
              v-for="department in selectedVisitDepartmentOptions"
              :key="department"
              :label="department"
              :value="department"
            />
          </el-select>
          <el-input
            v-model="visitDetailKeywordQuery"
            clearable
            placeholder="Diagnosis"
          />
        </div>

        <h3 class="font-bold mb-2">Diagnoses</h3>
        <el-table :data="filteredSelectedDiagnoses" border class="mb-4">
          <el-table-column prop="department" label="Department" width="150" />
          <el-table-column prop="name" label="Diagnosis" min-width="260" />
          <el-table-column prop="status" label="Status" width="140" />
          <el-table-column label="Date" width="190">
            <template #default="{ row }">
              {{ formatDateTime(row.date) }}
            </template>
          </el-table-column>
        </el-table>

        <h3 class="font-bold mb-2">Medications</h3>
        <el-table :data="selectedVisitMedications" border class="mb-4">
          <el-table-column prop="medication" label="Medication" min-width="280" />
          <el-table-column prop="status" label="Status" width="140" />
          <el-table-column label="Prescribed At" width="190">
            <template #default="{ row }">
              {{ formatDateTime(row.authored_on) }}
            </template>
          </el-table-column>
        </el-table>

        <h3 class="font-bold mb-2">Lab / Vital Results</h3>
        <el-table :data="selectedVisitObservations" border class="mb-4">
          <el-table-column prop="code" label="Item" min-width="260" />
          <el-table-column prop="value" label="Result" min-width="180" />
          <el-table-column prop="status" label="Status" width="140" />
          <el-table-column label="Date" width="190">
            <template #default="{ row }">
              {{ formatDateTime(row.effective_datetime) }}
            </template>
          </el-table-column>
        </el-table>

        <h3 class="font-bold mb-2">Procedures</h3>
        <el-table :data="selectedVisitProcedures" border class="mb-4">
          <el-table-column prop="code" label="Procedure" min-width="280" />
          <el-table-column prop="status" label="Status" width="140" />
          <el-table-column label="Date" width="190">
            <template #default="{ row }">
              {{ formatDateTime(row.performed_datetime) }}
            </template>
          </el-table-column>
        </el-table>

      </div>
    </el-dialog>

    <!-- Add New Record Dialog -->
    <el-dialog v-model="editDialogVisible" title="Add New Medical Record" width="90%">
      <el-alert
        title="Add a new medical record. This will be appended to the patient's existing records."
        type="info"
        show-icon
        :closable="false"
        class="mb-4"
      />

      <!-- 全局科室和医生信息 - 自动读取，只读不可修改 -->
      <div class="form-section global-department">
        <div style="display: flex; gap: 20px; flex-wrap: wrap;">
          <div style="flex: 1;">
            <h3 class="section-title">Record Department</h3>
            <el-input 
              v-model="globalDepartment" 
              :placeholder="doctorProfile?.department ? 'Auto-filled from your profile' : 'No department assigned'"
              disabled
              style="width: 100%"
            />
          </div>
          <div style="flex: 1;">
            <h3 class="section-title">Doctor Name</h3>
            <el-input 
              :value="doctorName"
              placeholder="Auto-filled from your profile"
              disabled
              style="width: 100%"
            />
          </div>
        </div>
      </div>

      <div style="max-height: 70vh; overflow-y: auto; padding-right: 8px;">
        <!-- 就诊信息 -->
        <div class="form-section">
          <h3 class="section-title">Visit Information</h3>
          <el-table :data="newRecordForm.encounters" border style="width: 100%">
            <el-table-column label="Visit Type" width="200">
              <template #default="{ $index }">
                <el-input v-model="newRecordForm.encounters[$index].type" placeholder="e.g., General examination" />
              </template>
            </el-table-column>
            <el-table-column label="Class" width="150">
              <template #default="{ $index }">
                <el-select v-model="newRecordForm.encounters[$index].class" placeholder="Select class" style="width: 100%">
                  <el-option label="AMB" value="AMB" />
                  <el-option label="EMER" value="EMER" />
                  <el-option label="IMP" value="IMP" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="Status" width="120">
              <template #default="{ $index }">
                <el-select v-model="newRecordForm.encounters[$index].status" placeholder="Status">
                  <el-option label="Finished" value="finished" />
                  <el-option label="In Progress" value="in-progress" />
                  <el-option label="Planned" value="planned" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="Date" width="200">
              <template #default="{ $index }">
                <el-date-picker
                  v-model="newRecordForm.encounters[$index].start"
                  type="datetime"
                  placeholder="Select date"
                  format="YYYY-MM-DD HH:mm"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  style="width: 100%"
                />
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="80">
              <template #default="{ $index }">
                <el-button type="danger" size="small" @click="removeEncounter($index)">Remove</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button type="primary" size="small" @click="addEncounter" class="mt-2">
            + Add Visit
          </el-button>
        </div>

        <!-- 诊断 -->
        <div class="form-section">
          <h3 class="section-title">Diagnoses</h3>
          <el-table :data="newRecordForm.conditions" border style="width: 100%">
            <el-table-column label="Diagnosis Code" min-width="300">
              <template #default="{ $index }">
                <el-input v-model="newRecordForm.conditions[$index].code" placeholder="e.g., Diabetes mellitus type 2" />
              </template>
            </el-table-column>
            <el-table-column label="Clinical Status" width="140">
              <template #default="{ $index }">
                <el-select v-model="newRecordForm.conditions[$index].clinical_status">
                  <el-option label="Active" value="active" />
                  <el-option label="Resolved" value="resolved" />
                  <el-option label="Inactive" value="inactive" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="Recorded Date" width="180">
              <template #default="{ $index }">
                <el-date-picker
                  v-model="newRecordForm.conditions[$index].recorded_date"
                  type="datetime"
                  placeholder="Select date and time"
                  format="YYYY-MM-DD HH:mm"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  style="width: 100%"
                />
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="80">
              <template #default="{ $index }">
                <el-button type="danger" size="small" @click="removeCondition($index)">Remove</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button type="primary" size="small" @click="addCondition" class="mt-2">
            + Add Diagnosis
          </el-button>
        </div>

        <!-- 检查结果 -->
        <div class="form-section">
          <h3 class="section-title">Lab / Vital Results</h3>
          <el-table :data="newRecordForm.observations" border style="width: 100%">
            <el-table-column label="Test Name" min-width="250">
              <template #default="{ $index }">
                <el-input v-model="newRecordForm.observations[$index].code" placeholder="e.g., Blood Pressure" />
              </template>
            </el-table-column>
            <el-table-column label="Value" width="200">
              <template #default="{ $index }">
                <el-input v-model="newRecordForm.observations[$index].value" placeholder="e.g., 120/80" />
              </template>
            </el-table-column>
            <el-table-column label="Status" width="120">
              <template #default="{ $index }">
                <el-select v-model="newRecordForm.observations[$index].status">
                  <el-option label="Final" value="final" />
                  <el-option label="Preliminary" value="preliminary" />
                  <el-option label="Corrected" value="corrected" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="Date" width="200">
              <template #default="{ $index }">
                <el-date-picker
                  v-model="newRecordForm.observations[$index].effective_datetime"
                  type="datetime"
                  placeholder="Select date"
                  format="YYYY-MM-DD HH:mm"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  style="width: 100%"
                />
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="80">
              <template #default="{ $index }">
                <el-button type="danger" size="small" @click="removeObservation($index)">Remove</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button type="primary" size="small" @click="addObservation" class="mt-2">
            + Add Lab Result
          </el-button>
        </div>

        <!-- 用药 -->
        <div class="form-section">
          <h3 class="section-title">Medications</h3>
          <el-table :data="newRecordForm.medications" border style="width: 100%">
            <el-table-column label="Medication" min-width="250">
              <template #default="{ $index }">
                <el-input v-model="newRecordForm.medications[$index].medication" placeholder="e.g., Metformin" />
              </template>
            </el-table-column>
            <el-table-column label="Status" width="120">
              <template #default="{ $index }">
                <el-select v-model="newRecordForm.medications[$index].status">
                  <el-option label="Active" value="active" />
                  <el-option label="Completed" value="completed" />
                  <el-option label="Stopped" value="stopped" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="Prescribed Date" width="200">
              <template #default="{ $index }">
                <el-date-picker
                  v-model="newRecordForm.medications[$index].authored_on"
                  type="datetime"
                  placeholder="Select date"
                  format="YYYY-MM-DD HH:mm"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  style="width: 100%"
                />
              </template>
            </el-table-column>
            <el-table-column label="Stop Date" width="200">
              <template #default="{ $index }">
                <el-date-picker
                  v-model="newRecordForm.medications[$index].stop_date"
                  type="datetime"
                  placeholder="Stop date (optional)"
                  format="YYYY-MM-DD HH:mm"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  style="width: 100%"
                />
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="80">
              <template #default="{ $index }">
                <el-button type="danger" size="small" @click="removeMedication($index)">Remove</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button type="primary" size="small" @click="addMedication" class="mt-2">
            + Add Medication
          </el-button>
        </div>

        <!-- 手术 -->
        <div class="form-section">
          <h3 class="section-title">Procedures</h3>
          <el-table :data="newRecordForm.procedures" border style="width: 100%">
            <el-table-column label="Procedure" min-width="300">
              <template #default="{ $index }">
                <el-input v-model="newRecordForm.procedures[$index].code" placeholder="e.g., Appendectomy" />
              </template>
            </el-table-column>
            <el-table-column label="Status" width="120">
              <template #default="{ $index }">
                <el-select v-model="newRecordForm.procedures[$index].status">
                  <el-option label="Completed" value="completed" />
                  <el-option label="In Progress" value="in-progress" />
                  <el-option label="Planned" value="planned" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="Date" width="200">
              <template #default="{ $index }">
                <el-date-picker
                  v-model="newRecordForm.procedures[$index].performed_datetime"
                  type="datetime"
                  placeholder="Select date"
                  format="YYYY-MM-DD HH:mm"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  style="width: 100%"
                />
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="80">
              <template #default="{ $index }">
                <el-button type="danger" size="small" @click="removeProcedure($index)">Remove</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button type="primary" size="small" @click="addProcedure" class="mt-2">
            + Add Procedure
          </el-button>
        </div>
      </div>

      <template #footer>
        <el-button @click="editDialogVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="savingRecord" @click="saveNewRecord">
          Save New Record
        </el-button>
      </template>
    </el-dialog>

    <!-- Apply Access Dialog -->
    <el-dialog v-model="applyDialogVisible" title="Apply for Medical Record Access">
      <el-form :model="applyForm" label-width="120px">
        <el-form-item label="Patient">
          <span>{{ applyForm.patient_name }}</span>
        </el-form-item>
        <el-form-item label="Access Scope">
          <el-select v-model="applyForm.record_scope">
            <el-option label="Default Access" value="DEFAULT" />
            <el-option label="Full Access (EXTRA)" value="EXTRA" />
          </el-select>
        </el-form-item>
        <el-form-item label="Reason">
          <el-input
            v-model="applyForm.reason"
            type="textarea"
            rows="3"
            placeholder="Please explain why you need this access..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="submitApply">Submit Request</el-button>
      </template>
    </el-dialog>
  </DashboardLayout>
</template>

<style scoped>
.mb-2 { margin-bottom: 8px; }
.mb-4 { margin-bottom: 16px; }
.mb-6 { margin-bottom: 24px; }
.mt-2 { margin-top: 8px; }
.font-bold { font-weight: bold; }
.text-muted { color: #909399; }

.doctor-profile-card {
  margin-bottom: 16px;
  border-radius: 8px;
}

.doctor-profile-card :deep(.el-card__body) {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  color: #606266;
}

.doctor-profile-card strong {
  color: #172033;
}

.record-dialog-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.record-trace {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #606266;
  font-size: 13px;
}

.record-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.record-section-header h3 {
  margin: 0;
}

.record-filter {
  width: min(420px, 100%);
}

.visit-detail-filters {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(240px, 1fr);
  gap: 12px;
}

.form-section {
  margin-bottom: 24px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  background-color: #fafafa;
}

.global-department {
  margin-bottom: 16px;
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: #172033;
  padding-bottom: 8px;
  border-bottom: 2px solid #409eff;
  display: inline-block;
}

.dashboard-alert-fade-leave-active {
  transition: opacity 0.4s ease, transform 0.4s ease;
}

.dashboard-alert-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
