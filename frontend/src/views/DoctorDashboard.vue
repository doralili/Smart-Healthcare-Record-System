<script setup lang="ts">
import DashboardLayout from "../layouts/DashboardLayout.vue";
</script>

<template>
  <DashboardLayout title="Doctor Dashboard">
    <el-alert
      title="Doctor account signed in successfully."
      type="success"
      show-icon
      :closable="false"
    />
  </DashboardLayout>
</template>
