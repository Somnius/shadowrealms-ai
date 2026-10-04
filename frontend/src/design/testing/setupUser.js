/**
 * Test helper: a user-event 14 instance. @testing-library/react 16 shares the one
 * @testing-library/dom with user-event and wraps its events in act() itself, so nothing else
 * is needed here any more; the helper stays so the tests don't change. Only imported by tests.
 */
import userEvent from '@testing-library/user-event';

export default function setupUser(options) {
  return userEvent.setup(options);
}
