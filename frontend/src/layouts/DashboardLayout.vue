<script setup lang="ts">
import { useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

defineProps<{
  title: string;
}>();

const router = useRouter();
const auth = useAuthStore();

const roleLabels: Record<string, string> = {
  PATIENT: "Patient",
  DOCTOR: "Doctor",
  ADMIN: "Admin",
  AUDITOR: "Auditor",
};

function logout() {
  auth.logout();
  router.push("/login");
}
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <h1>{{ title }}</h1>
        <p>{{ auth.user?.username }} · {{ roleLabels[auth.user?.role || ""] || auth.user?.role }}</p>
      </div>

      <el-button type="danger" plain @click="logout">Logout</el-button>
    </header>

    <section class="dashboard-content">
      <slot />
    </section>
  </main>
</template>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  background: #f4f7fb;
}

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 32px;
  background: #ffffff;
  border-bottom: 1px solid #d9e2ec;
}

h1 {
  margin: 0;
  color: #172033;
  font-size: 26px;
}

p {
  margin: 6px 0 0;
  color: #607086;
}

.dashboard-content {
  padding: 32px;
}
</style>
