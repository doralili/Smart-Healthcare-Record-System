<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();

function go(path: string) {
  if (route.path !== path) {
    router.push(path);
  }
}
</script>

<template>
  <nav class="auditor-nav" aria-label="Auditor sections">
    <button
      type="button"
      :class="{ active: route.path === '/auditor' }"
      @click="go('/auditor')"
    >
      Audit Logs
    </button>
    <button
      type="button"
      :class="{ active: route.path === '/auditor/watermarks' }"
      @click="go('/auditor/watermarks')"
    >
      Record Watermarks
    </button>
  </nav>
</template>

<style scoped>
.auditor-nav {
  display: flex;
  gap: 6px;
  width: fit-content;
  padding: 4px;
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
}

.auditor-nav button {
  min-width: 150px;
  padding: 10px 16px;
  color: #52637a;
  font: inherit;
  font-weight: 700;
  background: transparent;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
}

.auditor-nav button.active {
  color: #ffffff;
  background: #2f80ed;
}

.auditor-nav button:not(.active):hover {
  color: #172033;
  background: #f4f7fb;
}

@media (max-width: 640px) {
  .auditor-nav {
    width: 100%;
  }

  .auditor-nav button {
    min-width: 0;
    flex: 1;
  }
}
</style>
