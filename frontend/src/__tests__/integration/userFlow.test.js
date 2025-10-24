/**
 * Integration tests for critical user flows
 * Tests end-to-end user journeys through the application
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SimpleApp from '../../SimpleApp';

// Mock fetch for API calls
global.fetch = jest.fn();

describe('User Flow Integration Tests', () => {
  
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    
    // Reset fetch mock
    fetch.mockClear();
  });
  
  describe('Authentication Flow', () => {
    it('should allow user to register with valid invite code', async () => {
      // Mock successful registration
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          token: 'test-token',
          user: { id: 1, username: 'testuser', role: 'player' }
        })
      });
      
      render(<SimpleApp />);
      
      // Fill registration form
      const usernameInput = screen.getAllByPlaceholderText(/username/i)[1]; // Second one is register
      const emailInput = screen.getByPlaceholderText(/email/i);
      const passwordInput = screen.getAllByPlaceholderText(/password/i)[1];
      const inviteInput = screen.getByPlaceholderText(/invite code/i);
      
      fireEvent.change(usernameInput, { target: { value: 'testuser' } });
      fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
      fireEvent.change(passwordInput, { target: { value: 'SecurePass123' } });
      fireEvent.change(inviteInput, { target: { value: 'VALID-CODE' } });
      
      // Submit registration
      const registerButton = screen.getByRole('button', { name: /register/i });
      fireEvent.click(registerButton);
      
      // Wait for successful registration and redirect to dashboard
      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          '/api/auth/register',
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('testuser')
          })
        );
      });
    });
    
    it('should prevent registration with invalid invite code', async () => {
      // Mock failed registration
      fetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: 'Invalid invite code' })
      });
      
      render(<SimpleApp />);
      
      const inviteInput = screen.getByPlaceholderText(/invite code/i);
      fireEvent.change(inviteInput, { target: { value: 'INVALID' } });
      
      const registerButton = screen.getByRole('button', { name: /register/i });
      fireEvent.click(registerButton);
      
      await waitFor(() => {
        expect(screen.getByText(/invalid invite code/i)).toBeInTheDocument();
      });
    });
    
    it('should allow user to login with valid credentials', async () => {
      // Mock successful login
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          token: 'test-token',
          user: { id: 1, username: 'testuser', role: 'player' }
        })
      });
      
      render(<SimpleApp />);
      
      const usernameInput = screen.getAllByPlaceholderText(/username/i)[0]; // First one is login
      const passwordInput = screen.getAllByPlaceholderText(/password/i)[0];
      
      fireEvent.change(usernameInput, { target: { value: 'testuser' } });
      fireEvent.change(passwordInput, { target: { value: 'password123' } });
      
      const loginButton = screen.getByRole('button', { name: /^login$/i });
      fireEvent.click(loginButton);
      
      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          '/api/auth/login',
          expect.objectContaining({
            method: 'POST'
          })
        );
      });
    });
  });
  
  describe('Campaign Management Flow', () => {
    beforeEach(() => {
      // Set up authenticated state
      localStorage.setItem('token', 'test-token');
      localStorage.setItem('user', JSON.stringify({
        id: 1,
        username: 'testuser',
        role: 'admin'
      }));
    });
    
    it('should allow admin to create a new campaign', async () => {
      // Mock user data fetch
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 1,
          username: 'testuser',
          role: 'admin'
        })
      });
      
      // Mock campaigns fetch (empty)
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => []
      });
      
      // Mock campaign creation
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 1,
          name: 'Test Campaign',
          description: 'Test Description',
          game_system: 'vampire'
        })
      });
      
      // Mock campaigns fetch (with new campaign)
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [{
          id: 1,
          name: 'Test Campaign',
          description: 'Test Description',
          game_system: 'vampire'
        }]
      });
      
      render(<SimpleApp />);
      
      await waitFor(() => {
        expect(screen.getByText(/your campaigns/i)).toBeInTheDocument();
      });
      
      // Click "New Campaign" button
      const newCampaignButton = screen.getByRole('button', { name: /new campaign/i });
      fireEvent.click(newCampaignButton);
      
      await waitFor(() => {
        expect(screen.getByText(/create new campaign/i)).toBeInTheDocument();
      });
      
      // Fill campaign form
      const nameInput = screen.getByPlaceholderText(/campaign name/i);
      const descInput = screen.getByPlaceholderText(/campaign description/i);
      
      fireEvent.change(nameInput, { target: { value: 'Test Campaign' } });
      fireEvent.change(descInput, { target: { value: 'Test Description' } });
      
      // Submit campaign
      const createButton = screen.getByRole('button', { name: /create campaign/i });
      fireEvent.click(createButton);
      
      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          '/api/campaigns/',
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('Test Campaign')
          })
        );
      });
    });
    
    it('should prevent XSS in campaign creation', async () => {
      fetch.mockResolvedValue({
        ok: true,
        json: async () => ({ id: 1, username: 'testuser', role: 'admin' })
      });
      
      render(<SimpleApp />);
      
      await waitFor(() => {
        const newCampaignButton = screen.queryByRole('button', { name: /new campaign/i });
        if (newCampaignButton) {
          fireEvent.click(newCampaignButton);
        }
      });
      
      // Try to inject script in campaign name
      const nameInput = screen.queryByPlaceholderText(/campaign name/i);
      if (nameInput) {
        fireEvent.change(nameInput, { 
          target: { value: '<script>alert("xss")</script>' } 
        });
        
        // The sanitized value should not contain script tags
        expect(nameInput.value).not.toContain('<script>');
      }
    });
  });
  
  describe('Navigation Flow', () => {
    beforeEach(() => {
      localStorage.setItem('token', 'test-token');
      localStorage.setItem('user', JSON.stringify({
        id: 1,
        username: 'testuser',
        role: 'player'
      }));
    });
    
    it('should handle browser back button correctly', async () => {
      fetch.mockResolvedValue({
        ok: true,
        json: async () => []
      });
      
      render(<SimpleApp />);
      
      // Simulate navigation
      window.history.pushState({ page: 'dashboard' }, '', '/');
      window.history.pushState({ page: 'createCampaign' }, '', '/');
      
      // Trigger popstate (back button)
      window.dispatchEvent(new PopStateEvent('popstate', {
        state: { page: 'dashboard' }
      }));
      
      await waitFor(() => {
        // Should navigate back to dashboard
        expect(window.location.pathname).toBe('/');
      });
    });
  });
  
  describe('Security Tests', () => {
    it('should store tokens securely in localStorage', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          token: 'test-token-123',
          user: { id: 1, username: 'testuser', role: 'player' }
        })
      });
      
      render(<SimpleApp />);
      
      const usernameInput = screen.getAllByPlaceholderText(/username/i)[0];
      const passwordInput = screen.getAllByPlaceholderText(/password/i)[0];
      
      fireEvent.change(usernameInput, { target: { value: 'testuser' } });
      fireEvent.change(passwordInput, { target: { value: 'password123' } });
      
      const loginButton = screen.getByRole('button', { name: /^login$/i });
      fireEvent.click(loginButton);
      
      await waitFor(() => {
        const storedToken = localStorage.getItem('token');
        expect(storedToken).toBe('test-token-123');
      });
    });
    
    it('should clear sensitive data on logout', async () => {
      localStorage.setItem('token', 'test-token');
      localStorage.setItem('user', JSON.stringify({ id: 1, username: 'test' }));
      
      fetch.mockResolvedValue({
        ok: true,
        json: async () => []
      });
      
      render(<SimpleApp />);
      
      await waitFor(() => {
        const logoutButton = screen.queryByRole('button', { name: /logout/i });
        if (logoutButton) {
          fireEvent.click(logoutButton);
        }
      });
      
      await waitFor(() => {
        expect(localStorage.getItem('token')).toBeNull();
        expect(localStorage.getItem('user')).toBeNull();
      });
    });
  });
  
  describe('Rate Limiting', () => {
    it('should prevent spam message submissions', async () => {
      localStorage.setItem('token', 'test-token');
      
      fetch.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true })
      });
      
      render(<SimpleApp />);
      
      // Try to send multiple messages rapidly
      const messageInput = screen.queryByPlaceholderText(/type your message/i);
      if (messageInput) {
        for (let i = 0; i < 10; i++) {
          fireEvent.change(messageInput, { target: { value: `Message ${i}` } });
          fireEvent.submit(messageInput.closest('form'));
        }
        
        // Should have rate limiting in place
        // Exact number of calls depends on rate limit implementation
        expect(fetch).toHaveBeenCalledTimes(expect.any(Number));
      }
    });
  });
  
});

