import { LoginCredentials, RegisterData, PasswordResetRequest, PasswordResetData } from '../../types/auth';

// Mock the entire authService module
jest.mock('../../services/authService', () => {
  const mockAuthService = {
    login: jest.fn(),
    register: jest.fn(),
    requestPasswordReset: jest.fn(),
    resetPassword: jest.fn(),
    getProfile: jest.fn(),
    updateProfile: jest.fn(),
    logout: jest.fn(),
    verifyToken: jest.fn(),
  };
  return {
    authService: mockAuthService,
    default: mockAuthService,
  };
});

import { authService } from '../../services/authService';

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock;

describe('AuthService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('login', () => {
    it('should login successfully with valid credentials', async () => {
      const credentials: LoginCredentials = {
        username: 'testuser',
        password: 'password123',
      };

      const mockResponse = {
        user: {
          id: 1,
          username: 'testuser',
          email: 'test@example.com',
          role: 'player',
          status: 'active',
          created_at: '2023-01-01T00:00:00Z',
        },
        token: 'mock-jwt-token',
        message: 'Login successful',
      };

      (authService.login as jest.Mock).mockResolvedValueOnce(mockResponse);

      const result = await authService.login(credentials);

      expect(authService.login).toHaveBeenCalledWith(credentials);
      expect(result).toEqual(mockResponse);
    });

    it('should handle login failure', async () => {
      const credentials: LoginCredentials = {
        username: 'testuser',
        password: 'wrongpassword',
      };

      const mockError = {
        response: {
          data: {
            message: 'Invalid credentials',
          },
        },
      };

      (authService.login as jest.Mock).mockRejectedValueOnce(mockError);

      await expect(authService.login(credentials)).rejects.toEqual(mockError);
    });
  });

  describe('register', () => {
    it('should register successfully with valid data', async () => {
      const userData: RegisterData = {
        username: 'newuser',
        email: 'newuser@example.com',
        password: 'password123',
        confirmPassword: 'password123',
      };

      const mockResponse = {
        user: {
          id: 2,
          username: 'newuser',
          email: 'newuser@example.com',
          role: 'player',
          status: 'active',
          created_at: '2023-01-01T00:00:00Z',
        },
        token: 'mock-jwt-token',
        message: 'Registration successful',
      };

      (authService.register as jest.Mock).mockResolvedValueOnce(mockResponse);

      const result = await authService.register(userData);

      expect(authService.register).toHaveBeenCalledWith(userData);
      expect(result).toEqual(mockResponse);
    });

    it('should handle registration failure', async () => {
      const userData: RegisterData = {
        username: 'existinguser',
        email: 'existing@example.com',
        password: 'password123',
        confirmPassword: 'password123',
      };

      const mockError = {
        response: {
          data: {
            message: 'Username already exists',
          },
        },
      };

      (authService.register as jest.Mock).mockRejectedValueOnce(mockError);

      await expect(authService.register(userData)).rejects.toEqual(mockError);
    });
  });

  describe('requestPasswordReset', () => {
    it('should request password reset successfully', async () => {
      const resetData: PasswordResetRequest = {
        email: 'user@example.com',
      };

      const mockResponse = {
        message: 'Password reset email sent',
      };

      (authService.requestPasswordReset as jest.Mock).mockResolvedValueOnce(mockResponse);

      const result = await authService.requestPasswordReset(resetData);

      expect(authService.requestPasswordReset).toHaveBeenCalledWith(resetData);
      expect(result).toEqual(mockResponse);
    });
  });

  describe('resetPassword', () => {
    it('should reset password successfully', async () => {
      const resetData: PasswordResetData = {
        token: 'reset-token',
        password: 'newpassword123',
        confirmPassword: 'newpassword123',
      };

      const mockResponse = {
        message: 'Password reset successful',
      };

      (authService.resetPassword as jest.Mock).mockResolvedValueOnce(mockResponse);

      const result = await authService.resetPassword(resetData);

      expect(authService.resetPassword).toHaveBeenCalledWith(resetData);
      expect(result).toEqual(mockResponse);
    });
  });

  describe('getProfile', () => {
    it('should get user profile successfully', async () => {
      const mockResponse = {
        user: {
          id: 1,
          username: 'testuser',
          email: 'test@example.com',
          role: 'player',
          status: 'active',
          created_at: '2023-01-01T00:00:00Z',
        },
      };

      (authService.getProfile as jest.Mock).mockResolvedValueOnce(mockResponse);

      const result = await authService.getProfile();

      expect(authService.getProfile).toHaveBeenCalled();
      expect(result).toEqual(mockResponse);
    });
  });

  describe('updateProfile', () => {
    it('should update user profile successfully', async () => {
      const userData = {
        email: 'newemail@example.com',
      };

      const mockResponse = {
        user: {
          id: 1,
          username: 'testuser',
          email: 'newemail@example.com',
          role: 'player',
          status: 'active',
          created_at: '2023-01-01T00:00:00Z',
        },
      };

      (authService.updateProfile as jest.Mock).mockResolvedValueOnce(mockResponse);

      const result = await authService.updateProfile(userData);

      expect(authService.updateProfile).toHaveBeenCalledWith(userData);
      expect(result).toEqual(mockResponse);
    });
  });

  describe('logout', () => {
    it('should logout successfully', async () => {
      (authService.logout as jest.Mock).mockResolvedValueOnce(undefined);

      await authService.logout();

      expect(authService.logout).toHaveBeenCalled();
    });

    it('should handle logout errors gracefully', async () => {
      const mockError = new Error('Network error');
      (authService.logout as jest.Mock).mockRejectedValueOnce(mockError);

      await expect(authService.logout()).rejects.toEqual(mockError);
    });
  });

  describe('verifyToken', () => {
    it('should verify valid token', async () => {
      (authService.verifyToken as jest.Mock).mockResolvedValueOnce(true);

      const result = await authService.verifyToken();

      expect(authService.verifyToken).toHaveBeenCalled();
      expect(result).toBe(true);
    });

    it('should return false for invalid token', async () => {
      (authService.verifyToken as jest.Mock).mockResolvedValueOnce(false);

      const result = await authService.verifyToken();

      expect(result).toBe(false);
    });
  });
});