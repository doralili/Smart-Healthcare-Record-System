<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import {
  listRecordWatermarks,
  type RecordWatermark,
  type RecordWatermarkResponse,
} from "../api/auditor";
import AuditorNav from "../components/AuditorNav.vue";
import DashboardLayout from "../layouts/DashboardLayout.vue";
import { ElMessage } from "../utils/message";

const loading = ref(false);
const watermarkResult = ref<RecordWatermarkResponse | null>(null);
const statusFilter = ref<RecordWatermark["watermark_status"] | "ALL">("ALL");

const filteredRecords = computed(() => {
  const records = watermarkResult.value?.records || [];
  if (statusFilter.value === "ALL") {
    return records;
  }

  return records.filter((record) => record.watermark_status === statusFilter.value);
});

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

function formatPatient(row: RecordWatermark) {
  if (row.patient_name) {
    return `${row.patient_name} (#${row.patient_id})`;
  }

  return `Patient #${row.patient_id}`;
}

function formatSignedDoctor(row: RecordWatermark) {
  const doctorLabel = row.signed_doctor_name || row.signed_doctor_username;
  if (doctorLabel && row.signed_doctor_id !== null) {
    return `${doctorLabel} (#${row.signed_doctor_id})`;
  }

  if (row.signed_doctor_id !== null) {
    return `Doctor #${row.signed_doctor_id}`;
  }

  return "-";
}

function hasTamperSignal(row: RecordWatermark) {
  return (
    row.signed_doctor_id !== null &&
    row.updated_by_doctor_id !== null &&
    row.signed_doctor_id !== row.updated_by_doctor_id
  );
}

function formatTamperDoctor(row: RecordWatermark) {
  if (!hasTamperSignal(row)) {
    return "-";
  }

  const doctorLabel = row.updated_by_doctor_name || row.updated_by_doctor_username;
  if (doctorLabel && row.updated_by_doctor_id !== null) {
    return `${doctorLabel} (#${row.updated_by_doctor_id})`;
  }

  if (row.updated_by_doctor_id !== null) {
    return `Doctor #${row.updated_by_doctor_id}`;
  }

  return "-";
}

function formatTamperTime(row: RecordWatermark) {
  if (!hasTamperSignal(row)) {
    return "-";
  }

  return formatDateTime(row.updated_at);
}

function watermarkTagType(status: RecordWatermark["watermark_status"]) {
  if (status === "VALID") {
    return "success";
  }

  if (status === "INVALID" || status === "DECRYPTION_FAILED") {
    return "danger";
  }

  return "warning";
}

async function loadWatermarks() {
  loading.value = true;
  try {
    watermarkResult.value = await listRecordWatermarks();
  } catch (error) {
    console.error(error);
    ElMessage.error("Failed to load medical record watermarks");
  } finally {
    loading.value = false;
  }
}

onMounted(loadWatermarks);
</script>

<template>
  <DashboardLayout title="Medical Record Watermarks">
    <section v-loading="loading" class="watermark-page">
      <AuditorNav />

      <section class="page-toolbar">
        <el-select
          v-model="statusFilter"
          class="status-filter"
          placeholder="Filter status"
        >
          <el-option label="All Statuses" value="ALL" />
          <el-option label="Valid" value="VALID" />
          <el-option label="Invalid" value="INVALID" />
          <el-option label="Missing" value="MISSING" />
          <el-option label="Decrypt Failed" value="DECRYPTION_FAILED" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="loadWatermarks">
          Refresh
        </el-button>
      </section>

      <section class="watermark-summary">
        <div>
          <span>Total Records</span>
          <strong>{{ watermarkResult?.summary.total_records ?? 0 }}</strong>
        </div>
        <div>
          <span>Valid</span>
          <strong class="ok">{{ watermarkResult?.summary.valid ?? 0 }}</strong>
        </div>
        <div>
          <span>Invalid</span>
          <strong class="bad">{{ watermarkResult?.summary.invalid ?? 0 }}</strong>
        </div>
        <div>
          <span>Missing</span>
          <strong>{{ watermarkResult?.summary.missing ?? 0 }}</strong>
        </div>
        <div>
          <span>Decrypt Failed</span>
          <strong class="bad">{{ watermarkResult?.summary.decryption_failed ?? 0 }}</strong>
        </div>
      </section>

      <el-card class="panel" shadow="never">
        <template #header>
          <span>Watermark Verification Results</span>
        </template>
        <el-table
          :data="filteredRecords"
          border
          stripe
          empty-text="No medical records yet"
        >
          <el-table-column prop="record_id" label="Record" width="90" />
          <el-table-column label="Patient" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              {{ formatPatient(row) }}
            </template>
          </el-table-column>
          <el-table-column label="Signed Doctor" min-width="190" show-overflow-tooltip>
            <template #default="{ row }">
              {{ formatSignedDoctor(row) }}
            </template>
          </el-table-column>
          <el-table-column label="Signed At" min-width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.watermark_issued_at) }}
            </template>
          </el-table-column>
          <el-table-column label="Tamper Suspect" min-width="190" show-overflow-tooltip>
            <template #default="{ row }">
              {{ formatTamperDoctor(row) }}
            </template>
          </el-table-column>
          <el-table-column label="Tamper Time" min-width="170">
            <template #default="{ row }">
              {{ formatTamperTime(row) }}
            </template>
          </el-table-column>
          <el-table-column prop="source" label="Source" width="110" />
          <el-table-column label="Status" width="160">
            <template #default="{ row }">
              <el-tag :type="watermarkTagType(row.watermark_status)" size="small">
                {{ row.watermark_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="watermark_message" label="Verification" min-width="260" show-overflow-tooltip />
        </el-table>
      </el-card>
    </section>
  </DashboardLayout>
</template>

<style scoped>
.watermark-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.status-filter {
  width: 180px;
}

.watermark-summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 12px;
}

.watermark-summary div {
  border: 1px solid #e1e7ef;
  border-radius: 8px;
  padding: 12px 14px;
  background: #ffffff;
}

.watermark-summary span {
  display: block;
  color: #607086;
  font-size: 12px;
}

.watermark-summary strong {
  display: block;
  margin-top: 6px;
  color: #172033;
  font-size: 22px;
}

.ok {
  color: #2e7d32 !important;
}

.bad {
  color: #c62828 !important;
}

.panel {
  border-radius: 8px;
}

@media (max-width: 1000px) {
  .watermark-summary {
    grid-template-columns: repeat(2, minmax(120px, 1fr));
  }
}

@media (max-width: 640px) {
  .page-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .status-filter {
    width: 100%;
  }

  .watermark-summary {
    grid-template-columns: 1fr;
  }
}
</style>
