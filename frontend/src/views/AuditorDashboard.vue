<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import DashboardLayout from "../layouts/DashboardLayout.vue";
import {
  getAuditSummary,
  listAuditLogs,
  verifyAuditHashChain,
  type AuditLog,
  type AuditSummary,
  type VerifyResult,
} from "../api/auditor";

const loading = ref(false);
const verifying = ref(false);
const summary = ref<AuditSummary | null>(null);
const logs = ref<AuditLog[]>([]);
const verifyResult = ref<VerifyResult | null>(null);

const latestLogText = computed(() =>
  summary.value?.latest_log_at ? formatDateTime(summary.value.latest_log_at) : "None",
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

function shortHash(value: string | null) {
  if (!value) {
    return "GENESIS";
  }

  return `${value.slice(0, 10)}...${value.slice(-8)}`;
}

async function loadAuditData() {
  loading.value = true;
  try {
    const [summaryRes, logsRes] = await Promise.all([
      getAuditSummary(),
      listAuditLogs(100),
    ]);
    summary.value = summaryRes;
    logs.value = logsRes.logs;
  } catch (error) {
    console.error(error);
    ElMessage.error("Failed to load audit logs");
  } finally {
    loading.value = false;
  }
}

async function runVerification() {
  verifying.value = true;
  try {
    verifyResult.value = await verifyAuditHashChain();
    if (verifyResult.value.valid) {
      ElMessage.success("Audit hash chain is valid");
    } else {
      ElMessage.error(`Audit hash chain is broken at log #${verifyResult.value.broken_log_id}`);
    }
  } catch (error) {
    console.error(error);
    ElMessage.error("Failed to verify audit hash chain");
  } finally {
    verifying.value = false;
  }
}

onMounted(async () => {
  await loadAuditData();
  await runVerification();
});
</script>

<template>
  <DashboardLayout title="Auditor Dashboard">
    <section v-loading="loading" class="audit-page">
      <section class="summary-grid">
        <el-card shadow="never">
          <span>Total Logs</span>
          <strong>{{ summary?.total_logs ?? 0 }}</strong>
        </el-card>
        <el-card shadow="never">
          <span>Denied Events</span>
          <strong>{{ summary?.denied_logs ?? 0 }}</strong>
        </el-card>
        <el-card shadow="never">
          <span>Latest Event</span>
          <strong class="small-text">{{ latestLogText }}</strong>
        </el-card>
        <el-card shadow="never">
          <span>Hash Chain</span>
          <strong :class="verifyResult?.valid ? 'ok' : 'bad'">
            {{ verifyResult?.valid ? "Valid" : "Needs Check" }}
          </strong>
        </el-card>
      </section>

      <el-card class="panel" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>Integrity Verification</span>
            <div>
              <el-button :loading="loading" @click="loadAuditData">Refresh</el-button>
              <el-button type="primary" :loading="verifying" @click="runVerification">
                Verify Hash Chain
              </el-button>
            </div>
          </div>
        </template>

        <el-alert
          v-if="verifyResult?.valid"
          title="Audit log hash chain is intact."
          type="success"
          show-icon
          :closable="false"
        />
        <el-alert
          v-else-if="verifyResult"
          :title="`Audit chain broken at log #${verifyResult.broken_log_id}: ${verifyResult.reason}`"
          type="error"
          show-icon
          :closable="false"
        />
      </el-card>

      <el-card class="panel" shadow="never">
        <template #header>
          <span>Action Counts</span>
        </template>
        <el-table :data="summary?.action_counts || []" border empty-text="No audit actions yet">
          <el-table-column prop="action" label="Action" min-width="220" />
          <el-table-column prop="count" label="Count" width="120" />
        </el-table>
      </el-card>

      <el-card class="panel" shadow="never">
        <template #header>
          <span>Recent Audit Logs</span>
        </template>
        <el-table :data="logs" border stripe empty-text="No audit logs yet">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="Time" min-width="170">
            <template #default="{ row }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="actor_username" label="Actor" min-width="140" />
          <el-table-column prop="actor_role" label="Role" width="110" />
          <el-table-column prop="action" label="Action" min-width="180" />
          <el-table-column prop="outcome" label="Outcome" width="110">
            <template #default="{ row }">
              <el-tag :type="row.outcome === 'DENIED' ? 'danger' : 'success'" size="small">
                {{ row.outcome }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="patient_id" label="Patient" width="100" />
          <el-table-column prop="doctor_id" label="Doctor" width="100" />
          <el-table-column prop="record_scope" label="Scope" width="100" />
          <el-table-column prop="ip_address" label="IP" min-width="130" />
          <el-table-column prop="user_agent" label="User Agent" min-width="240" show-overflow-tooltip />
          <el-table-column label="Current Hash" min-width="190">
            <template #default="{ row }">
              <code>{{ shortHash(row.current_hash) }}</code>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </DashboardLayout>
</template>

<style scoped>
.audit-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  gap: 14px;
}

.summary-grid span {
  display: block;
  color: #607086;
  font-size: 13px;
}

.summary-grid strong {
  display: block;
  margin-top: 8px;
  color: #172033;
  font-size: 26px;
}

.summary-grid .small-text {
  font-size: 15px;
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

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

code {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
}

@media (max-width: 1000px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(150px, 1fr));
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .panel-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
