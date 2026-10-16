import { render, screen } from '@testing-library/react';
import { DesignProvider } from '../../../design';
import { ClipChip, VoiceMark } from '../ClipChip';

jest.mock('../../../app/http', () => ({
  API_URL: '/api',
  authFetch: jest.fn(),
  getCurrentToken: () => 'tok',
}));

const wrap = (ui) => render(<DesignProvider>{ui}</DesignProvider>);

test('mic marker for voice and phone dictation, with a spoken name; none for typed lines', () => {
  const { rerender } = wrap(<VoiceMark message={{ source: 'voice' }} />);
  expect(screen.getByRole('img', { name: 'Sent by voice' })).toBeInTheDocument();
  rerender(<DesignProvider><VoiceMark message={{ source: 'phone-voice' }} /></DesignProvider>);
  expect(screen.getByRole('img', { name: 'Dictated on the phone' })).toBeInTheDocument();
  rerender(<DesignProvider><VoiceMark message={{ source: null }} /></DesignProvider>);
  expect(screen.queryByTestId('voice-mark')).toBeNull();
});

test('replay chip: separate play button and seek bar, length from the message; no chip without a clip', () => {
  const { rerender } = wrap(<ClipChip message={{ clip_id: 'a'.repeat(32), clip_ms: 42000 }} />);
  expect(screen.getByRole('button', { name: 'Play the recording' })).toBeInTheDocument();
  expect(screen.getByRole('slider', { name: 'Position in the recording' })).toBeInTheDocument();
  expect(screen.getByTestId('clip-chip')).toHaveTextContent('0:42');
  rerender(<DesignProvider><ClipChip message={{ source: 'phone-voice' }} /></DesignProvider>);
  expect(screen.queryByTestId('clip-chip')).toBeNull();
});
