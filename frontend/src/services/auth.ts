import api from './api';
import type { TokenResponse, User } from '../types/api';

export async function login(username: string, password: string): Promise<TokenResponse> {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const response = await api.post<TokenResponse>('/api/v1/auth/token', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
}

export async function register(email: string, password: string, organizationName: string): Promise<User> {
  const response = await api.post<User>('/api/v1/auth/register', {
    email,
    password,
    organization_name: organizationName,
  });
  return response.data;
}

export async function getMe(): Promise<User> {
  const response = await api.get<User>('/api/v1/auth/me');
  return response.data;
}
