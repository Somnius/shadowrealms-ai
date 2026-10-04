import React from 'react';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import setupUser from '../../design/testing/setupUser';
import { setLanguage } from '../../i18n';
import LayaPanel from '../admin/LayaPanel';

const ITEMS = [
  {
    id: 3, campaign_id: 8, campaign_name: 'Athens by Night', location_id: 15, location_name: 'Elysium',
    location_type: 'story', message_type: 'ic', speaker_mode: 'character',
    content: '<b>bold?</b> <img src=x onerror="alert(1)"> *Eleni smiles.*', created_at: '2026-10-04T10:00:00',
    language: 'en', state: 'unlabelled', label: null,
  },
  {
    id: 2, campaign_id: 8, campaign_name: 'Athens by Night', location_id: 13, location_name: 'OOC',
    location_type: 'ooc', message_type: 'ooc', speaker_mode: 'player',
    content: 'Quick rules question about Hunger dice', created_at: '2026-10-04T09:00:00',
    language: 'en', state: 'labelled',
    label: { in_character: false, intent: 'rules_question', labelled_by: 'lef', updated_at: '2026-10-04T10:00:00' },
  },
];

const COUNTS = {
  eligible: 2, labelled: 1, unlabelled: 1, stale: 0, in_character: 0, out_of_character: 1,
  intents: { dice: 0, combat: 0, rules_question: 1, roleplay: 0, general: 0 }, scan_limit_reached: false,
};

const REPORT = {
  version: 1, created_at: '2026-10-04T12:00:00Z',
  model: { name: 'laya-shadowrealms-chat', config_sha256: '97070eefe2d3' },
  ooc_threshold: 0.8, n: 2, errors: 0, stale_labels_skipped: 0, min_n_per_label: 30, min_n_total: 100,
  sample_too_small: true,
  ooc: {
    n: 2, correct: 2, accuracy: 1, accuracy_ci95: [0.34, 1], macro_f1: 1,
    per_label: {
      in_character: { n: 1, predicted: 1, correct: 1, precision: 1, recall: 1, f1: 1, too_small: true },
      out_of_character: { n: 1, predicted: 1, correct: 1, precision: 1, recall: 1, f1: 1, too_small: true },
    },
    confusion: { labels: ['in_character', 'out_of_character'], matrix: [[1, 0], [0, 1]] },
    too_small: true,
  },
  intent: {
    n: 2, correct: 1, accuracy: 0.5, accuracy_ci95: [0.09, 0.91], macro_f1: 0.5,
    per_label: {
      dice: { n: 0, predicted: 1, correct: 0, precision: 0, recall: null, f1: null, too_small: true },
      combat: { n: 0, predicted: 0, correct: 0, precision: null, recall: null, f1: null, too_small: true },
      rules_question: { n: 1, predicted: 0, correct: 0, precision: null, recall: 0, f1: null, too_small: true },
      roleplay: { n: 1, predicted: 1, correct: 1, precision: 1, recall: 1, f1: 1, too_small: true },
      general: { n: 0, predicted: 0, correct: 0, precision: null, recall: null, f1: null, too_small: true },
    },
    confusion: {
      labels: ['dice', 'combat', 'rules_question', 'roleplay', 'general'],
      matrix: [[0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 0, 0, 1, 0], [0, 0, 0, 0, 0]],
    },
    too_small: true,
  },
  languages: { en: { n: 2, ooc_accuracy: 1, intent_accuracy: 0.5, too_small: true } },
  misclassified: [
    {
      message_id: 2, campaign_id: 8, language: 'en', wrong: ['intent'],
      gold: { in_character: false, intent: 'rules_question' },
      pred: { in_character: false, p_ic: 0.03, intent: 'dice', intent_score: 0.89 },
      excerpt: '<i>Quick</i> rules question about Hunger dice',
    },
  ],
};

let calls;
let evaluated;

function respond(status, body) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

beforeEach(() => {
  calls = [];
  evaluated = false;
  global.fetch = jest.fn(async (url, init = {}) => {
    const method = (init.method || 'GET').toUpperCase();
    calls.push({ url: String(url), method, body: init.body ? JSON.parse(init.body) : undefined });
    if (String(url).startsWith('/api/admin/laya/messages')) {
      return respond(200, { items: ITEMS, total: 2, page: 1, per_page: 25, counts: COUNTS, campaigns: [{ id: 8, name: 'Athens by Night', n: 2 }] });
    }
    if (String(url).startsWith('/api/admin/laya/labels/')) return respond(200, { ok: true });
    if (String(url) === '/api/admin/laya/evaluate') {
      evaluated = true;
      return respond(202, { run: { id: 1, status: 'running' } });
    }
    if (String(url).startsWith('/api/admin/laya/report')) {
      if (!evaluated) return respond(200, { run: null, report: null, history: [] });
      const run = { id: 1, status: 'done', n: 2, ooc_accuracy: 1, intent_accuracy: 0.5 };
      return respond(200, { run, report: REPORT, history: [run] });
    }
    return respond(404, { error: 'not found' });
  });
});

