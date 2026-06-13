<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessageBox } from "element-plus";

import DashboardLayout from "../layouts/DashboardLayout.vue";
import { ElMessage } from "../utils/message";
import {
  assignDoctorToPatient,
  createAdminUser,
  getAdminOverview,
  listAdminDoctors,
  listAdminPatients,
  listAdminUsers,
  resetAdminUserPassword,
  updateAdminDoctor,
  updateAdminUserStatus,
  type AccountStatus,
  type AdminDoctor,
  type AdminOverview,
  type AdminPatient,
  type AdminUser,
  type ManagedRole,
} from "../api/admin";

const loading = ref(false);
const saving = ref(false);
const overview = ref<AdminOverview | null>(null);
const users = ref<AdminUser[]>([]);
const doctors = ref<AdminDoctor[]>([]);
const patients = ref<AdminPatient[]>([]);
const patientQuery = ref("");
const activeTab = ref("users");
const createDialogOpen = ref(false);
const doctorDialogOpen = ref(false);
const selectedDoctor = ref<AdminDoctor | null>(null);

const createForm = reactive({
  username: "",
  password: "",
  role: "DOCTOR" as ManagedRole,
  name: "",
  department: "",
  license_no: "",
  note: "",
});

const doctorForm = reactive({
  name: "",
  department: "",
  license_no: "",
  note: "",
  verified: false,
  account_status: "ACTIVE" as AccountStatus,
});

const assignmentForm = reactive({
  doctor_user_id: null as number | null,
  patient_id: null as number | null,
  note: "",
});

const departmentOptions = [
  "General Medicine",
  "Internal Medicine",
  "Surgery",
  "Obstetrics and Gynecology",
  "Pediatrics",
  "Dentistry",
  "Mental Health",
  "Rehabilitation and Preventive Care",
];

const approvedDoctors = computed(() =>
  doctors.value.filter((doctor) => doctor.doctor_status === "APPROVED" && doctor.account_status === "ACTIVE"),
);

