<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import DashboardLayout from "../layouts/DashboardLayout.vue"
import { getMyPatients, submitAccessRequest, getPatientRecord, updatePatientRecord } from '../api/doctor'
import { ElMessage } from '../utils/message'

const activeTab = ref('patients')
const searchKeyword = ref('')
const searchResults = ref<any[]>([])
const patients = ref<any[]>([])
const showSignInAlert = ref(true)

// 弹窗相关
const recordDialogVisible = ref(false)
const currentRecord = ref<any>(null)
const currentPatient = ref<any>(null)
const editDialogVisible = ref(false)
const recordEditText = ref('')
const savingRecord = ref(false)
const applyDialogVisible = ref(false)
const applyForm = ref({
  patient_id: 0,
  patient_name: '',
  record_scope: 'EXTRA',
  reason: ''
})

// 日期格式化函数
const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  return dateStr.split('T')[0]
}

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
    const res = await getMyPatients()
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
    const res = await fetch(`http://localhost:8000/api/doctor/search-patients?q=${searchKeyword.value}`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })
    const data = await res.json()
    searchResults.value = data.patients || []
  } catch (err) {
    console.error('Search failed:', err)
    ElMessage.error('Search failed')
  }
}

// 查看病历
const openRecord = async (patient: any) => {
  try {
    const res = await getPatientRecord(patient.id)
    currentPatient.value = patient
    currentRecord.value = res.medical_record
    recordDialogVisible.value = true
  } catch (err) {
    ElMessage.error('Failed to load medical record')
  }
}

const openEditRecord = () => {
  if (!currentRecord.value?.record_id || !currentRecord.value?.raw_record) {
    ElMessage.warning('Full access medical record is required before editing')
    return
  }
  recordEditText.value = JSON.stringify(currentRecord.value.raw_record, null, 2)
  editDialogVisible.value = true
}

const saveRecordEdit = async () => {
  if (!currentPatient.value || !currentRecord.value?.record_id) {
    ElMessage.error('No medical record selected')
    return
  }

  let parsedRecord: Record<string, unknown>
  try {
    parsedRecord = JSON.parse(recordEditText.value)
  } catch {
    ElMessage.error('Record JSON is invalid')
    return
  }

  savingRecord.value = true
  try {
    await updatePatientRecord(currentPatient.value.id, currentRecord.value.record_id, parsedRecord)
    ElMessage.success('Medical record updated')
    editDialogVisible.value = false
    await openRecord(currentPatient.value)
  } catch (err: any) {
    const errorMsg = err.response?.data?.detail || 'Failed to update medical record'
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
  loadPatients()
  window.setTimeout(() => {
    showSignInAlert.value = false
  }, 2000)
})
</script>

<template>
  <DashboardLayout title="Doctor Dashboard">
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

    <el-tabs v-model="activeTab">
      <!-- 我的病人列表 Tab - 5个分组 -->
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
          <el-table-column prop="gender" label="Gender"width="70" />
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
              <!-- 已有 Full Access：不显示任何申请按钮 -->
              <span v-if="row.status === 'ACTIVE' && row.scope === 'EXTRA'" class="text-muted">
                ✓ Full Access Already Granted
              </span>
              
              <!-- 已有 Default Access：只显示 Apply Full Access -->
              <div v-else-if="row.status === 'ACTIVE' && row.scope === 'DEFAULT'" style="display: flex; gap: 8px;">
                <el-button
                  type="success"
                  size="small"
                  @click="openApplyDialog(row, 'EXTRA')"
                >
                  Apply Full Access
                </el-button>
              </div>
              
              <!-- 待审批：显示等待中 -->
              <span v-else-if="row.status === 'PENDING'" class="text-muted">
                Request Pending
              </span>
              
              <!-- 已拒绝：显示重新申请按钮 -->
              <div v-else-if="row.status === 'REJECTED'" style="display: flex; gap: 8px;">
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

              <!-- 已过期：允许重新申请 -->
              <div v-else-if="row.status === 'EXPIRED'" style="display: flex; gap: 8px;">
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
              
              <!-- 无任何授权：显示两个按钮 -->
              <div v-else style="display: flex; gap: 8px;">
                <el-button
                  type="primary"
                  size="small"
                  @click="openApplyDialog(row, 'DEFAULT')"
                >
                  Apply Default Access
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
          <el-button
            v-if="currentRecord.record_id && currentRecord.raw_record"
            type="warning"
            @click="openEditRecord"
          >
            Edit Record
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
          <el-descriptions-item label="Visits">{{ currentRecord.visits }}</el-descriptions-item>
          <el-descriptions-item label="Diagnoses">{{ currentRecord.diagnoses }}</el-descriptions-item>
          <el-descriptions-item label="Lab Results">
            <span v-if="typeof currentRecord.lab_results === 'string'">
              {{ currentRecord.lab_results }}
            </span>
            <span v-else>
              <span v-for="(item, idx) in currentRecord.lab_results" :key="idx">
                {{ item.test_name }}: {{ item.value }}<br />
              </span>
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="Medications">
            <span v-if="typeof currentRecord.medications === 'string'">
              {{ currentRecord.medications }}
            </span>
            <span v-else>
              <span v-for="(item, idx) in currentRecord.medications" :key="idx">
                {{ item.name }}<br />
              </span>
            </span>
          </el-descriptions-item>
        </el-descriptions>

        <h3 class="font-bold mb-2">Diagnosis List</h3>
        <el-table :data="currentRecord.diagnosis_list || []" border>
          <el-table-column prop="name" label="Diagnosis" />
          <el-table-column prop="department" label="Department" width="180" />
          <el-table-column prop="status" label="Status" width="100" />
          <el-table-column prop="date" label="Date" width="120" />
        </el-table>
      </div>
    </el-dialog>

    <!-- Edit Record Dialog -->
    <el-dialog v-model="editDialogVisible" title="Edit Medical Record JSON" width="76%">
      <el-alert
        title="This will overwrite the encrypted medical record. The system audits permission and stores updated_at / updated_by_doctor_id, but does not store a content diff."
        type="warning"
        show-icon
        :closable="false"
        class="mb-4"
      />
      <el-input
        v-model="recordEditText"
        type="textarea"
        :rows="20"
        spellcheck="false"
        class="record-json-editor"
      />
      <template #footer>
        <el-button @click="editDialogVisible = false">Cancel</el-button>
        <el-button type="primary" :loading="savingRecord" @click="saveRecordEdit">
          Save Overwrite
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
.font-bold { font-weight: bold; }
.text-muted { color: #909399; }

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

.record-json-editor {
  font-family: Consolas, Monaco, monospace;
}

.dashboard-alert-fade-leave-active {
  transition: opacity 0.4s ease, transform 0.4s ease;
}

.dashboard-alert-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
