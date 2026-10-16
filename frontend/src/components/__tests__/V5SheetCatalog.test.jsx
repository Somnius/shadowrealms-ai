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

test('advantages, flaws, loresheet levels and thin-blood entries open to their description', () => {
  render(
    <V5CharacterSheetView
      character={{
        wod_meta: {
          edition: 'v5',
          clan: 'Thin-blood',
          advantages: [
            { id: 'background:allies', name: 'Allies (police)', dots: 2, kind: 'background', note: 'police' },
            { id: 'loresheet:the-bahari', name: 'The Bahari', dots: 3, kind: 'loresheet', levels: [1, 2] },
            { name: 'Homebrew Patron', dots: 1, kind: 'merit', custom: true },
            { id: 'merit:renamed-since', name: 'Beautiful', dots: 2, kind: 'merit' }, // unknown id: by name
          ],
          flaws: [{ name: 'Prey Exclusion (locals)', dots: 1, kind: 'predator' }],
          thin_blood_merits: ['Day Drinker'],
          thin_blood_flaws: ['Clan Curse'],
        },
      }}
    />
  );
  expect(screen.getByText('Allies (police)').tagName).toBe('SUMMARY');
  expect(screen.getByText(/Test text for Allies\./)).toBeInTheDocument();
  expect(screen.getByText('The Bahari').tagName).toBe('SUMMARY');
  expect(screen.getByText('● Dangerous Reputation').tagName).toBe('SUMMARY');
  expect(screen.getByText(/Test level 2 of The Bahari\./)).toBeInTheDocument();
  expect(screen.queryByText(/Sacrifice the Children/)).toBeNull(); // level 3 not taken
  expect(screen.getByText('Homebrew Patron').tagName).toBe('SPAN');
  expect(screen.getByText('Beautiful').tagName).toBe('SUMMARY');
  expect(screen.getByText('Prey Exclusion (locals)').tagName).toBe('SUMMARY'); // an older row: by name
  expect(screen.getByText(/Test text for Day Drinker\./)).toBeInTheDocument();
  expect(screen.getByText(/Test text for Clan Curse\./)).toBeInTheDocument(); // the thin-blood one
  expect(screen.queryByText(/Caitiff Clan Curse/)).toBeNull();
});

test('a loresheet whose facts come from the wiki credits it', () => {
  applyV5Catalog({
    ...fixture,
    loresheets: [
      ...fixture.loresheets,
      { id: 'loresheet:salvador-garcia', name: 'Salvador Garcia', book: 'v5-anarch', page: 190, source: 'online', desc: { en: 'Ties to an Anarch.' }, levels: [1, 2, 3, 4, 5].map((dots) => ({ dots, name: null })) },
    ],
  });
  try {
    render(
      <V5CharacterSheetView
        character={{
          wod_meta: {
            edition: 'v5',
            advantages: [
              { id: 'loresheet:salvador-garcia', name: 'Salvador Garcia', dots: 2, kind: 'loresheet', levels: [2] },
              { id: 'loresheet:the-bahari', name: 'The Bahari', dots: 1, kind: 'loresheet', levels: [1] },
            ],
          },
        }}
      />
    );
    expect(screen.getByText('Salvador Garcia').tagName).toBe('SUMMARY');
    expect(screen.getByText('●● Level 2')).toBeInTheDocument();
    expect(screen.getAllByText('· facts from vtm.paradoxwikis.com (CC BY-SA)')).toHaveLength(1); // not on The Bahari
  } finally {
    applyV5Catalog(fixture);
  }
});
