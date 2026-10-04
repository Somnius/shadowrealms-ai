import { render, screen, waitFor, act } from '@testing-library/react';
import setupUser from '../testing/setupUser';
import { DesignProvider, MotionToggle, useMotionPreference } from '../motion';
import { ToastProvider, useToast } from '../components/Overlay';

function mockMatchMedia(reduce) {
  const original = window.matchMedia;
  window.matchMedia = (query) => ({
    matches: reduce && query.includes('reduce'),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  });
  return () => {
    window.matchMedia = original;
  };
}

beforeEach(() => {
  window.localStorage.clear();
});

test('DesignProvider renders the opt-in root with data-motion / data-line / lang', () => {
  const { container } = render(
    <DesignProvider line="werewolf" lang="el">
      <p>x</p>
    </DesignProvider>
  );
  const root = container.firstChild;
  expect(root).toHaveClass('sr-app');
  expect(root).toHaveAttribute('data-motion', 'full');
  expect(root).toHaveAttribute('data-line', 'werewolf');
  expect(root).toHaveAttribute('lang', 'el');
});

test('the OS reduced-motion setting is respected', () => {
  const restore = mockMatchMedia(true);
  const { container } = render(<DesignProvider>x</DesignProvider>);
  expect(container.firstChild).toHaveAttribute('data-motion', 'reduced');
  restore();
});

test('the manual toggle reduces motion and is remembered', async () => {
  const user = setupUser();
  function Probe() {
    const { reduced } = useMotionPreference();
    return <span data-testid="probe">{String(reduced)}</span>;
  }
  const { container } = render(
    <DesignProvider>
      <MotionToggle />
      <Probe />
    </DesignProvider>
  );
  const sw = screen.getByRole('switch', { name: 'Reduce motion' });
  expect(sw).toHaveAttribute('aria-checked', 'false');
  await user.click(sw);
  expect(sw).toHaveAttribute('aria-checked', 'true');
  expect(container.firstChild).toHaveAttribute('data-motion', 'reduced');
  expect(screen.getByTestId('probe')).toHaveTextContent('true');
  expect(window.localStorage.getItem('sr_motion')).toBe('reduced');
});

test('toasts announce politely, errors assertively, and can be dismissed', async () => {
  const user = setupUser();
  let api;
  function Grab() {
    api = useToast();
    return null;
  }
  render(
    <ToastProvider>
      <Grab />
    </ToastProvider>
  );
  act(() => {
    api.toast({ title: 'The raven arrives', duration: 0 });
    api.toast({ title: 'Connection lost', tone: 'danger', duration: 0 });
  });
  expect(screen.getByRole('region', { name: 'Notifications' })).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('The raven arrives');
  expect(screen.getByRole('alert')).toHaveTextContent('Connection lost');
  await user.click(screen.getAllByRole('button', { name: 'Dismiss' })[0]);
  await waitFor(() => expect(screen.queryByText('The raven arrives')).toBeNull());
});

test('toasts auto-dismiss after their duration', () => {
  jest.useFakeTimers();
  let api;
  function Grab() {
    api = useToast();
    return null;
  }
  render(
    <DesignProvider motion="reduced">
      <ToastProvider>
        <Grab />
      </ToastProvider>
    </DesignProvider>
  );
  act(() => {
    api.toast({ title: 'Brief', duration: 1000 });
  });
  expect(screen.getByText('Brief')).toBeInTheDocument();
  act(() => {
    jest.advanceTimersByTime(1100);
  });
  act(() => {
    jest.runOnlyPendingTimers();
  });
  jest.useRealTimers();
  return waitFor(() => expect(screen.queryByText('Brief')).toBeNull());
});
