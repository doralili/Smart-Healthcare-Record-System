<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";
import { roleHomeMap } from "../router";
import { ElMessage } from "../utils/message";

const router = useRouter();
const auth = useAuthStore();

const loading = ref(false);
const mode = ref<"login" | "register">("login");

const form = reactive({
  username: "",
  password: "",
  gender: "",
  birth_date: "",
  phone: "",
  address: "",
});

async function submitLogin() {
  if (loading.value) {
    return;
  }

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

async function submitRegister() {
  if (loading.value) {
    return;
  }

  if (
    !form.username.trim() ||
    !form.password ||
    !form.gender ||
    !form.birth_date ||
    !form.phone.trim() ||
    !form.address.trim()
  ) {
    ElMessage.error("Please complete all registration fields");
    return;
  }

  loading.value = true;

  try {
    const user = await auth.registerPatient({
      username: form.username,
      password: form.password,
      gender: form.gender,
      birth_date: form.birth_date,
      phone: form.phone,
      address: form.address,
    });
    ElMessage.success(`Patient account created: ${user.username}`);
    mode.value = "login";
  } catch (error: any) {
    if (!error.response) {
      ElMessage.error("Cannot connect to backend server");
    } else if (error.response.status === 409) {
      ElMessage.error("Username already exists");
    } else if (error.response.status === 400) {
      ElMessage.error(error.response.data?.detail || "Invalid registration information");
    } else {
      ElMessage.error("Registration failed");
    }
  } finally {
    loading.value = false;
  }
}

function submitForm() {
  if (mode.value === "register") {
    submitRegister();
    return;
  }

  submitLogin();
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <h1>Smart Healthcare Security</h1>
      <p>{{ mode === "login" ? "Sign in with a demo account." : "Create a patient account." }}</p>

      <el-radio-group v-model="mode" class="mode-switch">
        <el-radio-button label="login">Login</el-radio-button>
        <el-radio-button label="register">Patient Sign Up</el-radio-button>
      </el-radio-group>

      <el-form label-position="top" @submit.prevent="submitForm">
        <el-form-item label="Username">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>

        <el-form-item label="Password">
          <el-input
            v-model="form.password"
            type="password"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
            show-password
          />
        </el-form-item>

        <template v-if="mode === 'register'">
          <el-form-item label="Gender">
            <el-select v-model="form.gender" placeholder="Select gender">
              <el-option label="Female" value="female" />
              <el-option label="Male" value="male" />
              <el-option label="Other" value="other" />
            </el-select>
          </el-form-item>

          <el-form-item label="Birth Date">
            <el-date-picker
              v-model="form.birth_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="Select birth date"
              class="field-control"
            />
          </el-form-item>

          <el-form-item label="Phone">
            <el-input v-model="form.phone" autocomplete="tel" />
          </el-form-item>

          <el-form-item label="Address">
            <el-input
              v-model="form.address"
              type="textarea"
              :rows="3"
              autocomplete="street-address"
            />
          </el-form-item>
        </template>

        <el-button
          native-type="submit"
          type="primary"
          :loading="loading"
          class="login-button"
          @click="submitForm"
        >
          {{ mode === "login" ? "Login" : "Create Patient Account" }}
        </el-button>
      </el-form>
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

.mode-switch {
  width: 100%;
  margin-bottom: 20px;
}

.mode-switch :deep(.el-radio-button) {
  width: 50%;
}

.mode-switch :deep(.el-radio-button__inner) {
  width: 100%;
}

.login-button {
  width: 100%;
}

.field-control {
  width: 100%;
}

</style>
