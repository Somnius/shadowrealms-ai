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

test('marks dots and specialties bought with starting XP', () => {
  const { container } = render(
    <V5CharacterSheetView
      character={{
        ...character({
          disciplines: [{ name: 'Auspex', level: 1, powers: [] }],
          experience: {
            total: 15,
            spent: 13,
            unspent: 2,
            log: [
              { kind: 'attribute', trait: 'resolve', what: 'Resolve', from: 1, to: 2, cost: 10 },
              { kind: 'specialty', trait: 'Stocks', skill: 'finance', what: 'Finance specialty: Stocks', from: 0, to: 1, cost: 3 },
            ],
          },
        }),
        skills: { mental: { finance: 1 }, specialties: [{ skill: 'finance', name: 'Stocks', source: 'xp' }] },
      }}
    />
  );
  expect(screen.getByText('13 of 15 spent at creation · 2 unspent')).toBeInTheDocument();
  expect(container.querySelectorAll('[data-xp-dots]')).toHaveLength(1);
  expect(screen.getByText('Resolve').parentElement).toHaveTextContent('Resolve +1 XP');
  expect(screen.getByText('(Stocks – XP)')).toBeInTheDocument();
});
