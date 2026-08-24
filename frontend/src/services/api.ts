import axios, { AxiosError } from 'axios';
import { API_BASE_URL } from '../utils/constants';
import type { ApiError } from '../types/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: Attach JWT Token if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Response Interceptor: Handle API errors centrally
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    const status = error.response?.status;

    if (status === 401) {
      localStorage.removeItem('access_token');
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }

    if (status === 429) {
      window.dispatchEvent(
        new CustomEvent('api-rate-limit', {
          detail: {
            message: "You're sending requests too quickly. Please wait a moment and try again.",
          },
        })
      );
    }
    
    const errorData = error.response?.data;
    let message = 'An unexpected error occurred.';
    if (typeof errorData?.error === 'object' && errorData.error?.message) {
      message = errorData.error.message;
    } else if (typeof errorData?.error === 'string') {
      message = errorData.error;
    } else if (typeof (errorData as any)?.detail?.message === 'string') {
      message = (errorData as any).detail.message;
    } else if (typeof (errorData as any)?.detail === 'string') {
      message = (errorData as any).detail;
    } else if (error.message) {
      message = error.message;
    }

    return Promise.reject({
      status: error.response?.status,
      code: errorData?.error?.code || (errorData as any)?.detail?.code || 'UNKNOWN_ERROR',
      message,
      originalError: error,
    });
  }
);

export default api;
