/**
 * Test helper: user-event 14 resolves the top-level @testing-library/dom (v10) while
 * @testing-library/react 13 bundles its own dom v8, so user-event's events aren't wrapped in
 * act() and React prints "not wrapped in act(...)" warnings. Point the v10 config at RTL's act.
 * Only imported by tests.
 */
import { configure } from '@testing-library/dom';
import { act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

let configured = false;

export default function setupUser(options) {
  if (!configured) {
    configure({
      eventWrapper: (cb) => {
        let result;
        act(() => {
          result = cb();
        });
        return result;
      },
      asyncWrapper: async (cb) => {
        const previous = global.IS_REACT_ACT_ENVIRONMENT;
        global.IS_REACT_ACT_ENVIRONMENT = false;
        try {
          return await cb();
        } finally {
          global.IS_REACT_ACT_ENVIRONMENT = previous;
        }
      },
    });
    configured = true;
  }
  return userEvent.setup(options);
}
