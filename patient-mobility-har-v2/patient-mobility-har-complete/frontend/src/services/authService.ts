import { api } from "./api";

export type UserRole = "admin" | "caregiver";

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);

  const { data } = await api.post<LoginResponse>("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function registerUser(name: string, email: string, password: string, role: UserRole): Promise<User> {
  const { data } = await api.post<User>("/auth/register", { name, email, password, role });
  return data;
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  const { data } = await api.post("/auth/forgot-password", { email });
  return data;
}

export async function resetPassword(token: string, new_password: string): Promise<{ message: string }> {
  const { data } = await api.post("/auth/reset-password", { token, new_password });
  return data;
}
