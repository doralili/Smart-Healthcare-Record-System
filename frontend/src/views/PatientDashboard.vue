<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import {
  getMyRecordDetail,
  listMyRecords,
  type PatientRecordDetail,
  type PatientRecordSummary,
} from "../api/patientRecords";
import DashboardLayout from "../layouts/DashboardLayout.vue";
import { useAuthStore } from "../stores/auth";
import { ElMessage } from "../utils/message";

// 新增：授权管理相关的 API 和类型
import { 
  getPendingConsents, 
  approveConsent, 
  rejectConsent,
  getMyDoctors,
  revokeConsent,
  getAvailableDoctors,
  selectDefaultDoctor,
  type PendingConsent,
  type AuthorizedDoctor,
  type AvailableDoctor
} from "../api/patientAuth";

interface DiagnosisRow {
  index: number;
  diagnosis: string;
  department: string;
  status: string;
  date: string;
  rawDate: unknown;
  dateValue: number | null;
  dateKey: string;
  encounterId: string | null;
  doctor_name?: string;
  raw: Record<string, unknown>[];
}

interface TimelineRow {
  key: string;
  category: "Lab / Vital" | "Medication" | "Procedure" | "Visit";
  name: string;
  status?: string;
  date: string;
  rawDate: unknown;
  dateKey: string;
  encounterId: string | null;
  value?: string;
  type?: string;
  department?: string;
}

interface ObservationGroupRow {
  key: string;
  period: string;
  level: "Year" | "Month" | "Day";
  sortTime: number | null;
  count: number;
  types: string;
  rows: TimelineRow[];
  children?: ObservationGroupRow[];
}

const auth = useAuthStore();

const loading = ref(false);
const records = ref<PatientRecordSummary[]>([]);
const selectedRecord = ref<PatientRecordDetail | null>(null);
const diagnosisDateQuery = ref("");
const diagnosisDepartmentQuery = ref("");
const unlinkedDepartmentQuery = ref("");
const selectedDiagnosis = ref<DiagnosisRow | null>(null);
const diagnosisDrawerVisible = ref(false);
const selectedUnlinkedClinicalGroup = ref<ObservationGroupRow | null>(null);
const unlinkedClinicalDrawerVisible = ref(false);

// 新增：授权管理相关状态
const activeTab = ref('records')
const pendingConsents = ref<PendingConsent[]>([])
const authorizedDoctors = ref<AuthorizedDoctor[]>([])
const availableDoctors = ref<AvailableDoctor[]>([])
const availableDoctorDepartmentQuery = ref('')
const loadingAuth = ref(false)
const selectingDoctorId = ref<number | null>(null)
let pendingConsentsRefreshTimer: number | undefined;

const record = computed(() => selectedRecord.value?.record);
const patient = computed(() => selectedRecord.value?.patient);

const overviewItems = computed(() => [
  {
    label: "Visits",
    value: record.value?.encounters.length ?? 0,
  },
  {
    label: "Diagnoses",
    value: record.value?.conditions.length ?? 0,
  },
  {
    label: "Lab / Vital Results",
    value: record.value?.observations.length ?? 0,
  },
  {
    label: "Medications",
    value: record.value?.medications.length ?? 0,
  },
  {
    label: "Procedures",
    value: record.value?.procedures.length ?? 0,
  },
]);

const diagnosisRows = computed<DiagnosisRow[]>(() => {
  const grouped = new Map<string, DiagnosisRow>();

  (record.value?.conditions ?? []).forEach((item: unknown, index) => {
    const condition = asRecord(item);
    const rawDate = condition.recorded_date;
    const encounterId = getEncounterId(condition);
    const dateKey = formatDateKey(rawDate);
    const groupKey = encounterId ? `encounter:${encounterId}` : `date:${dateKey || index}`;
    const diagnosis = cleanMedicalText(condition.code);
    const department = formatDepartment(condition.department);
    const status = formatStatus(condition.clinical_status);

    const existing = grouped.get(groupKey);

    if (existing) {
      existing.raw.push(condition);
      existing.diagnosis = joinUniqueText(existing.diagnosis, diagnosis);
      existing.department = joinUniqueText(existing.department, department);
      existing.status = joinUniqueText(existing.status, status);
      return;
    }

    grouped.set(groupKey, {
      index,
      diagnosis,
      department,
      status,
      date: formatDateTime(rawDate),
      rawDate,
      dateValue: toTime(rawDate),
      dateKey,
      encounterId,
      doctor_name: condition.doctor_name,
      raw: [condition],
    });
  });

  return Array.from(grouped.values());
});

const filteredDiagnosisRows = computed(() => {
  const query = normalizeSearchText(diagnosisDateQuery.value);
  const departmentQuery = normalizeSearchText(diagnosisDepartmentQuery.value);

  if (!query && !departmentQuery) {
    return diagnosisRows.value;
  }

  return diagnosisRows.value.filter((item) => {
    const searchable = normalizeSearchText(
      [
        item.diagnosis,
        item.department,
        item.status,
        item.date,
        item.rawDate,
        formatDateOnly(item.rawDate),
      ].join(" "),
    );

    const department = normalizeSearchText(item.department);
    const matchesKeyword = !query || searchable.includes(query);
    const matchesDepartment = !departmentQuery || department.includes(departmentQuery);

    return matchesKeyword && matchesDepartment;
  });
});

