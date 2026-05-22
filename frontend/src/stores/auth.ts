import { defineStore } from "pinia";
import { login, register, type UserInfo } from "../api/auth";

interface AuthState {
  token: string;
  user: UserInfo | null;
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    token: localStorage.getItem("token") || "",
    user: JSON.parse(localStorage.getItem("user") || "null"),
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

      return res.data.user;
    },

    async registerPatient(username: string, password: string) {
      const res = await register({ username, password });
      return res.data;
    },

    logout() {
      this.token = "";
      this.user = null;

      localStorage.removeItem("token");
      localStorage.removeItem("user");
    },
  },
});
