import { defineStore } from "pinia";
import { getMe, login, register, type UserInfo } from "../api/auth";

interface AuthState {
  token: string;
  user: UserInfo | null;
  sessionVerified: boolean;
}

function isTokenExpired(token: string) {
  try {
    const payloadPart = token.split(".")[1] || "";
    const normalizedPayload = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
    const paddedPayload = normalizedPayload.padEnd(
      normalizedPayload.length + ((4 - (normalizedPayload.length % 4)) % 4),
      "=",
    );
    const payload = JSON.parse(atob(paddedPayload));
    if (!payload.exp) {
      return true;
    }
    return Date.now() >= payload.exp * 1000;
  } catch {
    return true;
  }
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    token: localStorage.getItem("token") || "",
    user: JSON.parse(localStorage.getItem("user") || "null"),
    sessionVerified: false,
  }),

  getters: {
    isLoggedIn: (state) => Boolean(state.token && state.user),
    role: (state) => state.user?.role || "",
  },

  actions: {
    async login(username: string, password: string) {
      const res = await login({ username, password });

      this.token = res.data.access_token;
      this.user = res.data.user;

      localStorage.setItem("token", this.token);
      localStorage.setItem("user", JSON.stringify(this.user));
      this.sessionVerified = true;

      return res.data.user;
    },

    async registerPatient(payload: {
      username: string;
      password: string;
      full_name: string;
      gender: string;
      birth_date: string;
      phone: string;
      address: string;
    }) {
      const res = await register(payload);
      return res.data;
    },

    logout() {
      this.token = "";
      this.user = null;
      this.sessionVerified = false;

      localStorage.removeItem("token");
      localStorage.removeItem("user");
    },

    async verifySession() {
      if (!this.token || isTokenExpired(this.token)) {
        this.logout();
        return false;
      }

      if (this.sessionVerified && this.user) {
        return true;
      }

      try {
        const res = await getMe(this.token);
        this.user = res.data;
        this.sessionVerified = true;
        localStorage.setItem("user", JSON.stringify(this.user));
        return true;
      } catch {
        this.logout();
        return false;
      }
    },
  },
});