const relatedEncounters = computed(() =>
  buildRelatedRows("encounters", selectedDiagnosis.value),
);

const relatedMedications = computed(() =>
  buildRelatedRows("medications", selectedDiagnosis.value),
);

const relatedObservations = computed(() =>
  buildRelatedRows("observations", selectedDiagnosis.value),
);

const relatedProcedures = computed(() =>
  buildRelatedRows("procedures", selectedDiagnosis.value),
);

const selectedUnlinkedLabRows = computed(() =>
  selectedUnlinkedClinicalGroup.value?.rows.filter((row) => row.category === "Lab / Vital") ?? [],
);

const selectedUnlinkedMedicationRows = computed(() =>
  selectedUnlinkedClinicalGroup.value?.rows.filter((row) => row.category === "Medication") ?? [],
);

const selectedUnlinkedProcedureRows = computed(() =>
  selectedUnlinkedClinicalGroup.value?.rows.filter((row) => row.category === "Procedure") ?? [],
);

const filteredAvailableDoctors = computed(() => {
  const query = availableDoctorDepartmentQuery.value.trim().toLowerCase();
  if (!query) {
    return availableDoctors.value;
  }

  return availableDoctors.value.filter((doctor) =>
    (doctor.department || '').toLowerCase().includes(query),
  );
});

function canSelectDefaultDoctor(doctor: AvailableDoctor) {
  if (doctor.can_select_default === false) {
    return false;
  }

  return !(doctor.access_status === 'ACTIVE' && ['DEFAULT', 'EXTRA'].includes(doctor.access_scope || ''));
}

function doctorAccessTagType(doctor: AvailableDoctor) {
  if (doctor.access_status === 'ACTIVE') {
    return doctor.access_scope === 'EXTRA' ? 'success' : 'primary';
  }

  return doctor.access_status === 'NONE' ? 'info' : 'warning';
}

function doctorAccessLabel(doctor: AvailableDoctor) {
  if (doctor.access_status === 'ACTIVE' && doctor.access_scope === 'EXTRA') {
    return 'Full Access';
  }

  if (doctor.access_status === 'ACTIVE' && doctor.access_scope === 'DEFAULT') {
    return 'Default Access';
  }

  return doctor.access_status || 'NONE';
}

const unlinkedClinicalRows = computed(() => {
  if (!record.value) {
    return [];
  }

  const observations = (record.value.observations ?? []).map((item: unknown) =>
    buildClinicalRow("observations", asRecord(item)),
  );
  const medications = (record.value.medications ?? []).map((item: unknown) =>
    buildClinicalRow("medications", asRecord(item)),
  );
  const procedures = (record.value.procedures ?? []).map((item: unknown) =>
    buildClinicalRow("procedures", asRecord(item)),
  );

  return dedupeRelatedRows([...observations, ...medications, ...procedures])
    .filter((item) => !isLinkedToAnyDiagnosis(item))
    .sort(compareTimelineRows);
});

const unlinkedClinicalGroups = computed<ObservationGroupRow[]>(() => {
  const yearGroups = new Map<string, Map<string, Map<string, TimelineRow[]>>>();
  const undatedRows: TimelineRow[] = [];

  unlinkedClinicalRows.value.forEach((item) => {
    if (!item.dateKey) {
      undatedRows.push(item);
      return;
    }

    const year = item.dateKey.slice(0, 4);
    const month = item.dateKey.slice(0, 7);
    const day = item.dateKey;

    const months = yearGroups.get(year) ?? new Map<string, Map<string, TimelineRow[]>>();
    const days = months.get(month) ?? new Map<string, TimelineRow[]>();
    const rows = days.get(day) ?? [];

    rows.push(item);
    days.set(day, rows);
    months.set(month, days);
    yearGroups.set(year, months);
  });

  const groups = Array.from(yearGroups.entries())
    .map(([year, months]) => {
      const monthChildren = Array.from(months.entries())
        .map(([month, days]) => {
          const dayChildren = Array.from(days.entries())
            .map(([day, rows]) =>
              buildClinicalGroup({
                key: `day:${day}`,
                period: formatDateOnly(day),
                level: "Day",
                rows,
              }),
            )
            .sort(compareObservationGroups);

          return buildClinicalGroup({
            key: `month:${month}`,
            period: formatMonthLabel(month),
            level: "Month",
            rows: flattenClinicalRows(dayChildren),
            children: dayChildren,
          });
        })
        .sort(compareObservationGroups);

      return buildClinicalGroup({
        key: `year:${year}`,
        period: year,
        level: "Year",
        rows: flattenClinicalRows(monthChildren),
        children: monthChildren,
      });
    })
    .sort(compareObservationGroups);

  if (undatedRows.length) {
    groups.push(
      buildClinicalGroup({
        key: "not-recorded",
        period: "Date not recorded",
        level: "Day",
        rows: undatedRows,
      }),
    );
  }

  return groups;
});

const filteredUnlinkedClinicalGroups = computed<ObservationGroupRow[]>(() => {
  const departmentQuery = normalizeSearchText(unlinkedDepartmentQuery.value);

  if (!departmentQuery) {
    return unlinkedClinicalGroups.value;
  }

  return unlinkedClinicalGroups.value
    .map((group) => filterClinicalGroupByDepartment(group, departmentQuery))
    .filter((group): group is ObservationGroupRow => Boolean(group));
});

