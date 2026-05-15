<script setup lang="ts">
import DashboardLayout from "../layouts/DashboardLayout.vue";
</script>

<template>
  <DashboardLayout title="Admin Dashboard">
    <el-alert
      title="Admin account signed in successfully."
      type="success"
      show-icon
      :closable="false"
    />
  </DashboardLayout>
</template>
