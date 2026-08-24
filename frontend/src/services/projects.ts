import api from './api';
import type { Project } from '../types/api';

export async function getProjects(): Promise<Project[]> {
  const response = await api.get<any>('/api/v1/projects');
  if (Array.isArray(response.data)) {
    return response.data;
  }
  if (response.data && Array.isArray(response.data.items)) {
    return response.data.items;
  }
  return [];
}

export async function createProject(name: string): Promise<Project> {
  const response = await api.post<Project>('/api/v1/projects', { name });
  return response.data;
}