watch(filteredDiagnosisRows, (rows) => {
  if (!selectedDiagnosis.value) {
    return;
  }

  const stillVisible = rows.some((row) => row.index === selectedDiagnosis.value?.index);
  if (!stillVisible) {
    diagnosisDrawerVisible.value = false;
    selectedDiagnosis.value = null;
  }
});

watch(filteredUnlinkedClinicalGroups, (groups) => {
  if (!selectedUnlinkedClinicalGroup.value) {
    return;
  }

  const nextGroup = findClinicalGroupByKey(groups, selectedUnlinkedClinicalGroup.value.key);
  if (!nextGroup) {
    unlinkedClinicalDrawerVisible.value = false;
    selectedUnlinkedClinicalGroup.value = null;
    return;
  }

  selectedUnlinkedClinicalGroup.value = nextGroup;
});

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object") {
    return value as Record<string, unknown>;
  }

  return {};
}

function cleanMedicalText(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "Not recorded";
  }

  return String(value)
    .replace(/\s*\((finding|disorder|procedure|observable entity|regime\/therapy)\)\s*$/i, "")
    .trim();
}

function formatStatus(value: unknown) {
  if (!value) {
    return "Not recorded";
  }

  return String(value)
    .replace(/-/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "Not recorded";
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  return String(value);
}

function formatDepartment(value: unknown) {
  if (!value) {
    return "Not classified";
  }

  return String(value);
}

function formatDateOnly(value: unknown) {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(String(value));

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function formatDateTime(value: unknown) {
  if (!value) {
    return "Not recorded";
  }

  const date = new Date(String(value));

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function normalizeSearchText(value: unknown) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[./]/g, "-")
    .replace(/\s+/g, "");
}

function toTime(value: unknown) {
  if (!value) {
    return null;
  }

  const time = new Date(String(value)).getTime();
  return Number.isNaN(time) ? null : time;
}

function formatDateKey(value: unknown) {
  if (!value) {
    return "";
  }

  const text = String(value);

  if (/^\d{4}-\d{2}-\d{2}/.test(text)) {
    return text.slice(0, 10);
  }

  const date = new Date(String(value));

  if (Number.isNaN(date.getTime())) {
    return text.slice(0, 10);
  }

  return date.toISOString().slice(0, 10);
}

function getEncounterId(source: Record<string, unknown>) {
  const directValue = source.encounter_id;

  if (directValue) {
    return String(directValue);
  }

  const encounter = source.encounter;

  if (encounter && typeof encounter === "object") {
    const reference = (encounter as Record<string, unknown>).reference;
    if (reference) {
      return String(reference).split("/").pop() || null;
    }
  }

  return null;
}

function joinUniqueText(current: string, next: string) {
  const values = current
    .split("; ")
    .map((item) => item.trim())
    .filter(Boolean);

  if (!values.includes(next)) {
    values.push(next);
  }

  return values.join("; ");
}

function isRelatedToDiagnosis(item: TimelineRow, diagnosis: DiagnosisRow | null) {
  if (!diagnosis) {
    return false;
  }

  if (diagnosis.encounterId && item.encounterId) {
    return diagnosis.encounterId === item.encounterId;
  }

  return Boolean(diagnosis.dateKey && item.dateKey && diagnosis.dateKey === item.dateKey);
}

function isLinkedToAnyDiagnosis(item: TimelineRow) {
  return diagnosisRows.value.some((diagnosis) => isRelatedToDiagnosis(item, diagnosis));
}

function compareTimelineRows(first: TimelineRow, second: TimelineRow) {
  const firstTime = toTime(first.rawDate);
  const secondTime = toTime(second.rawDate);

  if (firstTime === null && secondTime === null) {
    return first.name.localeCompare(second.name);
  }

  if (firstTime === null) {
    return 1;
  }

  if (secondTime === null) {
    return -1;
  }

  return firstTime - secondTime;
}

function compareObservationGroups(first: ObservationGroupRow, second: ObservationGroupRow) {
  if (first.sortTime === null && second.sortTime === null) {
    return first.period.localeCompare(second.period);
  }

  if (first.sortTime === null) {
    return 1;
  }

  if (second.sortTime === null) {
    return -1;
  }

  return first.sortTime - second.sortTime;
}

function buildClinicalGroup({
  key,
  period,
  level,
  rows,
  children,
}: {
  key: string;
  period: string;
  level: ObservationGroupRow["level"];
  rows: TimelineRow[];
  children?: ObservationGroupRow[];
}): ObservationGroupRow {
  const sortedRows = [...rows].sort(compareTimelineRows);
  const firstDatedRow = sortedRows.find((row) => toTime(row.rawDate) !== null);

  return {
    key,
    period,
    level,
    sortTime: firstDatedRow ? toTime(firstDatedRow.rawDate) : null,
    count: sortedRows.length,
    types: getClinicalTypes(sortedRows),
    rows: sortedRows,
    children,
  };
}

function flattenClinicalRows(groups: ObservationGroupRow[]) {
  return groups.flatMap((group) => group.rows);
}

function filterClinicalGroupByDepartment(
  group: ObservationGroupRow,
  departmentQuery: string,
): ObservationGroupRow | null {
  const children = group.children
    ?.map((child) => filterClinicalGroupByDepartment(child, departmentQuery))
    .filter((child): child is ObservationGroupRow => Boolean(child));
  const childRows = children ? flattenClinicalRows(children) : [];
  const ownRows = group.rows.filter((row) =>
    normalizeSearchText(row.department).includes(departmentQuery),
  );
  const rows = dedupeRelatedRows([...childRows, ...ownRows]).sort(compareTimelineRows);

  if (!rows.length) {
    return null;
  }

  return buildClinicalGroup({
    key: group.key,
    period: group.period,
    level: group.level,
    rows,
    children,
  });
}

function findClinicalGroupByKey(groups: ObservationGroupRow[], key: string): ObservationGroupRow | null {
  for (const group of groups) {
    if (group.key === key) {
      return group;
    }

    const childMatch = group.children ? findClinicalGroupByKey(group.children, key) : null;
    if (childMatch) {
      return childMatch;
    }
  }

  return null;
}

function getClinicalTypes(rows: TimelineRow[]) {
  return Array.from(new Set(rows.map((row) => row.category))).join(", ");
}

function formatMonthLabel(value: string) {
  const [year, month] = value.split("-");
  return `${year}/${month}`;
}

function buildClinicalRow(
  category: "medications" | "observations" | "procedures",
  source: Record<string, unknown>,
): TimelineRow {
  if (category === "medications") {
    const name = cleanMedicalText(source.medication);
    const department = formatDepartment(source.department);
    const status = formatStatus(source.status);
    const date = formatDateTime(source.authored_on);

    return {
      key: buildRelatedRowKey(category, source, [name, status, date]),
      category: "Medication",
      name,
      department,
      status,
      date,
      rawDate: source.authored_on,
      dateKey: formatDateKey(source.authored_on),
      encounterId: getEncounterId(source),
    };
  }

  if (category === "observations") {
    const name = cleanMedicalText(source.code);
    const value = formatValue(source.value);
    const department = formatDepartment(source.department);
    const status = formatStatus(source.status);
    const date = formatDateTime(source.effective_datetime);

    return {
      key: buildRelatedRowKey(category, source, [name, value, status, date]),
      category: "Lab / Vital",
      name,
      value,
      department,
      status,
      date,
      rawDate: source.effective_datetime,
      dateKey: formatDateKey(source.effective_datetime),
      encounterId: getEncounterId(source),
    };
  }

  const name = cleanMedicalText(source.code);
  const department = formatDepartment(source.department);
  const status = formatStatus(source.status);
  const date = formatDateTime(source.performed_datetime);

  return {
    key: buildRelatedRowKey(category, source, [name, status, date]),
    category: "Procedure",
    name,
    department,
    status,
    date,
    rawDate: source.performed_datetime,
    dateKey: formatDateKey(source.performed_datetime),
    encounterId: getEncounterId(source),
  };
}

function buildRelatedRows(
  category: "encounters" | "medications" | "observations" | "procedures",
  diagnosis: DiagnosisRow | null,
) {
  if (!diagnosis || !record.value) {
    return [];
  }

  const rows = (record.value[category] ?? [])
    .map((item: unknown): TimelineRow => {
      const source = asRecord(item);

      if (category === "encounters") {
        const name = cleanMedicalText(source.type);
        const status = formatStatus(source.status);
        const date = formatDateTime(source.start);
        const type = cleanMedicalText(source.class);

        return {
          key: buildRelatedRowKey(category, source, [name, status, date, type]),
          category: "Visit",
          name,
          status,
          date,
          rawDate: source.start,
          dateKey: formatDateKey(source.start),
          encounterId: getEncounterId(source),
          type,
        };
      }

      if (category === "medications") {
        const name = cleanMedicalText(source.medication);
        const department = formatDepartment(source.department);
        const status = formatStatus(source.status);
        const date = formatDateTime(source.authored_on);

        return {
          key: buildRelatedRowKey(category, source, [name, status, date]),
          category: "Medication",
          name,
          department,
          status,
          date,
          rawDate: source.authored_on,
          dateKey: formatDateKey(source.authored_on),
          encounterId: getEncounterId(source),
        };
      }

      if (category === "observations") {
        const name = cleanMedicalText(source.code);
        const value = formatValue(source.value);
        const department = formatDepartment(source.department);
        const status = formatStatus(source.status);
        const date = formatDateTime(source.effective_datetime);

        return {
          key: buildRelatedRowKey(category, source, [name, value, status, date]),
          category: "Lab / Vital",
          name,
          value,
          department,
          status,
          date,
          rawDate: source.effective_datetime,
          dateKey: formatDateKey(source.effective_datetime),
          encounterId: getEncounterId(source),
        };
      }

      const name = cleanMedicalText(source.code);
      const department = formatDepartment(source.department);
      const status = formatStatus(source.status);
      const date = formatDateTime(source.performed_datetime);

      return {
        key: buildRelatedRowKey(category, source, [name, status, date]),
        category: "Procedure",
        name,
        department,
        status,
        date,
        rawDate: source.performed_datetime,
        dateKey: formatDateKey(source.performed_datetime),
        encounterId: getEncounterId(source),
      };
    })
    .filter((item) => isRelatedToDiagnosis(item, diagnosis));

  return dedupeRelatedRows(rows);
}

function buildRelatedRowKey(
  category: string,
  source: Record<string, unknown>,
  fallbackParts: unknown[],
) {
  if (source.id) {
    return `${category}:${String(source.id)}`;
  }

  return `${category}:${fallbackParts.map((part) => String(part ?? "")).join("|")}`;
}

function dedupeRelatedRows(rows: TimelineRow[]) {
  const seen = new Set<string>();

  return rows.filter((row) => {
    if (seen.has(row.key)) {
      return false;
    }

    seen.add(row.key);
    return true;
  });
}

function openDiagnosis(row: DiagnosisRow) {
  selectedDiagnosis.value = row;
  diagnosisDrawerVisible.value = true;
}

function openUnlinkedClinicalGroup(row: ObservationGroupRow) {
  selectedUnlinkedClinicalGroup.value = row;
  unlinkedClinicalDrawerVisible.value = true;
}

async function loadRecords() {
  if (!auth.token) {
    ElMessage.error("Please sign in again.");
    return;
  }

  loading.value = true;

  try {
    const res = await listMyRecords(auth.token);
    records.value = res.data;

    if (!records.value.length) {
      selectedRecord.value = null;
      return;
    }

    const firstRecord = records.value[0];
    const detailRes = await getMyRecordDetail(auth.token, firstRecord.id);
    selectedRecord.value = detailRes.data;
  } catch {
    ElMessage.error("Failed to load your medical record.");
  } finally {
    loading.value = false;
  }
}

// 新增：加载待审批申请
async function loadPendingConsents(silent = false) {
  if (!auth.token) return;
  if (!silent) {
    loadingAuth.value = true;
  }
  try {
    const res = await getPendingConsents(auth.token);
    // 修复：res 已经是 response.data，直接取 pending_consents
    pendingConsents.value = res.pending_consents || [];
    console.log('Pending consents loaded:', pendingConsents.value);
  } catch (err) {
    console.error('Failed to load pending requests:', err);
    if (!silent) {
      ElMessage.error("Failed to load pending requests");
    }
  } finally {
    if (!silent) {
      loadingAuth.value = false;
    }
  }
}

// 新增：加载已授权医生
async function loadMyDoctors() {
  if (!auth.token) return;
  loadingAuth.value = true;
  try {
    const res = await getMyDoctors(auth.token);
    // 修复：res 已经是 response.data，直接取 doctors
    authorizedDoctors.value = res.doctors || [];
    console.log('Authorized doctors loaded:', authorizedDoctors.value);
  } catch (err) {
    console.error('Failed to load authorized doctors:', err);
    ElMessage.error("Failed to load authorized doctors");
  } finally {
    loadingAuth.value = false;
  }
}

// 鏂板锛氬姞杞藉彲閫夊尰鐢?
async function loadAvailableDoctors(silent = false) {
  if (!auth.token) return;
  if (!silent) {
    loadingAuth.value = true;
  }
  try {
    const res = await getAvailableDoctors(auth.token, availableDoctorDepartmentQuery.value);
    availableDoctors.value = res.doctors || [];
  } catch (err) {
    console.error('Failed to load available doctors:', err);
    if (!silent) {
      ElMessage.error("Failed to load available doctors");
    }
  } finally {
    if (!silent) {
      loadingAuth.value = false;
    }
  }
}

// 新增：批准申请
async function handleApprove(consentId: number) {
  try {
    await approveConsent(auth.token, consentId);
    ElMessage.success("Access granted to doctor");
    await loadPendingConsents();
    await loadMyDoctors();
    await loadAvailableDoctors(true);
  } catch (err) {
    console.error('Failed to approve request:', err);
    ElMessage.error("Failed to approve request");
  }
}

// 新增：拒绝申请
async function handleReject(consentId: number) {
  try {
    await rejectConsent(auth.token, consentId);
    ElMessage.success("Request rejected");
    await loadPendingConsents();
  } catch (err) {
    console.error('Failed to reject request:', err);
    ElMessage.error("Failed to reject request");
  }
}

// 新增：撤销授权
async function handleRevoke(consentId: number, doctorName: string) {
  try {
    await revokeConsent(auth.token, consentId);
    ElMessage.success(`Revoked access for Dr. ${doctorName}`);
    await loadMyDoctors();
    await loadPendingConsents();
    await loadAvailableDoctors(true);
  } catch (err) {
    console.error('Failed to revoke access:', err);
    ElMessage.error("Failed to revoke access");
  }
}

// 鏂板锛氭偅鑰呴€夋嫨榛樿鍖荤敓
async function handleSelectDoctor(doctor: AvailableDoctor) {
  if (!auth.token) return;
  if (!canSelectDefaultDoctor(doctor)) {
    ElMessage.warning("This doctor already has active access");
    return;
  }

  selectingDoctorId.value = doctor.doctor_user_id;
  try {
    await selectDefaultDoctor(auth.token, doctor.doctor_user_id);
    ElMessage.success(`Default access granted to ${doctor.name || doctor.username}`);
    await Promise.all([
      loadAvailableDoctors(true),
      loadMyDoctors(),
      loadPendingConsents(true),
    ]);
  } catch (err: any) {
    console.error('Failed to select doctor:', err);
    ElMessage.error(err?.response?.data?.detail || "Failed to select doctor");
  } finally {
    selectingDoctorId.value = null;
  }
}

// 新增：切换 Tab 时加载数据
async function onTabChange(tab: any) {
  if (tab === 'auth') {
    await Promise.all([loadPendingConsents(), loadMyDoctors(), loadAvailableDoctors()]);
  }
}

async function handleDepartmentSearch() {
  await loadAvailableDoctors();
}

async function handleClearDepartmentSearch() {
  availableDoctorDepartmentQuery.value = '';
  await loadAvailableDoctors();
}

async function handleTabClick(tab: any) {
  await onTabChange(tab.paneName);
}

onMounted(() => {
  loadRecords();
  loadPendingConsents();
  loadMyDoctors();
  loadAvailableDoctors(true);
  pendingConsentsRefreshTimer = window.setInterval(() => {
    loadPendingConsents(true);
  }, 10000);
});

onUnmounted(() => {
  if (pendingConsentsRefreshTimer !== undefined) {
    window.clearInterval(pendingConsentsRefreshTimer);
  }
});
</script>

<template>
  <DashboardLayout title="Patient Dashboard">
    <el-tabs v-model="activeTab" @tab-click="handleTabClick">
      <!-- 我的病历 Tab -->
      <el-tab-pane label="My Records" name="records">
        <section v-loading="loading" class="record-page">
          <el-empty
            v-if="!loading && !selectedRecord"
            description="No medical record found."
          />

          <template v-if="selectedRecord">
            <section class="overview-panel">
              <div>
                <p class="eyebrow">Complete Medical Record</p>
                <h2>My Health Record</h2>
                <p class="muted">
                  This record is decrypted securely after you sign in.
                </p>
              </div>

              <el-button :loading="loading" @click="loadRecords">
                Refresh
              </el-button>
            </section>

            <el-card class="info-card" shadow="never">
              <template #header>
                <span>Patient Information</span>
              </template>

              <el-descriptions :column="2" border>
                <el-descriptions-item label="Name">
                  {{ patient?.full_name || "Not recorded" }}
                </el-descriptions-item>
                <el-descriptions-item label="Gender">
                  {{ formatStatus(patient?.gender) }}
                </el-descriptions-item>
                <el-descriptions-item label="Birth Date">
                  {{ formatDateOnly(patient?.birth_date) }}
                </el-descriptions-item>
                <el-descriptions-item label="Phone">
                  {{ patient?.phone || "Not recorded" }}
                </el-descriptions-item>
                <el-descriptions-item label="Address" :span="2">
                  {{ patient?.address || "Not recorded" }}
                </el-descriptions-item>
              </el-descriptions>
            </el-card>

            <section class="stats-grid">
              <div
                v-for="item in overviewItems"
                :key="item.label"
                class="stat-card"
              >
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </section>

            <el-card class="info-card" shadow="never">
              <template #header>
                <span>Record Information</span>
              </template>

              <el-descriptions :column="2" border>
                <el-descriptions-item label="Record ID">
                  {{ selectedRecord.id }}
                </el-descriptions-item>
                <el-descriptions-item label="Created At">
                  {{ formatDateTime(selectedRecord.created_at) }}
                </el-descriptions-item>
              </el-descriptions>
            </el-card>

            <el-card class="section-card" shadow="never">
              <template #header>
                <div class="section-header">
                  <span>Diagnoses</span>
                  <div class="record-filters">
                    <el-input
                      v-model="diagnosisDateQuery"
                      clearable
                      class="record-filter"
                      placeholder="Search by date, e.g. 2024, 2024-05, 2024-05-20"
                    />
                    <el-input
                      v-model="diagnosisDepartmentQuery"
                      clearable
                      class="department-filter"
                      placeholder="Search by department"
                    />
                  </div>
                </div>
              </template>

              <el-table
                :data="filteredDiagnosisRows"
                border
                empty-text="No diagnoses match these filters."
              >
                <el-table-column prop="department" label="Department" min-width="170" />
                <el-table-column prop="diagnosis" label="Diagnosis" min-width="260" />
                <el-table-column prop="status" label="Status" width="160" />
                <el-table-column prop="date" label="Date" width="190" />
                <el-table-column label="Details" width="120">
                  <template #default="{ row }">
                    <el-button type="primary" link @click="openDiagnosis(row)">
                      View
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>

            <el-card class="section-card" shadow="never">
              <template #header>
                <div class="section-header">
                  <span>Unlinked Clinical Records</span>
                  <el-input
                    v-model="unlinkedDepartmentQuery"
                    clearable
                    class="department-filter"
                    placeholder="Search by department"
                  />
                </div>
              </template>

              <el-table
                :data="filteredUnlinkedClinicalGroups"
                border
                row-key="key"
                empty-text="No unlinked clinical records match these filters."
              >
                <el-table-column prop="period" label="Period" min-width="220" />
                <el-table-column prop="level" label="Level" min-width="120" />
                <el-table-column prop="types" label="Types" min-width="260" />
                <el-table-column prop="count" label="Records" min-width="140" />
                <el-table-column label="Details" min-width="180">
                  <template #default="{ row }">
                    <el-button type="primary" link @click="openUnlinkedClinicalGroup(row)">
                      View Records
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>

            <el-drawer
              v-model="diagnosisDrawerVisible"
              size="58%"
              :title="selectedDiagnosis?.diagnosis || 'Diagnosis Details'"
            >
              <template v-if="selectedDiagnosis">
                <section class="drawer-section">
                  <h3>Diagnosis Information</h3>
                  <el-descriptions :column="2" border>
                    <el-descriptions-item label="Diagnosis">
                      {{ selectedDiagnosis.diagnosis }}
                    </el-descriptions-item>
                    <el-descriptions-item label="Department">
                      {{ selectedDiagnosis.department }}
                    </el-descriptions-item>
                    <el-descriptions-item label="Status">
                      {{ selectedDiagnosis.status }}
                    </el-descriptions-item>
                    <el-descriptions-item label="Recorded At">
                      {{ selectedDiagnosis.date }}
                    </el-descriptions-item>
                    <el-descriptions-item label="Doctor">
                       {{ selectedDiagnosis.doctor_name || 'Not recorded in current imported record' }}
                    </el-descriptions-item>
                  </el-descriptions>
                </section>

                <section class="drawer-section">
                  <h3>Related Visits</h3>
                  <el-table
                    :data="relatedEncounters"
                    border
                    empty-text="No visit found near this diagnosis date."
                  >
                    <el-table-column prop="name" label="Visit Type" min-width="220" />
                    <el-table-column prop="type" label="Class" width="130" />
                    <el-table-column prop="status" label="Status" width="140" />
                    <el-table-column prop="date" label="Date" width="190" />
                  </el-table>
                </section>

                <section class="drawer-section">
                  <h3>Related Medications</h3>
                  <el-table
                    :data="relatedMedications"
                    border
                    empty-text="No medication found near this diagnosis date."
                  >
                    <el-table-column prop="department" label="Department" width="170" />
                    <el-table-column prop="name" label="Medication" min-width="280" />
                    <el-table-column prop="status" label="Status" width="140" />
                    <el-table-column prop="date" label="Prescribed At" width="190" />
                  </el-table>
                </section>

                <section class="drawer-section">
                  <h3>Related Lab / Vital Results</h3>
                  <el-table
                    :data="relatedObservations"
                    border
                    empty-text="No lab or vital result found near this diagnosis date."
                  >
                    <el-table-column prop="department" label="Department" width="170" />
                    <el-table-column prop="name" label="Item" min-width="240" />
                    <el-table-column prop="value" label="Result" min-width="180" />
                    <el-table-column prop="status" label="Status" width="140" />
                    <el-table-column prop="date" label="Date" width="190" />
                  </el-table>
                </section>

                <section class="drawer-section">
                  <h3>Related Procedures</h3>
                  <el-table
                    :data="relatedProcedures"
                    border
                    empty-text="No procedure found near this diagnosis date."
                  >
                    <el-table-column prop="department" label="Department" width="170" />
                    <el-table-column prop="name" label="Procedure" min-width="280" />
                    <el-table-column prop="status" label="Status" width="140" />
                    <el-table-column prop="date" label="Date" width="190" />
                  </el-table>
                </section>
              </template>
            </el-drawer>

            <el-drawer
              v-model="unlinkedClinicalDrawerVisible"
              size="52%"
              :title="`Unlinked Clinical Records - ${selectedUnlinkedClinicalGroup?.period || ''}`"
            >
              <template v-if="selectedUnlinkedClinicalGroup">
                <section class="drawer-section">
                  <h3>Lab / Vital Results</h3>
                  <el-table
                    :data="selectedUnlinkedLabRows"
                    border
                    empty-text="No unlinked lab or vital results in this period."
                  >
                    <el-table-column prop="department" label="Department" width="170" />
                    <el-table-column prop="name" label="Item" min-width="260" />
                    <el-table-column prop="value" label="Result" min-width="180" />
                    <el-table-column prop="status" label="Status" width="140" />
                    <el-table-column prop="date" label="Date" width="190" />
                  </el-table>
                </section>

                <section class="drawer-section">
                  <h3>Medications</h3>
                  <el-table
                    :data="selectedUnlinkedMedicationRows"
                    border
                    empty-text="No unlinked medications in this period."
                  >
                    <el-table-column prop="department" label="Department" width="170" />
                    <el-table-column prop="name" label="Medication" min-width="280" />
                    <el-table-column prop="status" label="Status" width="140" />
                    <el-table-column prop="date" label="Prescribed At" width="190" />
                  </el-table>
                </section>

                <section class="drawer-section">
                  <h3>Procedures</h3>
                  <el-table
                    :data="selectedUnlinkedProcedureRows"
                    border
                    empty-text="No unlinked procedures in this period."
                  >
                    <el-table-column prop="department" label="Department" width="170" />
                    <el-table-column prop="name" label="Procedure" min-width="280" />
                    <el-table-column prop="status" label="Status" width="140" />
                    <el-table-column prop="date" label="Date" width="190" />
                  </el-table>
                </section>
              </template>
            </el-drawer>
          </template>
        </section>
      </el-tab-pane>

      <!-- 医生授权管理 Tab -->
      <el-tab-pane name="auth">
        <template #label>
          <el-badge
            :hidden="pendingConsents.length === 0"
            is-dot
            class="auth-tab-badge"
          >
            <span>Doctor Authorization</span>
          </el-badge>
        </template>
        <section v-loading="loadingAuth" class="auth-page">
          <el-card class="auth-card" shadow="never">
            <template #header>
              <div class="section-header auth-section-header">
                <span>Choose Default Doctor</span>
                <div class="doctor-search-bar">
                  <el-input
                    v-model="availableDoctorDepartmentQuery"
                    clearable
                    placeholder="Search by department"
                    class="doctor-search-input"
                    @keyup.enter="handleDepartmentSearch"
                    @clear="handleClearDepartmentSearch"
                  />
                  <el-button type="primary" @click="handleDepartmentSearch">
                    Search
                  </el-button>
                </div>
              </div>
            </template>

            <el-table :data="filteredAvailableDoctors" border empty-text="No approved doctors available">
              <el-table-column prop="name" label="Doctor" min-width="180">
                <template #default="{ row }">
                  {{ row.name || row.username }}
                </template>
              </el-table-column>
              <el-table-column prop="department" label="Department" min-width="170">
                <template #default="{ row }">
                  <span>{{ row.department || "Not recorded" }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="license_no" label="License" width="150">
                <template #default="{ row }">
                  {{ row.license_no || "Not recorded" }}
                </template>
              </el-table-column>
              <el-table-column label="Current Access" width="150">
                <template #default="{ row }">
                  <el-tag
                    :type="doctorAccessTagType(row)"
                    size="small"
                  >
                    {{ doctorAccessLabel(row) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="Expires At" width="180">
                <template #default="{ row }">
                  {{ row.access_end_time ? formatDateTime(row.access_end_time) : "Not selected" }}
                </template>
              </el-table-column>
              <el-table-column label="Action" width="150">
                <template #default="{ row }">
                  <el-button
                    type="primary"
                    size="small"
                    :disabled="!canSelectDefaultDoctor(row)"
                    :loading="selectingDoctorId === row.doctor_user_id"
                    @click="handleSelectDoctor(row)"
                  >
                    Choose
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- 待审批申请 -->
          <el-card class="auth-card" shadow="never">
            <template #header>
              <span>Pending Requests ({{ pendingConsents.length }})</span>
            </template>

            <el-table :data="pendingConsents" border empty-text="No pending requests">
              <el-table-column prop="doctor_name" label="Doctor" width="180" />
              <el-table-column label="Request Type" width="140">
                <template #default="{ row }">
                  <el-tag :type="row.record_scope === 'EXTRA' ? 'success' : 'info'" size="small">
                    {{ row.record_scope === 'EXTRA' ? 'Full Access' : 'Default Access' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="request_reason" label="Reason" min-width="200" />
              <el-table-column prop="created_at" label="Requested At" width="180">
                <template #default="{ row }">
                  {{ formatDateTime(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column label="Action" width="180">
                <template #default="{ row }">
                  <el-button type="success" size="small" @click="handleApprove(row.consent_id)">
                    Approve
                  </el-button>
                  <el-button type="danger" size="small" @click="handleReject(row.consent_id)">
                    Reject
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- 已授权医生 -->
          <el-card class="auth-card" shadow="never">
            <template #header>
              <span>Authorized Doctors ({{ authorizedDoctors.length }})</span>
            </template>

            <el-table :data="authorizedDoctors" border empty-text="No authorized doctors">
              <el-table-column prop="doctor_name" label="Doctor" width="180" />
              <el-table-column label="Access Level" width="140">
                <template #default="{ row }">
                  <el-tag :type="row.record_scope === 'EXTRA' ? 'success' : 'info'" size="small">
                    {{ row.record_scope === 'EXTRA' ? 'Full Access' : 'Default Access' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="granted_at" label="Granted At" width="180">
                <template #default="{ row }">
                  {{ formatDateTime(row.granted_at) }}
                </template>
              </el-table-column>
              <el-table-column label="Action" width="120">
                <template #default="{ row }">
                  <el-button type="danger" size="small" @click="handleRevoke(row.consent_id, row.doctor_name)">
                    Revoke
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </section>
      </el-tab-pane>
    </el-tabs>
  </DashboardLayout>
</template>

<style scoped>
.record-page {
  margin-top: 20px;
}

.auth-page {
  margin-top: 20px;
}

.auth-card {
  margin-bottom: 24px;
  border-radius: 8px;
}

.auth-tab-badge {
  line-height: 1;
}

.auth-section-header {
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.doctor-search-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.doctor-search-input {
  width: 280px;
}

.match-tag {
  margin-left: 8px;
}

:deep(.auth-tab-badge .el-badge__content.is-dot) {
  right: -4px;
  top: 2px;
}

.overview-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 24px;
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #2f80ed;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
}

h2 {
  margin: 0;
  color: #172033;
  font-size: 24px;
}

h3 {
  margin: 0 0 12px;
  color: #172033;
  font-size: 17px;
}

.muted {
  margin: 8px 0 0;
  color: #607086;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(140px, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.stat-card {
  padding: 18px;
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
}

.stat-card span {
  display: block;
  color: #607086;
  font-size: 13px;
}

.stat-card strong {
  display: block;
  margin-top: 8px;
  color: #172033;
  font-size: 28px;
}

.info-card,
.section-card {
  margin-top: 16px;
  border-radius: 8px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.record-filters {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  width: min(680px, 100%);
}

.record-filter {
  width: min(420px, 100%);
}

.department-filter {
  width: min(240px, 100%);
}

.drawer-section + .drawer-section {
  margin-top: 24px;
}

:deep(.el-card__header) {
  color: #172033;
  font-size: 18px;
  font-weight: 700;
}

@media (max-width: 1100px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(140px, 1fr));
  }
}

@media (max-width: 720px) {
  .overview-panel,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .record-filters,
  .record-filter,
  .department-filter {
    width: 100%;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  :deep(.el-drawer) {
    width: 92% !important;
  }
}
</style>
