import React from 'react';
import { render, screen } from '@testing-library/react';
import Card from '../../../components/ui/Card';

describe('Card Component', () => {
  it('renders with children', () => {
    render(
      <Card>
        <div>Card content</div>
      </Card>
    );
    
    expect(screen.getByText('Card content')).toBeInTheDocument();
  });

  it('applies default classes', () => {
    render(
      <Card>
        <div>Content</div>
      </Card>
    );
    
    const card = screen.getByText('Content').parentElement;
    expect(card).toHaveClass('card', 'p-6');
  });

  it('applies custom className', () => {
    render(
      <Card className="custom-class">
        <div>Content</div>
      </Card>
    );
    
    const card = screen.getByText('Content').parentElement;
    expect(card).toHaveClass('custom-class');
  });

  it('applies hover classes when hover prop is true', () => {
    render(
      <Card hover>
        <div>Content</div>
      </Card>
    );
    
    const card = screen.getByText('Content').parentElement;
    expect(card).toHaveClass('hover:shadow-2xl', 'hover:scale-105');
  });

  it('does not apply hover classes when hover prop is false', () => {
    render(
      <Card hover={false}>
        <div>Content</div>
      </Card>
    );
    
    const card = screen.getByText('Content').parentElement;
    expect(card).not.toHaveClass('hover:shadow-2xl', 'hover:scale-105');
  });

  it('renders multiple children', () => {
    render(
      <Card>
        <h1>Title</h1>
        <p>Description</p>
        <button>Action</button>
      </Card>
    );
    
    expect(screen.getByText('Title')).toBeInTheDocument();
    expect(screen.getByText('Description')).toBeInTheDocument();
    expect(screen.getByText('Action')).toBeInTheDocument();
  });
});
