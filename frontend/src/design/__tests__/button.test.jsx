import React from 'react';
import { render, screen } from '@testing-library/react';
import setupUser from '../testing/setupUser';
import Button, { IconButton } from '../components/Button';

describe('Button', () => {
  test('renders a button that fires onClick', async () => {
    const user = setupUser();
    const onClick = jest.fn();
    render(
      <Button variant="primary" icon="send" onClick={onClick}>
        Send
      </Button>
    );
    const btn = screen.getByRole('button', { name: 'Send' });
    expect(btn).toHaveClass('sr-btn', 'sr-btn--primary', 'sr-btn--md');
    expect(btn).toHaveAttribute('type', 'button');
    await user.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  test('loading blocks clicks and form submit, keeps focus, and is announced', async () => {
    const user = setupUser();
    const onClick = jest.fn();
    const onSubmit = jest.fn((e) => e.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <Button type="submit" loading onClick={onClick} loadingLabel="Saving">
          Save
        </Button>
      </form>
    );
    const btn = screen.getByRole('button', { name: /Saving/ });
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(btn).toHaveAttribute('aria-disabled', 'true');
    expect(btn).not.toBeDisabled();
    await user.click(btn);
    expect(onClick).not.toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test('disabled button does not fire', async () => {
    const user = setupUser();
    const onClick = jest.fn();
    render(
      <Button disabled onClick={onClick}>
        Nope
      </Button>
    );
    await user.click(screen.getByRole('button', { name: 'Nope' }));
    expect(onClick).not.toHaveBeenCalled();
  });

  test('IconButton uses its label as the accessible name and shows a tooltip on focus', async () => {
    const user = setupUser();
    render(<IconButton icon="settings" label="Settings" />);
    const btn = screen.getByRole('button', { name: 'Settings' });
    await user.tab();
    expect(btn).toHaveFocus();
    expect(screen.getByRole('tooltip', { hidden: true })).toHaveClass('is-open');
    await user.keyboard('{Escape}');
    expect(screen.getByRole('tooltip', { hidden: true })).not.toHaveClass('is-open');
  });
});
