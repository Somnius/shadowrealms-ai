import { render, screen } from '@testing-library/react';
import V5CharacterSheetView from '../V5CharacterSheetView';
import fixture from '../../rules/__fixtures__/v5-catalog.json';
import { applyV5Catalog } from '../../characterSheet/v5/rulesData';

beforeAll(() => applyV5Catalog(fixture));
afterAll(() => applyV5Catalog(null));

test('powers with a catalog description open to show it; ceremonies are marked', () => {
  render(
    <V5CharacterSheetView
      character={{
        wod_meta: {
          edition: 'v5',
          disciplines: [{ name: 'Dominate', level: 2, powers: ['Cloud Memory', 'Homebrew Glare'] }],
          rituals: [{ name: 'Summon Spirit', level: 1, source: 'creation', kind: 'ceremony' }],
        },
      }}
    />
  );
  expect(screen.getByText('Cloud Memory').tagName).toBe('SUMMARY');
  expect(screen.getByText(/Victim forgets the last moments\./)).toBeInTheDocument();
  expect(screen.getByText('Homebrew Glare').tagName).toBe('SPAN'); // not in the catalog: plain text
  expect(screen.getByText(/Ceremony ·/)).toBeInTheDocument();
});
