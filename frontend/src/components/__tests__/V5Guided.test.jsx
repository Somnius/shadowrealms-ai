import { act, fireEvent, render, screen, within } from '@testing-library/react';
import CharacterCreationWizard from '../CharacterCreationWizard';
import fixture from '../../rules/__fixtures__/v5-catalog.json';
import { applyV5Catalog } from '../../characterSheet/v5/rulesData';
import { setLanguage } from '../../i18n';

// A small question set of our own, so the tests don't depend on the content in docs/ (Mario's).
const SET = {
  version: 1,
  author: 'test',
  thresholds: { min_score_share: 0.3, min_lead: 2 },
  questions: [
    {
      id: 'night',
      text: { en: 'Where do you spend the night?', el: 'Πού περνάς τη νύχτα;' },
      options: [
        {
          id: 'hospice',
          text: { en: 'At a hospice.', el: 'Σε έναν ξενώνα.' },
          weights: {
            clan: { Hecata: 3 },
            predator: { 'Grim Reaper': 2 },
            attributes: { mental: 2, resolve: 1 },
            skills: { medicine: 2, occult: 1 },
            distribution: { specialist: 1 },
          },
        },
        { id: 'court', text: { en: 'At court.', el: 'Στην αυλή.' }, weights: { clan: { Ventrue: 3 }, predator: { Osiris: 1 } } },
      ],
    },
    {
      id: 'fear',
      text: { en: 'What do you fear?', el: 'Τι φοβάσαι;' },
      options: [
        { id: 'dead', text: { en: 'The dead.', el: 'Τους νεκρούς.' }, weights: { clan: { Hecata: 3 }, skills: { occult: 2 } } },
        { id: 'rivals', text: { en: 'My rivals.', el: 'Τους αντιπάλους μου.' }, weights: { clan: { Ventrue: 2, Caitiff: 1 } } },
      ],
    },
    {
      id: 'road',
      text: { en: 'Do you stay or go?', el: 'Μένεις ή φεύγεις;' },
      options: [
        { id: 'stay', text: { en: 'I stay.', el: 'Μένω.' }, weights: { clan: { Hecata: 1 }, predator: { 'Grim Reaper': 1 } } },
        { id: 'drive', text: { en: 'I drive away.', el: 'Φεύγω.' }, weights: { clan: { Caitiff: 1 }, predator: { 'Roadside Killer': 2 } } },
      ],
    },
  ],
};

const respond = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
let guided;

beforeAll(() => applyV5Catalog(fixture));
afterAll(() => applyV5Catalog(null));

beforeEach(() => {
  guided = respond(200, SET);
  global.fetch = jest.fn(async (url) => (String(url) === '/api/rules/v5/guided' ? guided : respond(404, { error: 'not found' })));
});

afterEach(async () => {
  await act(() => setLanguage('en', { remember: false, save: false }));
});

const campaigns = (creation_settings) => [{ id: 2, name: 'Blood', game_system: 'vampire', rules_edition: 'v5', creation_settings }];

function renderEntry(creation_settings) {
  render(<CharacterCreationWizard token="x" campaigns={campaigns(creation_settings)} onCancel={() => {}} />);
}

async function startGuide() {
  fireEvent.click(screen.getByRole('button', { name: 'Guided' }));
  return screen.findByRole('heading', { name: 'Where do you spend the night?' });
}

/** Pick an answer on the current screen and go on. */
function answer(label) {
  fireEvent.click(screen.getByRole('radio', { name: label }));
  fireEvent.click(screen.getByRole('button', { name: /^(Next|See the suggestion)$/ }));
}

