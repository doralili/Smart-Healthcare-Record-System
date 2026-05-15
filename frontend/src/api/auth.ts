import axios from "axios";

export const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
});

export interface LoginRequest {
  username: string;
  password: string;
}

export interface UserInfo {
  id: number;
  username: string;
  role: "PATIENT" | "DOCTOR" | "ADMIN" | "AUDITOR";
  status: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

export function login(data: LoginRequest) {
  return api.post<LoginResponse>("/api/auth/login", data);
}

export function getMe(token: string) {
  return api.get<UserInfo>("/api/auth/me", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}
