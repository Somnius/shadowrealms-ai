import { render, screen } from '@testing-library/react';
import V5CharacterSheetView from '../V5CharacterSheetView';

const character = (wodMeta) => ({
  name: 'Ada',
  system_type: 'vampire',
  attributes: { stamina: 2, composure: 2, resolve: 2 },
  skills: {},
  wod_meta: { edition: 'v5', clan: 'Tremere', ...wodMeta },
});

test('renders rituals with their level and source', () => {
  render(
    <V5CharacterSheetView
      character={character({
        disciplines: [{ name: 'Blood Sorcery', level: 3, powers: [] }],
        rituals: [
          { name: 'Ward against Ghouls', level: 1, source: 'creation' },
          { name: 'Communicate with Kindred Sire', level: 1, source: 'xp' },
        ],
      })}
    />
  );
  expect(screen.getByText('Rituals')).toBeInTheDocument();
  expect(screen.getByText('Ward against Ghouls')).toBeInTheDocument();
  expect(screen.getByText('Communicate with Kindred Sire')).toBeInTheDocument();
  expect(screen.getByText('Level 1 · bought with XP')).toBeInTheDocument();
});

test('no rituals block without rituals', () => {
  render(<V5CharacterSheetView character={character({})} />);
  expect(screen.queryByText('Rituals')).toBeNull();
});
