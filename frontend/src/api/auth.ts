import { api } from "./client";

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  full_name: string;
  gender: string;
  birth_date: string;
  phone: string;
  address: string;
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
  return api.post<unknown, LoginResponse>("/api/auth/login", data);
}

export function register(data: RegisterRequest) {
  return api.post<unknown, UserInfo>("/api/auth/register", data);
}

export function getMe() {
  return api.get<unknown, UserInfo>("/api/auth/me");
}
