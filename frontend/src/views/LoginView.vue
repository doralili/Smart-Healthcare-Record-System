<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { useAuthStore } from "../stores/auth";
import { roleHomeMap } from "../router";

const router = useRouter();
const auth = useAuthStore();

const loading = ref(false);

const form = reactive({
  username: "doctor1",
  password: "password123",
});

async function submitLogin() {
  loading.value = true;

  try {
    const user = await auth.login(form.username, form.password);
    ElMessage.success(`Welcome, ${user.username}`);
    await router.push(roleHomeMap[user.role] || "/login");
  } catch (error: any) {
    if (!error.response) {
      ElMessage.error("Cannot connect to backend server");
    } else if (error.response.status === 401) {
      ElMessage.error("Invalid username or password");
    } else {
      ElMessage.error("Login failed");
    }
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <h1>Smart Healthcare Security</h1>
      <p>Sign in with a demo account.</p>

      <el-form label-position="top" @submit.prevent="submitLogin">
        <el-form-item label="Username">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>

        <el-form-item label="Password">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            show-password
          />
        </el-form-item>

        <el-button
          type="primary"
          :loading="loading"
          class="login-button"
          @click="submitLogin"
        >
          Login
        </el-button>
      </el-form>

      <div class="demo-users">
        <span>patient1</span>
        <span>doctor1</span>
        <span>admin</span>
        <span>auditor</span>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #f4f7fb;
}

.login-panel {
  width: min(420px, calc(100vw - 32px));
  padding: 28px;
  background: #ffffff;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  box-shadow: 0 12px 32px rgb(15 23 42 / 8%);
}

h1 {
  margin: 0 0 8px;
  font-size: 26px;
  color: #172033;
}

p {
  margin: 0 0 24px;
  color: #607086;
}

.login-button {
  width: 100%;
}

.demo-users {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 18px;
  color: #607086;
  font-size: 13px;
  text-align: center;
}
</style>
