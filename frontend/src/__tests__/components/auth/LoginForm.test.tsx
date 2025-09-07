import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LoginForm from '../../../components/auth/LoginForm';
import { useAuthStore } from '../../../store/authStore';

// Mock the auth store
jest.mock('../../../store/authStore');
const mockedUseAuthStore = useAuthStore as jest.MockedFunction<typeof useAuthStore>;

// Mock the store methods
const mockLogin = jest.fn();
const mockClearError = jest.fn();

describe('LoginForm Component', () => {
  const mockProps = {
    onSwitchToRegister: jest.fn(),
    onSwitchToPasswordReset: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseAuthStore.mockReturnValue({
      login: mockLogin,
      clearError: mockClearError,
      isLoading: false,
      error: null,
      user: null,
      token: null,
      isAuthenticated: false,
      register: jest.fn(),
      logout: jest.fn(),
      updateUser: jest.fn(),
      checkAuth: jest.fn(),
    });
  });

  it('renders login form correctly', () => {
    render(<LoginForm {...mockProps} />);
    
    expect(screen.getByText('Welcome Back')).toBeInTheDocument();
    expect(screen.getByText('Sign in to your ShadowRealms AI account')).toBeInTheDocument();
    expect(screen.getByLabelText('Username')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('handles form input changes', async () => {
    const user = userEvent.setup();
    render(<LoginForm {...mockProps} />);
    
    const usernameInput = screen.getByPlaceholderText('Enter your username');
    const passwordInput = screen.getByPlaceholderText('Enter your password');
    
    await user.type(usernameInput, 'testuser');
    await user.type(passwordInput, 'password123');
    
    expect(usernameInput).toHaveValue('testuser');
    expect(passwordInput).toHaveValue('password123');
  });

  it('shows validation errors for empty fields', async () => {
    const user = userEvent.setup();
    render(<LoginForm {...mockProps} />);
    
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    await user.click(submitButton);
    
    expect(screen.getByText('Username is required')).toBeInTheDocument();
    expect(screen.getByText('Password is required')).toBeInTheDocument();
  });

  it('calls login with correct credentials', async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValueOnce(undefined);
    
    render(<LoginForm {...mockProps} />);
    
    const usernameInput = screen.getByPlaceholderText('Enter your username');
    const passwordInput = screen.getByPlaceholderText('Enter your password');
    const submitButton = screen.getByTestId('sign-in-button');
    
    await user.type(usernameInput, 'testuser');
    await user.type(passwordInput, 'password123');
    await user.click(submitButton);
    
    expect(mockLogin).toHaveBeenCalledWith({
      username: 'testuser',
      password: 'password123',
    });
  });

  it('shows loading state during login', async () => {
    const user = userEvent.setup();
    mockedUseAuthStore.mockReturnValue({
      login: mockLogin,
      clearError: mockClearError,
      isLoading: true,
      error: null,
      user: null,
      token: null,
      isAuthenticated: false,
      register: jest.fn(),
      logout: jest.fn(),
      updateUser: jest.fn(),
      checkAuth: jest.fn(),
    });
    
    render(<LoginForm {...mockProps} />);
    
    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(screen.getByTestId('sign-in-button')).toBeDisabled();
  });

  it('displays error message from store', () => {
    mockedUseAuthStore.mockReturnValue({
      login: mockLogin,
      clearError: mockClearError,
      isLoading: false,
      error: 'Invalid credentials',
      user: null,
      token: null,
      isAuthenticated: false,
      register: jest.fn(),
      logout: jest.fn(),
      updateUser: jest.fn(),
      checkAuth: jest.fn(),
    });
    
    render(<LoginForm {...mockProps} />);
    
    expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
  });

  it('clears error when user starts typing', async () => {
    const user = userEvent.setup();
    mockedUseAuthStore.mockReturnValue({
      login: mockLogin,
      clearError: mockClearError,
      isLoading: false,
      error: 'Some error',
      user: null,
      token: null,
      isAuthenticated: false,
      register: jest.fn(),
      logout: jest.fn(),
      updateUser: jest.fn(),
      checkAuth: jest.fn(),
    });
    
    render(<LoginForm {...mockProps} />);
    
    const usernameInput = screen.getByPlaceholderText('Enter your username');
    await user.type(usernameInput, 'test');
    
    expect(mockClearError).toHaveBeenCalled();
  });

  it('toggles password visibility', async () => {
    const user = userEvent.setup();
    render(<LoginForm {...mockProps} />);
    
    const passwordInput = screen.getByPlaceholderText('Enter your password');
    const toggleButton = screen.getByTestId('password-toggle');
    
    expect(passwordInput).toHaveAttribute('type', 'password');
    
    await user.click(toggleButton);
    expect(passwordInput).toHaveAttribute('type', 'text');
    
    await user.click(toggleButton);
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  it('calls onSwitchToRegister when register link is clicked', async () => {
    const user = userEvent.setup();
    render(<LoginForm {...mockProps} />);
    
    const registerLink = screen.getByTestId('sign-up-link');
    await user.click(registerLink);
    
    expect(mockProps.onSwitchToRegister).toHaveBeenCalledTimes(1);
  });

  it('calls onSwitchToPasswordReset when forgot password link is clicked', async () => {
    const user = userEvent.setup();
    render(<LoginForm {...mockProps} />);
    
    const forgotPasswordLink = screen.getByTestId('forgot-password-link');
    await user.click(forgotPasswordLink);
    
    expect(mockProps.onSwitchToPasswordReset).toHaveBeenCalledTimes(1);
  });

  it('prevents form submission with invalid data', async () => {
    const user = userEvent.setup();
    render(<LoginForm {...mockProps} />);
    
    const submitButton = screen.getByTestId('sign-in-button');
    await user.click(submitButton);
    
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('handles login failure gracefully', async () => {
    const user = userEvent.setup();
    const loginError = new Error('Login failed');
    mockLogin.mockRejectedValueOnce(loginError);
    
    render(<LoginForm {...mockProps} />);
    
    const usernameInput = screen.getByPlaceholderText('Enter your username');
    const passwordInput = screen.getByPlaceholderText('Enter your password');
    const submitButton = screen.getByTestId('sign-in-button');
    
    await user.type(usernameInput, 'testuser');
    await user.type(passwordInput, 'password123');
    await user.click(submitButton);
    
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalled();
    });
  });
});
