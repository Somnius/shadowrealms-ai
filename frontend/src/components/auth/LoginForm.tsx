import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { EyeIcon, EyeSlashIcon, UserIcon, LockClosedIcon } from '@heroicons/react/24/outline';
import { useAuthStore } from '../../store/authStore';
import { LoginCredentials } from '../../types/auth';
import Button from '../ui/Button';
import Input from '../ui/Input';
import Card from '../ui/Card';

interface LoginFormProps {
  onSwitchToRegister: () => void;
  onSwitchToPasswordReset: () => void;
}

const LoginForm: React.FC<LoginFormProps> = ({
  onSwitchToRegister,
  onSwitchToPasswordReset,
}) => {
  const [formData, setFormData] = useState<LoginCredentials>({
    username: '',
    password: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Partial<LoginCredentials>>({});
  
  const { login, isLoading, error, clearError } = useAuthStore();

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    
    // Clear error when user starts typing
    if (error) clearError();
    if (errors[name as keyof LoginCredentials]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Partial<LoginCredentials> = {};
    
    if (!formData.username.trim()) {
      newErrors.username = 'Username is required';
    }
    
    if (!formData.password) {
      newErrors.password = 'Password is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) return;
    
    try {
      await login(formData);
    } catch (error) {
      // Error is handled by the store
    }
  };

  return (
    <Card className="w-full max-w-md mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">
            Welcome Back
          </h1>
          <p className="text-dark-400">
            Sign in to your ShadowRealms AI account
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <Input
            label="Username"
            name="username"
            type="text"
            value={formData.username}
            onChange={handleInputChange}
            error={errors.username}
            icon={<UserIcon />}
            placeholder="Enter your username"
            autoComplete="username"
            id="username-input"
          />

          <div className="relative">
            <Input
              label="Password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              value={formData.password}
              onChange={handleInputChange}
              error={errors.password}
              icon={<LockClosedIcon />}
              placeholder="Enter your password"
              autoComplete="current-password"
              id="password-input"
            />
            <button
              type="button"
              className="absolute inset-y-0 right-0 pr-3 flex items-center"
              onClick={() => setShowPassword(!showPassword)}
              data-testid="password-toggle"
            >
              {showPassword ? (
                <EyeSlashIcon className="h-5 w-5 text-dark-400 hover:text-dark-300" />
              ) : (
                <EyeIcon className="h-5 w-5 text-dark-400 hover:text-dark-300" />
              )}
            </button>
          </div>

          {error && (
            <motion.div
              className="bg-red-900/20 border border-red-500/50 rounded-lg p-3"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              <p className="text-red-400 text-sm">{error}</p>
            </motion.div>
          )}

          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={onSwitchToPasswordReset}
              className="text-sm text-primary-400 hover:text-primary-300 transition-colors"
              data-testid="forgot-password-link"
            >
              Forgot password?
            </button>
          </div>

          <Button
            type="submit"
            loading={isLoading}
            className="w-full"
            size="lg"
            data-testid="sign-in-button"
          >
            Sign In
          </Button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-dark-400">
            Don't have an account?{' '}
            <button
              type="button"
              onClick={onSwitchToRegister}
              className="text-primary-400 hover:text-primary-300 font-medium transition-colors"
              data-testid="sign-up-link"
            >
              Sign up
            </button>
          </p>
        </div>
      </motion.div>
    </Card>
  );
};

export default LoginForm;
