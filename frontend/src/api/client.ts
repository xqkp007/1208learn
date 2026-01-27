import axios from 'axios';
import { useAuthStore } from '@/store/auth';

const DEFAULT_LOCAL_BASE_URL = 'http://127.0.0.1:8011';
const envBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
export const API_BASE_URL =
  envBaseUrl?.trim() || (import.meta.env.DEV ? DEFAULT_LOCAL_BASE_URL : '');
const LOGIN_PATH = '/login';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const url: string | undefined = error?.config?.url;

    if (status === 401) {
      // Avoid clearing state when the login request itself is unauthorized (wrong password).
      if (!url?.includes('/api/v1.6/auth/login')) {
        const { clearAuth } = useAuthStore.getState();
        clearAuth();
        if (typeof window !== 'undefined' && window.location.pathname !== LOGIN_PATH) {
          window.location.assign(LOGIN_PATH);
        }
      }
    }

    return Promise.reject(error);
  },
);
