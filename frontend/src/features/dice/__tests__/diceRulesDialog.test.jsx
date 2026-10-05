import { act, fireEvent, render, screen } from '@testing-library/react';
import { DesignProvider } from '../../../design';
import { DiceRulesDialog } from '../DiceDialogs';

function open(campaign, location) {
  const api = jest.fn().mockResolvedValue({ ok: true, data: {} });
  const toast = jest.fn();
  render(
    <DesignProvider>
      <DiceRulesDialog open onClose={() => {}} api={api} campaign={campaign} location={location} onSaved={() => {}} toast={toast} />
    </DesignProvider>
  );
  return { api, toast };
}

test('V5 room: switches instead of the floor, sent as dice_leniency_v5', async () => {
  const { api } = open(
    { id: 3, rules_edition: 'v5', game_system: 'vampire' },
    { id: 4, name: 'Elysium', dice_leniency_v5: { no_bestial: false, no_messy: true, min_successes: 0 } }
  );
  expect(screen.queryByLabelText(/Leniency floor/)).toBeNull();
  expect(screen.getByLabelText(/No messy critical/)).toBeChecked();
  fireEvent.click(screen.getByLabelText(/No bestial failure/));
  fireEvent.change(screen.getByLabelText(/At least this many dice/), { target: { value: '2' } });
  await act(async () => fireEvent.click(screen.getByText('Save')));
  expect(api).toHaveBeenCalledWith('/campaigns/3/locations/4/dice-leniency', {
    method: 'PUT',
    body: { dice_leniency_v5: { no_bestial: true, no_messy: true, min_successes: 2 } },
  });
});

test('Classic room keeps the floor', async () => {
  const { api } = open({ id: 3, rules_edition: 'classic' }, { id: 4, name: 'Bar', dice_leniency_floor: 7 });
  expect(screen.queryByLabelText(/No bestial failure/)).toBeNull();
  expect(screen.getByLabelText(/Leniency floor/)).toHaveValue(7);
  await act(async () => fireEvent.click(screen.getByText('Save')));
  expect(api).toHaveBeenCalledWith('/campaigns/3/locations/4/dice-leniency', { method: 'PUT', body: { dice_leniency_floor: 7 } });
});
