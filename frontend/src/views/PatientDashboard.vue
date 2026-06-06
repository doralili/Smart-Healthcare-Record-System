<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import {
  getMyCombinedRecord,
  type PatientRecordDetail,
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

interface VisitRow {
  key: string;
  title: string;
  date: string;
  rawDate: unknown;
  dateValue: number | null;
  dateKey: string;
  encounterId: string | null;
  departments: string;
  visitTypes: string;
  classes: string;
  statuses: string;
  doctors: string;
  clinicalSummary: string;
  diagnoses: DiagnosisRow[];
  encounters: TimelineRow[];
  medications: TimelineRow[];
  observations: TimelineRow[];
  procedures: TimelineRow[];
}

const auth = useAuthStore();

const loading = ref(false);
const selectedRecord = ref<PatientRecordDetail | null>(null);
const diagnosisDateQuery = ref("");
const diagnosisDepartmentQuery = ref("");
const selectedVisit = ref<VisitRow | null>(null);
const visitDrawerVisible = ref(false);
const selectedVisitDepartmentFilter = ref("");

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
const VISIT_TYPE_FALLBACK = "General Clinical Visit";
const VISIT_CLASS_FALLBACK = "GENERAL";

const diagnosisRows = computed<DiagnosisRow[]>(() => {
  return (record.value?.conditions ?? []).map((item: unknown, index) => {
    const condition = asRecord(item);
    const rawDate = condition.recorded_date;
    const encounterId = getEncounterId(condition);
    const dateKey = formatDateKey(rawDate);
    const diagnosis = cleanMedicalText(condition.code);
    const department = formatPrimaryDepartment(condition.department);
    const status = formatStatus(condition.clinical_status);

    return {
      index,
      diagnosis,
      department,
      status,
      date: formatDateTime(rawDate),
      rawDate,
      dateValue: toTime(rawDate),
      dateKey,
      encounterId,
      doctor_name: typeof condition.doctor_name === "string" ? condition.doctor_name : undefined,
      raw: [condition],
    };
  });
});

const visitRows = computed<VisitRow[]>(() => {
  const grouped = new Map<string, VisitRow>();
  const encounterRows = buildTimelineRows("encounters");
  const medicationRows = buildTimelineRows("medications");
  const observationRows = buildTimelineRows("observations");
  const procedureRows = buildTimelineRows("procedures");

  diagnosisRows.value.forEach((diagnosis) => {
    const relatedEncounters = encounterRows.filter((row) => isRelatedToDiagnosis(row, diagnosis));
    const relatedMedications = medicationRows.filter((row) => isRelatedToDiagnosis(row, diagnosis));
    const relatedObservations = observationRows.filter((row) => isRelatedToDiagnosis(row, diagnosis));
    const relatedProcedures = procedureRows.filter((row) => isRelatedToDiagnosis(row, diagnosis));
    const firstEncounter = relatedEncounters[0];
    const key = getVisitGroupKey(
      firstEncounter?.encounterId || diagnosis.encounterId,
      firstEncounter?.dateKey || diagnosis.dateKey,
      `diagnosis-${diagnosis.index}`,
    );
    const visit = ensureVisit(grouped, key, {
      encounter: firstEncounter,
      date: firstEncounter?.date || diagnosis.date,
      rawDate: firstEncounter?.rawDate || diagnosis.rawDate,
      dateKey: firstEncounter?.dateKey || diagnosis.dateKey,
      encounterId: firstEncounter?.encounterId || diagnosis.encounterId,
      department: diagnosis.department,
      status: diagnosis.status,
    });

    visit.diagnoses.push(diagnosis);
    visit.encounters = dedupeRelatedRows([...visit.encounters, ...relatedEncounters]);
    visit.medications = dedupeRelatedRows([...visit.medications, ...relatedMedications]);
    visit.observations = dedupeRelatedRows([...visit.observations, ...relatedObservations]);
    visit.procedures = dedupeRelatedRows([...visit.procedures, ...relatedProcedures]);
    visit.departments = joinUniqueText(visit.departments, diagnosis.department);
    visit.statuses = joinUniqueText(visit.statuses, diagnosis.status);
    if (diagnosis.doctor_name) {
      visit.doctors = joinUniqueText(visit.doctors, diagnosis.doctor_name);
    }
    refreshVisitSummary(visit);
  });

  encounterRows.forEach((encounter, index) => {
    const key = getVisitGroupKey(encounter.encounterId, encounter.dateKey, `encounter-${index}`);
    if (grouped.has(key)) {
      return;
    }

    const visit = ensureVisit(grouped, key, {
      encounter,
      date: encounter.date,
      rawDate: encounter.rawDate,
      dateKey: encounter.dateKey,
      encounterId: encounter.encounterId,
      status: encounter.status,
    });
    refreshVisitSummary(visit);
  });

  return Array.from(grouped.values()).filter((visit) =>
    visit.diagnoses.length > 0 ||
    visit.medications.length > 0 ||
    visit.observations.length > 0 ||
    visit.procedures.length > 0
  ).sort((first, second) => {
    if (first.dateValue === null && second.dateValue === null) {
      return first.title.localeCompare(second.title);
    }
    if (first.dateValue === null) return 1;
    if (second.dateValue === null) return -1;
    return second.dateValue - first.dateValue;
  });
});

const filteredVisitRows = computed(() => {
  const query = normalizeSearchText(diagnosisDateQuery.value);
  const departmentQuery = normalizeSearchText(diagnosisDepartmentQuery.value);

  if (!query && !departmentQuery) {
    return visitRows.value;
  }

  return visitRows.value.filter((item) => {
    const searchable = normalizeSearchText(
      [
        item.title,
        item.departments,
        item.visitTypes,
        item.classes,
        item.statuses,
        item.date,
        item.rawDate,
        formatDateOnly(item.rawDate),
        item.diagnoses.map((diagnosis) => diagnosis.diagnosis).join(" "),
      ].join(" "),
    );

    const department = normalizeSearchText(item.departments);
    const matchesKeyword = !query || searchable.includes(query);
    const matchesDepartment = !departmentQuery || department.includes(departmentQuery);

    return matchesKeyword && matchesDepartment;
  });
});

const overviewItems = computed(() => [
  {
    label: "Visits",
    value: visitRows.value.length,
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

const filteredAvailableDoctors = computed(() => {
  const query = availableDoctorDepartmentQuery.value.trim().toLowerCase();
  if (!query) {
    return availableDoctors.value;
  }

  return availableDoctors.value.filter((doctor) =>
    (doctor.department || '').toLowerCase().includes(query),
  );
});

const selectedVisitDepartmentOptions = computed(() => {
  if (!selectedVisit.value) {
    return [];
  }

  const departments = [
    ...selectedVisit.value.diagnoses.map((item) => item.department),
    ...selectedVisit.value.medications.map((item) => item.department || ""),
    ...selectedVisit.value.observations.map((item) => item.department || ""),
    ...selectedVisit.value.procedures.map((item) => item.department || ""),
  ]
    .flatMap(splitDepartments)
    .filter((item) => item && item !== "Not recorded");

  return Array.from(new Set(departments)).sort((first, second) =>
    first.localeCompare(second),
  );
});

const filteredSelectedDiagnoses = computed(() => {
  if (!selectedVisit.value) {
    return [];
  }

  return selectedVisit.value.diagnoses.filter((item) =>
    departmentMatchesFilter(item.department, selectedVisitDepartmentFilter.value),
  );
});

const filteredSelectedMedications = computed(() => {
  if (!selectedVisit.value) {
    return [];
  }

  return selectedVisit.value.medications.filter((item) =>
    departmentMatchesFilter(item.department, selectedVisitDepartmentFilter.value),
  );
});

const filteredSelectedObservations = computed(() => {
  if (!selectedVisit.value) {
    return [];
  }

  return selectedVisit.value.observations.filter((item) =>
    departmentMatchesFilter(item.department, selectedVisitDepartmentFilter.value),
  );
});

const filteredSelectedProcedures = computed(() => {
  if (!selectedVisit.value) {
    return [];
  }

  return selectedVisit.value.procedures.filter((item) =>
    departmentMatchesFilter(item.department, selectedVisitDepartmentFilter.value),
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

watch(filteredVisitRows, (rows) => {
  if (!selectedVisit.value) {
    return;
  }

  const stillVisible = rows.some((row) => row.key === selectedVisit.value?.key);
  if (!stillVisible) {
    visitDrawerVisible.value = false;
    selectedVisit.value = null;
  }
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
    return "";
  }

  return String(value);
}

function formatPrimaryDepartment(value: unknown) {
  return formatDepartment(value)
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean)[0] || "";
}

function splitDepartments(value: unknown) {
  return formatDepartment(value)
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean);
}

function departmentMatchesFilter(department: unknown, filter: string) {
  const normalizedFilter = normalizeSearchText(filter);
  if (!normalizedFilter) {
    return true;
  }

  return splitDepartments(department).some(
    (item) => normalizeSearchText(item) === normalizedFilter,
  );
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

function getEncounterId(source: Record<string, unknown>, allowOwnId = false) {
  const directValue = source.encounter_id;

  if (directValue) {
    return String(directValue);
  }

  if (allowOwnId && source.id) {
    return String(source.id);
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
  if (!next.trim()) {
    return current;
  }

  const values = current
    .split("; ")
    .map((item) => item.trim())
    .filter((item) => item && item !== "Not recorded");

  if (!values.includes(next)) {
    values.push(next);
  }

  return values.join("; ");
}

function getVisitTypes(encounters: TimelineRow[]) {
  const values = encounters
    .map((encounter) => encounter.name)
    .filter((value) => value && value !== "Not recorded");
  return values.length ? Array.from(new Set(values)).join("; ") : VISIT_TYPE_FALLBACK;
}

function getVisitClasses(encounters: TimelineRow[]) {
  const values = encounters
    .map((encounter) => encounter.type)
    .filter((value) => value && value !== "Not recorded");
  return values.length ? Array.from(new Set(values)).join("; ") : VISIT_CLASS_FALLBACK;
}

function getClinicalSummary(visit: VisitRow) {
  const diagnoses = visit.diagnoses.map((item) => item.diagnosis);
  const treatments = [
    ...visit.medications.map((item) => item.name),
    ...visit.observations.map((item) => item.name),
    ...visit.procedures.map((item) => item.name),
  ];

  const sections = [
    diagnoses.length ? `Diagnosis: ${Array.from(new Set(diagnoses)).join("; ")}` : "",
    treatments.length ? `Care: ${Array.from(new Set(treatments)).join("; ")}` : "",
  ].filter(Boolean);

  return sections.length ? sections.join(" | ") : "Not recorded";
}

function isRelatedToDiagnosis(item: TimelineRow, diagnosis: DiagnosisRow | null) {
  if (!diagnosis) {
    return false;
  }

  if (diagnosis.encounterId && item.encounterId && diagnosis.encounterId === item.encounterId) {
    return true;
  }

  return Boolean(diagnosis.dateKey && item.dateKey && diagnosis.dateKey === item.dateKey);
}

function buildTimelineRows(
  category: "encounters" | "medications" | "observations" | "procedures",
): TimelineRow[] {
  if (!record.value) {
    return [];
  }

  const rows = (record.value[category] ?? []).map((item: unknown): TimelineRow => {
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
        encounterId: getEncounterId(source, true),
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
  });

  return dedupeRelatedRows(rows);
}

function getVisitGroupKey(encounterId: string | null, dateKey: string, fallback: string) {
  if (dateKey) {
    return `date:${dateKey}`;
  }
  if (encounterId) {
    return `encounter:${encounterId}`;
  }
  return fallback;
}

function ensureVisit(
  grouped: Map<string, VisitRow>,
  key: string,
  seed: {
    encounter?: TimelineRow;
    date: string;
    rawDate: unknown;
    dateKey: string;
    encounterId: string | null;
    department?: string;
    status?: string;
  },
) {
  const existing = grouped.get(key);
  if (existing) {
    return existing;
  }

  const visit: VisitRow = {
    key,
    title: seed.dateKey ? `Visit ${seed.dateKey}` : seed.encounter?.name || "Visit Unknown",
    date: seed.date,
    rawDate: seed.rawDate,
    dateValue: toTime(seed.rawDate),
    dateKey: seed.dateKey,
    encounterId: seed.encounterId,
    departments: seed.department || "",
    visitTypes: seed.encounter?.name && seed.encounter.name !== "Not recorded"
      ? seed.encounter.name
      : VISIT_TYPE_FALLBACK,
    classes: seed.encounter?.type && seed.encounter.type !== "Not recorded"
      ? seed.encounter.type
      : VISIT_CLASS_FALLBACK,
    statuses: seed.status || seed.encounter?.status || "Not recorded",
    doctors: "Not recorded",
    clinicalSummary: "Not recorded",
    diagnoses: [],
    encounters: seed.encounter ? [seed.encounter] : [],
    medications: [],
    observations: [],
    procedures: [],
  };

  grouped.set(key, visit);
  return visit;
}

function refreshVisitSummary(visit: VisitRow) {
  const encounterStatus = visit.encounters
    .map((encounter) => encounter.status || "")
    .filter(Boolean)
    .join("; ");

  if (!visit.statuses || visit.statuses === "Not recorded") {
    visit.statuses = encounterStatus || "Not recorded";
  }

  visit.visitTypes = getVisitTypes(visit.encounters);
  visit.classes = getVisitClasses(visit.encounters);
  visit.title = visit.dateKey ? `Visit ${visit.dateKey}` : visit.visitTypes;
  visit.clinicalSummary = getClinicalSummary(visit);
  visit.dateValue = toTime(visit.rawDate);
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

function openVisit(row: VisitRow) {
  selectedVisit.value = row;
  selectedVisitDepartmentFilter.value = "";
  visitDrawerVisible.value = true;
}

async function loadRecords() {
  if (!auth.token) {
    ElMessage.error("Please sign in again.");
    return;
  }

  loading.value = true;

  try {
    const res = await getMyCombinedRecord(auth.token);
    selectedRecord.value = res.data;
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

            <el-card class="section-card" shadow="never">
              <template #header>
                <div class="section-header">
                  <span>Visits</span>
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
                :data="filteredVisitRows"
                border
                empty-text="No visits match these filters."
              >
                <el-table-column prop="departments" label="Department" min-width="170" />
                <el-table-column prop="visitTypes" label="Visit Type" min-width="220" />
                <el-table-column prop="classes" label="Class" width="120" />
                <el-table-column prop="date" label="Date" width="190" />
                <el-table-column label="Diagnoses" width="110">
                  <template #default="{ row }">
                    {{ row.diagnoses.length }}
                  </template>
                </el-table-column>
                <el-table-column label="Lab / Vital" width="110">
                  <template #default="{ row }">
                    {{ row.observations.length }}
                  </template>
                </el-table-column>
                <el-table-column label="Medications" width="120">
                  <template #default="{ row }">
                    {{ row.medications.length }}
                  </template>
                </el-table-column>
                <el-table-column label="Procedures" width="110">
                  <template #default="{ row }">
                    {{ row.procedures.length }}
                  </template>
                </el-table-column>
                <el-table-column label="Details" width="120">
                  <template #default="{ row }">
                    <el-button type="primary" link @click="openVisit(row)">
                      View
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>

            <el-drawer
              v-model="visitDrawerVisible"
              size="58%"
              :title="selectedVisit?.title || 'Visit Details'"
            >
              <template v-if="selectedVisit">
                <section class="drawer-section">
                  <h3>Visit Information</h3>
                  <el-descriptions :column="2" border>
                    <el-descriptions-item label="Visit Type">
                      {{ selectedVisit.visitTypes }}
                    </el-descriptions-item>
                    <el-descriptions-item label="Department">
                      {{ selectedVisit.departments }}
                    </el-descriptions-item>
                    <el-descriptions-item label="Class">
                      {{ selectedVisit.classes }}
                    </el-descriptions-item>
                    <el-descriptions-item label="Date">
                      {{ selectedVisit.date }}
                    </el-descriptions-item>
                    <el-descriptions-item label="Doctor">
                       {{ selectedVisit.doctors }}
                    </el-descriptions-item>
                  </el-descriptions>
                </section>

                <section class="drawer-section drawer-filter-section">
                  <el-select
                    v-model="selectedVisitDepartmentFilter"
                    clearable
                    filterable
                    class="drawer-department-filter"
                    placeholder="Filter by department"
                  >
                    <el-option
                      v-for="department in selectedVisitDepartmentOptions"
                      :key="department"
                      :label="department"
                      :value="department"
                    />
                  </el-select>
                </section>

                <section class="drawer-section">
                  <h3>Diagnoses</h3>
                  <el-table
                    :data="filteredSelectedDiagnoses"
                    border
                    empty-text="No diagnoses found for this visit."
                  >
                    <el-table-column prop="department" label="Department" width="170" />
                    <el-table-column prop="diagnosis" label="Diagnosis" min-width="260" />
                    <el-table-column prop="status" label="Status" width="140" />
                    <el-table-column prop="date" label="Recorded At" width="190" />
                  </el-table>
                </section>

                <section class="drawer-section">
                  <h3>Medications</h3>
                  <el-table
                    :data="filteredSelectedMedications"
                    border
                    empty-text="No medication found for this visit."
                  >
                    <el-table-column prop="department" label="Department" width="170" />
                    <el-table-column prop="name" label="Medication" min-width="280" />
                    <el-table-column prop="status" label="Status" width="140" />
                    <el-table-column prop="date" label="Prescribed At" width="190" />
                  </el-table>
                </section>

                <section class="drawer-section">
                  <h3>Lab / Vital Results</h3>
                  <el-table
                    :data="filteredSelectedObservations"
                    border
                    empty-text="No lab or vital result found for this visit."
                  >
                    <el-table-column prop="department" label="Department" width="170" />
                    <el-table-column prop="name" label="Item" min-width="240" />
                    <el-table-column prop="value" label="Result" min-width="180" />
                    <el-table-column prop="status" label="Status" width="140" />
                    <el-table-column prop="date" label="Date" width="190" />
                  </el-table>
                </section>

                <section class="drawer-section">
                  <h3>Procedures</h3>
                  <el-table
                    :data="filteredSelectedProcedures"
                    border
                    empty-text="No procedure found for this visit."
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

.drawer-filter-section {
  display: flex;
  justify-content: flex-end;
}

.drawer-department-filter {
  width: min(280px, 100%);
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
  .department-filter,
  .drawer-department-filter {
    width: 100%;
  }

  .drawer-filter-section {
    justify-content: stretch;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  :deep(.el-drawer) {
    width: 92% !important;
  }
}
</style>
