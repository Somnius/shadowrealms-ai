import { render, screen, waitFor } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider } from '../../../design';
import { VoiceGenderLine } from '../VoiceGender';

const mockFetch = jest.fn();
beforeEach(() => mockFetch.mockResolvedValue({ ok: true, status: 200, data: {} }));
jest.mock('../../../app/http', () => ({
  apiFetch: (...a) => mockFetch(...a),
  getCurrentToken: () => 'tok',
  errorText: (d, f) => f,
}));

const wrap = (ui) => render(<DesignProvider>{ui}</DesignProvider>);

test('others see the voice read-only; unset reads "Not set"', () => {
  wrap(<VoiceGenderLine character={{ id: 3, gender: null }} owner={false} />);
  expect(screen.getByTestId('voice-gender')).toHaveTextContent('Voice: Not set');
  expect(screen.queryByRole('combobox')).toBeNull();
});

test('the owner gets the reminder and can set it', async () => {
  const user = setupUser();
  wrap(<VoiceGenderLine character={{ id: 3, gender: null }} owner />);
  expect(screen.getByText(/Until then a neutral voice is used/)).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText('Voice'), 'female');
  await waitFor(() => expect(mockFetch).toHaveBeenCalledWith('tok', '/characters/3', { method: 'PUT', body: { gender: 'female' } }));
  expect(screen.queryByText(/Until then/)).toBeNull();
});