test('the V5 forge starts with a choice: Guided or the full forge', () => {
  renderEntry();
  expect(screen.getByText('How do you want to start?')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Guided' })).toHaveAccessibleDescription(/suggests a clan and a predator type/);
  fireEvent.click(screen.getByRole('button', { name: 'Full forge' }));
  expect(screen.getByLabelText('Character name')).toBeInTheDocument();
  expect(screen.queryByRole('note', { name: 'Suggested by the guide' })).toBeNull();
  expect(screen.getByRole('heading', { name: 'Character sheet forge · V5' })).toHaveFocus();
});

test('happy path: one question per screen, back keeps the answer, the suggestion lands in the forge', async () => {
  renderEntry();
  const first = await startGuide();
  expect(first).toHaveFocus();
  expect(screen.getByText('Question 1 of 3')).toBeInTheDocument();
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '1');
  const group = screen.getByRole('radiogroup', { name: 'Where do you spend the night?' });
  expect(within(group).getAllByRole('radio').map((r) => r.labels[0].textContent)).toEqual(['At a hospice.', 'At court.', 'None of these']);
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();

  answer('At a hospice.');
  expect(screen.getByRole('heading', { name: 'What do you fear?' })).toHaveFocus();
  answer('The dead.');
  // back to the second question: the answer is still there
  fireEvent.click(screen.getByRole('button', { name: 'Back' }));
  expect(screen.getByRole('heading', { name: 'What do you fear?' })).toHaveFocus();
  expect(screen.getByRole('radio', { name: 'The dead.' })).toBeChecked();
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(screen.getByText('Question 3 of 3')).toBeInTheDocument();
  answer('I stay.');

  const result = screen.getByRole('region', { name: 'The guide suggests' });
  expect(screen.getByRole('heading', { name: 'The guide suggests' })).toHaveFocus();
  expect(result).toHaveTextContent('Hecata');
  expect(result).toHaveTextContent('Test clan text. (Players Guide, p. 25)'); // the catalog description and page
  expect(result).toHaveTextContent('Grim Reaper');
  expect(result).toHaveTextContent('(Players Guide, p. 108)');
  expect(within(result).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
    '“At a hospice.”',
    '“The dead.”',
    '“I stay.”',
    '“At a hospice.”',
    '“I stay.”',
  ]);
  expect(result).toHaveTextContent('Attributes: Mental first, then Physical, then Social; Resolve starts at 4.');
  expect(result).toHaveTextContent('Skills: Specialist, built around Occult and Medicine.');

  fireEvent.click(screen.getByRole('button', { name: 'Build this character' }));
  expect(document.getElementById('v5-field-clan')).toHaveValue('Hecata');
  expect(document.getElementById('v5-field-predator')).toHaveValue('Grim Reaper');
  expect(document.getElementById('v5-field-distribution')).toHaveValue('specialist');
  expect(screen.getByRole('note', { name: 'Suggested by the guide' })).toHaveTextContent('Hecata · Grim Reaper');
  expect(screen.getByRole('group', { name: 'Resolve: 4 of 4' })).toBeInTheDocument();
  expect(screen.getByRole('group', { name: 'Composure: 1 of 4' })).toBeInTheDocument();
  expect(screen.getByRole('group', { name: 'Occult: 4 of 4' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Character sheet forge · V5' })).toHaveFocus();
});

test('"none of these" twice leaves the path at once and offers the full forge', async () => {
  renderEntry();
  await startGuide();
  answer('None of these');
  expect(screen.getByText('Question 2 of 3')).toBeInTheDocument();
  answer('None of these');
  const panel = screen.getByRole('region', { name: 'This path doesn’t fit' });
  expect(screen.getByRole('heading', { name: 'This path doesn’t fit' })).toHaveFocus();
  expect(panel).toHaveTextContent('You picked “None of these” twice');
  fireEvent.click(within(panel).getByRole('button', { name: 'Open the full forge' }));
  expect(screen.getByLabelText('Character name')).toBeInTheDocument();
  expect(screen.queryByRole('note', { name: 'Suggested by the guide' })).toBeNull();
});

test('answers that point nowhere in particular are off the path; the answers can still be changed', async () => {
  renderEntry();
  await startGuide();
  answer('At court.'); // Ventrue 3
  answer('The dead.'); // Hecata 3
  answer('I drive away.'); // Caitiff 1: no clan leads
  expect(screen.getByRole('region', { name: 'This path doesn’t fit' })).toHaveTextContent('Your answers point in several directions');
  fireEvent.click(screen.getByRole('button', { name: 'Change my answers' }));
  expect(screen.getByRole('heading', { name: 'Do you stay or go?' })).toHaveFocus();
  expect(screen.getByRole('radio', { name: 'I drive away.' })).toBeChecked();
});

test("a clan the Storyteller doesn't allow ends the path with that reason", async () => {
  renderEntry({ allowed_clans: ['Ventrue', 'Caitiff'] });
  await startGuide();
  answer('At a hospice.');
  answer('The dead.');
  answer('I stay.');
  expect(screen.getByRole('region', { name: 'This path doesn’t fit' })).toHaveTextContent('a clan this chronicle doesn’t offer');
});

test('Back on the first question returns to the choice', async () => {
  renderEntry();
  await startGuide();
  fireEvent.click(screen.getByRole('button', { name: 'Back' }));
  expect(screen.getByText('How do you want to start?')).toHaveFocus();
});

test('without the questions the guide says so and offers the full forge', async () => {
  guided = respond(404, { error: 'The guided questions are not installed' });
  renderEntry();
  fireEvent.click(screen.getByRole('button', { name: 'Guided' }));
  expect(await screen.findByRole('heading', { name: 'The guide is not available' })).toHaveFocus();
  fireEvent.click(screen.getByRole('button', { name: 'Open the full forge' }));
  expect(screen.getByLabelText('Character name')).toBeInTheDocument();
});

test('the guide speaks Greek; the game terms and names stay English', async () => {
  await act(() => setLanguage('el', { remember: false, save: false }));
  renderEntry();
  expect(screen.getByText('Πώς θέλεις να ξεκινήσεις;')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Με οδηγό' }));
  expect(await screen.findByRole('heading', { name: 'Πού περνάς τη νύχτα;' })).toHaveFocus();
  expect(screen.getByText('Ερώτηση 1 από 3')).toBeInTheDocument();
  ['Σε έναν ξενώνα.', 'Τους νεκρούς.', 'Μένω.'].forEach((label) => {
    fireEvent.click(screen.getByRole('radio', { name: label }));
    fireEvent.click(screen.getByRole('button', { name: /^(Επόμενη|Δες την πρόταση)$/ }));
  });
  const result = screen.getByRole('region', { name: 'Ο οδηγός προτείνει' });
  expect(result).toHaveTextContent('Hecata');
  expect(result).toHaveTextContent('Κείμενο δοκιμής.');
  expect(result).toHaveTextContent('«Σε έναν ξενώνα.»');
  fireEvent.click(screen.getByRole('button', { name: 'Φτιάξε αυτόν τον χαρακτήρα' }));
  expect(screen.getByRole('note', { name: 'Πρόταση του οδηγού' })).toHaveTextContent('Hecata · Grim Reaper');
});
