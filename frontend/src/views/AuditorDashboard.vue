<script setup lang="ts">
import DashboardLayout from "../layouts/DashboardLayout.vue";
</script>

<template>
  <DashboardLayout title="Auditor Dashboard">
    <el-alert
      title="Auditor account signed in successfully."
      type="success"
      show-icon
      :closable="false"
    />
  </DashboardLayout>
</template>
