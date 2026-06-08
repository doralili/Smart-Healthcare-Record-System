import { createRouter, createWebHistory } from "vue-router";

import LoginView from "../views/LoginView.vue";
import PatientDashboard from "../views/PatientDashboard.vue";
import DoctorDashboard from "../views/DoctorDashboard.vue";
import AdminDashboard from "../views/AdminDashboard.vue";
import AuditorDashboard from "../views/AuditorDashboard.vue";
import AuditorWatermarks from "../views/AuditorWatermarks.vue";
import { useAuthStore } from "../stores/auth";

const roleHomeMap: Record<string, string> = {
  PATIENT: "/patient",
  DOCTOR: "/doctor",
  ADMIN: "/admin",
  AUDITOR: "/auditor",
};

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      redirect: "/login",
    },
    {
      path: "/login",
      component: LoginView,
      meta: { public: true },
    },
    {
      path: "/patient",
      component: PatientDashboard,
      meta: { role: "PATIENT" },
    },
    {
      path: "/doctor",
      component: DoctorDashboard,
      meta: { role: "DOCTOR" },
    },
    {
      path: "/admin",
      component: AdminDashboard,
      meta: { role: "ADMIN" },
    },
    {
      path: "/auditor",
      component: AuditorDashboard,
      meta: { role: "AUDITOR" },
    },
    {
      path: "/auditor/watermarks",
      component: AuditorWatermarks,
      meta: { role: "AUDITOR" },
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  const hasValidSession = await auth.verifySession();

  if (to.meta.public) {
    if (hasValidSession && auth.role) {
      return roleHomeMap[auth.role] || "/login";
    }
    return true;
  }

  if (!hasValidSession) {
    return "/login";
  }

  if (to.meta.role && auth.role !== to.meta.role) {
    return roleHomeMap[auth.role] || "/login";
  }

  return true;
});

export { roleHomeMap };
export default router;
