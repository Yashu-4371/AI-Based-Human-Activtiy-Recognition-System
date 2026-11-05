import axios from "axios";

export const api = axios.create({
  baseURL: "/api/v1",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  // Note: token storage here uses localStorage for simplicity in this
  // reference implementation. For a production deployment, prefer an
  // httpOnly cookie issued by the backend to reduce XSS token-theft risk.
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("current_user");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