afterEach(async () => {
  await act(async () => {
    await setLanguage('en', { remember: false, save: false });
  });
});

function mount() {
  const showSuccess = jest.fn();
  const showError = jest.fn();
  render(<LayaPanel token="jwt" showSuccess={showSuccess} showError={showError} />);
  return { showSuccess, showError };
}

test('lists player chat as plain text, with progress counts', async () => {
  mount();
  const item = await screen.findByTestId('laya-item-3');
  // The markup is shown literally, never parsed into elements.
  expect(within(item).getByText(/<b>bold\?<\/b> <img src=x onerror="alert\(1\)"> \*Eleni smiles\.\*/)).toBeInTheDocument();
  expect(item.querySelector('b')).toBeNull();
  expect(item.querySelector('img')).toBeNull();
  const counts = screen.getByTestId('laya-counts');
  expect(within(counts).getByText('Player chat messages')).toBeInTheDocument();
  expect(within(screen.getByTestId('laya-item-2')).getByText(/Out of character · Rules question · lef/)).toBeInTheDocument();
  expect(screen.getByText('No evaluation yet. Label some messages, then run one.')).toBeInTheDocument();
  expect(calls[0].url).toContain('status=unlabelled');
});

test('keyboard shortcuts label the current message', async () => {
  const user = setupUser();
  mount();
  await screen.findByTestId('laya-controls');
  await user.keyboard('i4');
  expect(screen.getByRole('button', { name: /In character/ })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByRole('button', { name: /Roleplay/ })).toHaveAttribute('aria-pressed', 'true');
  await user.keyboard('{Enter}');
  await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true));
  const put = calls.find((c) => c.method === 'PUT');
  expect(put.url).toBe('/api/admin/laya/labels/3');
  expect(put.body).toEqual({ in_character: true, intent: 'roleplay' });
});

test('save needs both answers; J moves to the next message', async () => {
  const user = setupUser();
  mount();
  await screen.findByTestId('laya-controls');
  await user.keyboard('o');
  expect(screen.getByRole('button', { name: 'Save label' })).toBeDisabled();
  await user.keyboard('{Enter}');
  expect(calls.some((c) => c.method === 'PUT')).toBe(false);
  await user.keyboard('j');
  expect(screen.getByTestId('laya-item-2')).toHaveAttribute('aria-current', 'true');
  // The labelled message's answers are preselected, and it can be cleared.
  expect(screen.getByRole('button', { name: /Rules question/ })).toHaveAttribute('aria-pressed', 'true');
  await user.click(screen.getByRole('button', { name: 'Clear label' }));
  await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.url === '/api/admin/laya/labels/2')).toBe(true));
});

test('running an evaluation shows the report, the small-sample warning and the confusion matrix', async () => {
  const user = setupUser();
  const { showSuccess } = mount();
  await screen.findByTestId('laya-item-3');
  await user.click(screen.getByRole('button', { name: 'Run evaluation' }));
  expect(calls.some((c) => c.method === 'POST' && c.url === '/api/admin/laya/evaluate')).toBe(true);
  const report = await screen.findByTestId('laya-report');
  expect(showSuccess).toHaveBeenCalledWith('Evaluation started.');
  expect(within(report).getByTestId('laya-too-small')).toHaveTextContent('fewer than 100 messages');
  const intent = within(report).getByTestId('laya-intent');
  expect(within(intent).getByText('Accuracy 0.500 (1 of 2) · 95% interval 0.090–0.910 · macro-F1 0.500')).toBeInTheDocument();
  expect(within(intent).getByText(/Confusion matrix, Intent/)).toBeInTheDocument();
  const misses = within(report).getByTestId('laya-misses');
  expect(within(misses).getByText('<i>Quick</i> rules question about Hunger dice')).toBeInTheDocument();
  expect(misses.querySelector('i')).toBeNull();
});

test('Greek labels', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false, save: false });
  });
  mount();
  await screen.findByTestId('laya-item-3');
  expect(screen.getByRole('button', { name: 'Εκτέλεση αξιολόγησης' })).toBeInTheDocument();
  expect(screen.getByText('Ουρά σήμανσης')).toBeInTheDocument();
});
