<script setup lang="ts">
import DashboardLayout from "../layouts/DashboardLayout.vue";
</script>

<template>
  <DashboardLayout title="Patient Dashboard">
    <el-alert
      title="Patient account signed in successfully."
      type="success"
      show-icon
      :closable="false"
    />
  </DashboardLayout>
</template>
