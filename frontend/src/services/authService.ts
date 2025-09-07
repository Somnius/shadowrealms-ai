import axios from 'axios';
import { 
  LoginCredentials, 
  RegisterData, 
  PasswordResetRequest, 
  PasswordResetData, 
  AuthResponse 
} from '../types/auth';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle token expiration
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authService = {
  // Login user
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await api.post('/api/auth/login', credentials);
    return response.data;
  },

  // Register new user
  async register(userData: RegisterData): Promise<AuthResponse> {
    const response = await api.post('/api/auth/register', userData);
    return response.data;
  },

  // Request password reset
  async requestPasswordReset(data: PasswordResetRequest): Promise<{ message: string }> {
    const response = await api.post('/api/auth/forgot-password', data);
    return response.data;
  },

  // Reset password with token
  async resetPassword(data: PasswordResetData): Promise<{ message: string }> {
    const response = await api.post('/api/auth/reset-password', data);
    return response.data;
  },

  // Get current user profile
  async getProfile(): Promise<{ user: any }> {
    const response = await api.get('/api/auth/profile');
    return response.data;
  },

  // Update user profile
  async updateProfile(userData: Partial<RegisterData>): Promise<{ user: any }> {
    const response = await api.put('/api/auth/profile', userData);
    return response.data;
  },

  // Logout user
  async logout(): Promise<void> {
    try {
      await api.post('/api/auth/logout');
    } catch (error) {
      // Even if logout fails on server, clear local storage
      console.error('Logout error:', error);
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
  },

  // Verify token validity
  async verifyToken(): Promise<boolean> {
    try {
      const response = await api.get('/api/auth/verify');
      return response.status === 200;
    } catch (error) {
      return false;
    }
  }
};

export default authService;
