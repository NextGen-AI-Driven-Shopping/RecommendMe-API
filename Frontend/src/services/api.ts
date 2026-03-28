import axios from 'axios';
import { QueryRequest, QueryResponse, HealthResponse } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  async query(request: QueryRequest): Promise<QueryResponse> {
    const response = await apiClient.post<QueryResponse>('/v1/query', request);
    return response.data;
  },

  async health(): Promise<HealthResponse> {
    const response = await apiClient.get<HealthResponse>('/v1/health');
    return response.data;
  },

  async root() {
    const response = await apiClient.get('/');
    return response.data;
  },
};

export default apiClient;
