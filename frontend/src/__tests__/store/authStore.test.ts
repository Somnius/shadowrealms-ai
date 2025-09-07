import { renderHook, act } from '@testing-library/react';
import { useAuthStore } from '../../store/authStore';
import { authService } from '../../services/authService';
import { User, LoginCredentials, RegisterData } from '../../types/auth';

// Mock the auth service
jest.mock('../../services/authService');
const mockedAuthService = authService as jest.Mocked<typeof authService>;

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock;

describe('AuthStore', () => {
  const mockUser: User = {
    id: 1,
    username: 'testuser',
    email: 'test@example.com',
    role: 'player',
    status: 'active',
    created_at: '2023-01-01T00:00:00Z',
  };

  const mockToken = 'mock-jwt-token';

  beforeEach(() => {
    jest.clearAllMocks();
    // Reset the store state
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  });

  describe('initial state', () => {
    it('should have correct initial state', () => {
      const { result } = renderHook(() => useAuthStore());
      
      expect(result.current.user).toBeNull();
      expect(result.current.token).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });
  });

  describe('login', () => {
    it('should login successfully', async () => {
      const credentials: LoginCredentials = {
        username: 'testuser',
        password: 'password123',
      };

      mockedAuthService.login.mockResolvedValueOnce({
        user: mockUser,
        token: mockToken,
        message: 'Login successful',
      });

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.login(credentials);
      });

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.token).toBe(mockToken);
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
      // Note: localStorage calls are handled by Zustand persist middleware
      // We focus on testing the store state rather than localStorage interactions
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

      mockedAuthService.login.mockRejectedValueOnce(mockError);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        try {
          await result.current.login(credentials);
        } catch (error) {
          // Expected to throw
        }
      });

      expect(result.current.user).toBeNull();
      expect(result.current.token).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBe('Invalid credentials');
    });

    it('should set loading state during login', async () => {
      const credentials: LoginCredentials = {
        username: 'testuser',
        password: 'password123',
      };

      let resolveLogin: (value: any) => void;
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve;
      });

      mockedAuthService.login.mockReturnValueOnce(loginPromise);

      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.login(credentials);
      });

      expect(result.current.isLoading).toBe(true);

      await act(async () => {
        resolveLogin!({
          user: mockUser,
          token: mockToken,
        });
      });

      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('register', () => {
    it('should register successfully', async () => {
      const userData: RegisterData = {
        username: 'newuser',
        email: 'newuser@example.com',
        password: 'password123',
        confirmPassword: 'password123',
      };

      mockedAuthService.register.mockResolvedValueOnce({
        user: mockUser,
        token: mockToken,
        message: 'Registration successful',
      });

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.register(userData);
      });

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.token).toBe(mockToken);
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
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

      mockedAuthService.register.mockRejectedValueOnce(mockError);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        try {
          await result.current.register(userData);
        } catch (error) {
          // Expected to throw
        }
      });

      expect(result.current.user).toBeNull();
      expect(result.current.token).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBe('Username already exists');
    });
  });

  describe('logout', () => {
    it('should logout successfully', async () => {
      // Set initial authenticated state
      useAuthStore.setState({
        user: mockUser,
        token: mockToken,
        isAuthenticated: true,
      });

      mockedAuthService.logout.mockResolvedValueOnce();

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.token).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('should clear state even if logout fails', async () => {
      // Set initial authenticated state
      useAuthStore.setState({
        user: mockUser,
        token: mockToken,
        isAuthenticated: true,
      });

      mockedAuthService.logout.mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.token).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('updateUser', () => {
    it('should update user data', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.updateUser(mockUser);
      });

      expect(result.current.user).toEqual(mockUser);
      // Note: localStorage calls are handled by Zustand persist middleware
    });
  });

  describe('clearError', () => {
    it('should clear error state', () => {
      // Set initial error state
      useAuthStore.setState({
        error: 'Some error',
      });

      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('checkAuth', () => {
    it('should authenticate user with valid token', async () => {
      localStorageMock.getItem
        .mockReturnValueOnce(mockToken)
        .mockReturnValueOnce(JSON.stringify(mockUser));

      mockedAuthService.verifyToken.mockResolvedValueOnce(true);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.token).toBe(mockToken);
      expect(result.current.isAuthenticated).toBe(true);
    });

    it('should clear state with invalid token', async () => {
      localStorageMock.getItem
        .mockReturnValueOnce(mockToken)
        .mockReturnValueOnce(JSON.stringify(mockUser));

      mockedAuthService.verifyToken.mockResolvedValueOnce(false);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.token).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      // Note: localStorage calls are handled by Zustand persist middleware
    });

    it('should clear state when no token exists', async () => {
      localStorageMock.getItem.mockReturnValue(null);

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.token).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });
  });
});