function formatDateTime(value: string | null) {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusTag(status: string) {
  if (status === "ACTIVE" || status === "APPROVED") {
    return "success";
  }
  if (status === "DISABLED") {
    return "danger";
  }
  return "warning";
}

async function loadAdminData() {
  loading.value = true;
  try {
    const [overviewRes, usersRes, doctorsRes, patientsRes] = await Promise.all([
      getAdminOverview(),
      listAdminUsers(),
      listAdminDoctors(),
      listAdminPatients(patientQuery.value),
    ]);
    overview.value = overviewRes;
    users.value = usersRes.users;
    doctors.value = doctorsRes.doctors;
    patients.value = patientsRes.patients;
  } catch (error) {
    console.error(error);
    ElMessage.error("Failed to load admin dashboard");
  } finally {
    loading.value = false;
  }
}

function openCreateDialog() {
  createForm.username = "";
  createForm.password = "";
  createForm.role = "DOCTOR";
  createForm.name = "";
  createForm.department = "";
  createForm.license_no = "";
  createForm.note = "";
  createDialogOpen.value = true;
}

async function submitCreateUser() {
  if (!createForm.username.trim() || !createForm.password || !createForm.name.trim()) {
    ElMessage.warning("Username, password, and doctor name are required");
    return;
  }

  saving.value = true;
  try {
    await createAdminUser({
      username: createForm.username.trim(),
      password: createForm.password,
      role: createForm.role,
      name: createForm.role === "DOCTOR" ? createForm.name.trim() : undefined,
      department: createForm.role === "DOCTOR" ? createForm.department : undefined,
      license_no: createForm.role === "DOCTOR" ? createForm.license_no : undefined,
      note: createForm.role === "DOCTOR" ? createForm.note : undefined,
    });
    ElMessage.success("Account created");
    createDialogOpen.value = false;
    await loadAdminData();
  } catch (error) {
    console.error(error);
    ElMessage.error("Failed to create account");
  } finally {
    saving.value = false;
  }
}

async function toggleUserStatus(user: AdminUser) {
  const nextStatus: AccountStatus = user.status === "DISABLED" ? "ACTIVE" : "DISABLED";
  try {
    await updateAdminUserStatus(user.id, nextStatus);
    ElMessage.success(`Account ${nextStatus === "ACTIVE" ? "enabled" : "disabled"}`);
    await loadAdminData();
  } catch (error) {
    console.error(error);
    ElMessage.error("Failed to update account status");
  }
}

async function resetPassword(user: AdminUser) {
  try {
    const result = await ElMessageBox.prompt(
      `Reset password for ${user.username}`,
      "Reset Password",
      {
        inputValue: "",
        inputPattern: /^.{1,72}$/,
        inputErrorMessage: "Password must be 1-72 characters",
        confirmButtonText: "Reset",
        cancelButtonText: "Cancel",
      },
    );
    await resetAdminUserPassword(user.id, result.value);
    ElMessage.success("Password reset");
  } catch (error) {
    if (error !== "cancel") {
      console.error(error);
      ElMessage.error("Failed to reset password");
    }
  }
}

function openDoctorDialog(doctor: AdminDoctor) {
  selectedDoctor.value = doctor;
  doctorForm.name = doctor.name || "";
  doctorForm.department = doctor.department || "";
  doctorForm.license_no = doctor.license_no || "";
  doctorForm.note = doctor.note || "";
  doctorForm.verified = doctor.verified;
  doctorForm.account_status = doctor.account_status;
  doctorDialogOpen.value = true;
}

async function submitDoctorUpdate() {
  if (!selectedDoctor.value) {
    return;
  }

  saving.value = true;
  try {
    await updateAdminDoctor(selectedDoctor.value.user_id, {
      name: doctorForm.name.trim(),
      department: doctorForm.department,
      license_no: doctorForm.license_no,
      note: doctorForm.note,
      verified: doctorForm.verified,
      account_status: doctorForm.account_status,
    });
    ElMessage.success("Doctor profile updated");
    doctorDialogOpen.value = false;
    await loadAdminData();
  } catch (error) {
    console.error(error);
    ElMessage.error("Failed to update doctor");
  } finally {
    saving.value = false;
  }
}

async function assignDefaultClinicalAccess() {
  if (!assignmentForm.doctor_user_id || !assignmentForm.patient_id) {
    ElMessage.warning("Select one approved doctor and one patient");
    return;
  }

  saving.value = true;
  try {
    await assignDoctorToPatient({
      doctor_user_id: assignmentForm.doctor_user_id,
      patient_id: assignmentForm.patient_id,
      note: assignmentForm.note,
    });
    ElMessage.success("Default clinical access assigned");
    assignmentForm.note = "";
    await loadAdminData();
  } catch (error) {
    console.error(error);
    ElMessage.error("Failed to assign patient");
  } finally {
    saving.value = false;
  }
}

async function searchPatients() {
  loading.value = true;
  try {
    const res = await listAdminPatients(patientQuery.value);
    patients.value = res.patients;
  } catch (error) {
    console.error(error);
    ElMessage.error("Failed to search patients");
  } finally {
    loading.value = false;
  }
}

onMounted(loadAdminData);
</script>

<template>
  <DashboardLayout title="Admin Dashboard">
    <section v-loading="loading" class="admin-page">
      <section class="summary-grid">
        <el-card shadow="never">
          <span>Users</span>
          <strong>{{ overview?.user_count ?? 0 }}</strong>
        </el-card>
        <el-card shadow="never">
          <span>Doctors</span>
          <strong>{{ overview?.doctor_count ?? 0 }}</strong>
        </el-card>
        <el-card shadow="never">
          <span>Patients</span>
          <strong>{{ overview?.patient_count ?? 0 }}</strong>
        </el-card>
        <el-card shadow="never">
          <span>Disabled</span>
          <strong>{{ overview?.disabled_user_count ?? 0 }}</strong>
        </el-card>
      </section>

      <el-card class="panel" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>Security Boundary</span>
            <el-button :loading="loading" @click="loadAdminData">Refresh</el-button>
          </div>
        </template>
        <div class="boundary-grid">
          <div>
            <span>Medical Records</span>
            <strong>{{ overview?.medical_record_count ?? 0 }}</strong>
          </div>
          <div>
            <span>Consents</span>
            <strong>{{ overview?.consent_count ?? 0 }}</strong>
          </div>
          <div>
            <span>Recent Audit Logs</span>
            <strong>{{ overview?.recent_audit_log_count ?? 0 }}</strong>
          </div>
          <div>
            <span>Hash Chain</span>
            <strong :class="overview?.hash_chain_valid ? 'ok' : 'bad'">
              {{ overview?.hash_chain_valid ? "Valid" : "Needs Check" }}
            </strong>
          </div>
        </div>
        <el-alert
          class="boundary-alert"
          :title="overview?.record_access_note || 'Admin can view counts only. Decrypted records are restricted.'"
          type="info"
          show-icon
          :closable="false"
        />
      </el-card>

      <el-card class="panel" shadow="never">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="Accounts" name="users">
            <div class="toolbar">
              <el-button type="primary" @click="openCreateDialog">Create Account</el-button>
            </div>
            <el-table :data="users" border stripe empty-text="No users">
              <el-table-column prop="id" label="ID" width="70" />
              <el-table-column prop="username" label="Username" min-width="150" />
              <el-table-column prop="role" label="Role" width="110" />
              <el-table-column label="Status" width="120">
                <template #default="{ row }">
                  <el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="Doctor Review" width="140">
                <template #default="{ row }">
                  <el-tag v-if="row.doctor_status" :type="statusTag(row.doctor_status)" size="small">
                    {{ row.doctor_status }}
                  </el-tag>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="Created" min-width="170">
                <template #default="{ row }">
                  {{ formatDateTime(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column label="Last Login" min-width="170">
                <template #default="{ row }">
                  {{ formatDateTime(row.last_login_at) }}
                </template>
              </el-table-column>
              <el-table-column label="Actions" width="220" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click="toggleUserStatus(row)">
                    {{ row.status === "DISABLED" ? "Enable" : "Disable" }}
                  </el-button>
                  <el-button size="small" @click="resetPassword(row)">Reset</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="Doctor Review" name="doctors">
            <el-table :data="doctors" border stripe empty-text="No doctors">
              <el-table-column prop="user_id" label="User ID" width="90" />
              <el-table-column prop="username" label="Username" min-width="150" />
              <el-table-column prop="name" label="Doctor Name" min-width="160" />
              <el-table-column label="Review" width="120">
                <template #default="{ row }">
                  <el-tag :type="statusTag(row.doctor_status)" size="small">
                    {{ row.doctor_status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="Account" width="120">
                <template #default="{ row }">
                  <el-tag :type="statusTag(row.account_status)" size="small">
                    {{ row.account_status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="department" label="Department" min-width="150" />
              <el-table-column prop="license_no" label="License No." min-width="150" />
              <el-table-column prop="note" label="Note" min-width="180" />
              <el-table-column label="Actions" width="130" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="primary" @click="openDoctorDialog(row)">Edit</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="Patient Assignment" name="assignments">
            <div class="assignment-layout">
              <el-form
                label-position="top"
                class="assignment-form"
                @submit.prevent="assignDefaultClinicalAccess"
              >
                <el-form-item label="Approved Doctor">
                  <el-select v-model="assignmentForm.doctor_user_id" filterable placeholder="Select doctor">
                    <el-option
                      v-for="doctor in approvedDoctors"
                      :key="doctor.user_id"
                      :label="`${doctor.name || doctor.username} · ${doctor.department || 'No department'}`"
                      :value="doctor.user_id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="Patient">
                  <el-select v-model="assignmentForm.patient_id" filterable placeholder="Select patient">
                    <el-option
                      v-for="patient in patients"
                      :key="patient.id"
                      :label="`${patient.full_name} · #${patient.id}`"
                      :value="patient.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="Note">
                  <el-input
                    v-model="assignmentForm.note"
                    maxlength="200"
                    @keyup.enter="assignDefaultClinicalAccess"
                  />
                </el-form-item>
                <el-button type="primary" :loading="saving" @click="assignDefaultClinicalAccess">
                  Assign DEFAULT_CLINICAL
                </el-button>
              </el-form>

              <div class="patient-search">
                <div class="toolbar">
                  <el-input
                    v-model="patientQuery"
                    placeholder="Search patient name"
                    clearable
                    @keyup.enter="searchPatients"
                  />
                  <el-button @click="searchPatients">Search</el-button>
                </div>
                <el-table :data="patients" border stripe height="310" empty-text="No patients">
                  <el-table-column prop="id" label="ID" width="80" />
                  <el-table-column prop="full_name" label="Patient" min-width="180" />
                  <el-table-column prop="gender" label="Gender" width="100" />
                  <el-table-column prop="birth_date" label="Birth Date" width="130" />
                </el-table>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>

      <el-dialog v-model="createDialogOpen" title="Create Account" width="520px">
        <el-form label-position="top" @submit.prevent="submitCreateUser">
          <el-form-item label="Role">
            <el-segmented v-model="createForm.role" :options="['DOCTOR']" />
          </el-form-item>
          <el-form-item label="Username">
            <el-input
              v-model="createForm.username"
              maxlength="50"
              @keyup.enter="submitCreateUser"
            />
          </el-form-item>
          <el-form-item label="Password">
            <el-input
              v-model="createForm.password"
              show-password
              maxlength="72"
              @keyup.enter="submitCreateUser"
            />
          </el-form-item>
          <template v-if="createForm.role === 'DOCTOR'">
            <el-form-item label="Doctor Name">
              <el-input
                v-model="createForm.name"
                maxlength="100"
                autocomplete="name"
                @keyup.enter="submitCreateUser"
              />
            </el-form-item>
            <el-form-item label="Department">
              <el-select v-model="createForm.department" filterable placeholder="Select department">
                <el-option
                  v-for="department in departmentOptions"
                  :key="department"
                  :label="department"
                  :value="department"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="License No.">
              <el-input
                v-model="createForm.license_no"
                maxlength="50"
                @keyup.enter="submitCreateUser"
              />
            </el-form-item>
            <el-form-item label="Note">
              <el-input v-model="createForm.note" type="textarea" :rows="3" maxlength="300" />
            </el-form-item>
          </template>
        </el-form>
        <template #footer>
          <el-button @click="createDialogOpen = false">Cancel</el-button>
          <el-button type="primary" :loading="saving" @click="submitCreateUser">Create</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="doctorDialogOpen" title="Doctor Review" width="560px">
        <el-form label-position="top" @submit.prevent="submitDoctorUpdate">
          <el-form-item label="Doctor Name">
            <el-input
              v-model="doctorForm.name"
              maxlength="100"
              autocomplete="name"
              @keyup.enter="submitDoctorUpdate"
            />
          </el-form-item>
          <el-form-item label="Department">
            <el-select v-model="doctorForm.department" filterable placeholder="Select department">
              <el-option
                v-for="department in departmentOptions"
                :key="department"
                :label="department"
                :value="department"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="License No.">
            <el-input
              v-model="doctorForm.license_no"
              maxlength="50"
              @keyup.enter="submitDoctorUpdate"
            />
          </el-form-item>
          <el-form-item label="Account Status">
            <el-select v-model="doctorForm.account_status">
              <el-option label="Active" value="ACTIVE" />
              <el-option label="Disabled" value="DISABLED" />
              <el-option label="Pending" value="PENDING" />
            </el-select>
          </el-form-item>
          <el-form-item label="Review">
            <el-switch
              v-model="doctorForm.verified"
              active-text="Approved"
              inactive-text="Pending"
            />
          </el-form-item>
          <el-form-item label="Note">
            <el-input v-model="doctorForm.note" type="textarea" :rows="4" maxlength="500" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="doctorDialogOpen = false">Cancel</el-button>
          <el-button type="primary" :loading="saving" @click="submitDoctorUpdate">Save</el-button>
        </template>
      </el-dialog>
    </section>
  </DashboardLayout>
</template>

<style scoped>
.admin-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 14px;
}

.summary-grid span,
.boundary-grid span {
  display: block;
  color: #607086;
  font-size: 13px;
}

.summary-grid strong,
.boundary-grid strong {
  display: block;
  margin-top: 8px;
  color: #172033;
  font-size: 26px;
}

.panel {
  border-radius: 8px;
}

.panel-header,
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.toolbar {
  margin-bottom: 14px;
}

.boundary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}

.boundary-alert {
  margin-top: 8px;
}

.assignment-layout {
  display: grid;
  grid-template-columns: minmax(260px, 340px) 1fr;
  gap: 18px;
}

.assignment-form {
  max-width: 340px;
}

.patient-search {
  min-width: 0;
}

.ok {
  color: #1f8f4d;
}

.bad {
  color: #be3434;
}

@media (max-width: 900px) {
  .summary-grid,
  .boundary-grid,
  .assignment-layout {
    grid-template-columns: 1fr;
  }

  .panel-header,
  .toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .assignment-form {
    max-width: none;
  }
}
</style>
