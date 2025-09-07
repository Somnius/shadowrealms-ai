import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import Input from '../../../components/ui/Input';

describe('Input Component', () => {
  it('renders with default props', () => {
    render(<Input placeholder="Enter text" />);
    
    const input = screen.getByPlaceholderText('Enter text');
    expect(input).toBeInTheDocument();
    expect(input).toHaveClass('input-field');
  });

  it('renders with label', () => {
    render(<Input label="Username" placeholder="Enter username" />);
    
    expect(screen.getByText('Username')).toBeInTheDocument();
    const input = screen.getByPlaceholderText('Enter username');
    expect(input).toBeInTheDocument();
  });

  it('renders with error message', () => {
    render(<Input error="This field is required" placeholder="Enter text" />);
    
    expect(screen.getByText('This field is required')).toBeInTheDocument();
    const input = screen.getByPlaceholderText('Enter text');
    expect(input).toHaveClass('border-red-500');
  });

  it('renders with icon', () => {
    const MockIcon = () => <div data-testid="mock-icon">Icon</div>;
    render(<Input icon={<MockIcon />} placeholder="Enter text" />);
    
    expect(screen.getByTestId('mock-icon')).toBeInTheDocument();
    const input = screen.getByPlaceholderText('Enter text');
    expect(input).toHaveClass('pl-10');
  });

  it('handles input changes', () => {
    const handleChange = jest.fn();
    render(<Input onChange={handleChange} placeholder="Enter text" />);
    
    const input = screen.getByPlaceholderText('Enter text');
    fireEvent.change(input, { target: { value: 'test input' } });
    
    expect(handleChange).toHaveBeenCalledTimes(1);
    expect(input).toHaveValue('test input');
  });

  it('applies custom className', () => {
    render(<Input className="custom-class" placeholder="Enter text" />);
    
    const input = screen.getByPlaceholderText('Enter text');
    expect(input).toHaveClass('custom-class');
  });

  it('passes through other props', () => {
    render(
      <Input 
        name="username" 
        type="email" 
        required 
        placeholder="Enter email" 
      />
    );
    
    const input = screen.getByPlaceholderText('Enter email');
    expect(input).toHaveAttribute('name', 'username');
    expect(input).toHaveAttribute('type', 'email');
    expect(input).toBeRequired();
  });

  it('shows error styling when error is present', () => {
    render(<Input error="Error message" placeholder="Enter text" />);
    
    const input = screen.getByPlaceholderText('Enter text');
    expect(input).toHaveClass('border-red-500', 'focus:ring-red-500');
  });

  it('renders error message with animation', () => {
    render(<Input error="Error message" placeholder="Enter text" />);
    
    const errorMessage = screen.getByText('Error message');
    expect(errorMessage).toBeInTheDocument();
    expect(errorMessage).toHaveClass('text-red-400');
  });
});
