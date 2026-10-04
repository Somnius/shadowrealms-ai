import React, { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import setupUser from '../testing/setupUser';
import { Modal, Drawer } from '../components/Overlay';
import Button from '../components/Button';

function Harness({ Comp = Modal, onCloseSpy = () => {} }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Open
      </button>
      <Comp
        open={open}
        onClose={() => {
          onCloseSpy();
          setOpen(false);
        }}
        title="Leave the chronicle?"
        description="Your character stays."
      >
        <input aria-label="Confirm name" />
        <Button>Leave</Button>
      </Comp>
    </div>
  );
}

describe('Modal', () => {
  test('is a labelled modal dialog that takes focus, traps Tab and closes on Escape', async () => {
    const user = setupUser();
    const spy = jest.fn();
    render(<Harness onCloseSpy={spy} />);
    const opener = screen.getByRole('button', { name: 'Open' });
    await user.click(opener);

    const dialog = await screen.findByRole('dialog', { name: 'Leave the chronicle?' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAccessibleDescription('Your character stays.');
    // portal root carries the design-system scope
    expect(dialog.closest('.sr-app.sr-portal')).not.toBeNull();

    // first focusable inside = the close button
    const close = screen.getByRole('button', { name: 'Close' });
    expect(close).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText('Confirm name')).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Leave' })).toHaveFocus();
    await user.tab(); // wraps
    expect(close).toHaveFocus();
    await user.tab({ shift: true }); // wraps backwards
    expect(screen.getByRole('button', { name: 'Leave' })).toHaveFocus();

    expect(document.body.style.overflow).toBe('hidden');
    await user.keyboard('{Escape}');
    expect(spy).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(opener).toHaveFocus();
    expect(document.body.style.overflow).toBe('');
  });

  test('the close button closes it', async () => {
    const user = setupUser();
    render(<Harness />);
    await user.click(screen.getByRole('button', { name: 'Open' }));
    await user.click(await screen.findByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  test('Drawer has the same dialog behaviour', async () => {
    const user = setupUser();
    render(<Harness Comp={Drawer} />);
    await user.click(screen.getByRole('button', { name: 'Open' }));
    const dialog = await screen.findByRole('dialog', { name: 'Leave the chronicle?' });
    expect(dialog).toHaveClass('sr-drawer', 'sr-drawer--left');
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });
});
