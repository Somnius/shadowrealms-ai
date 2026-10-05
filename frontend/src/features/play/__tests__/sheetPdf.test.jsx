import { act, render, screen, waitFor } from '@testing-library/react';
import { DesignProvider, ToastProvider } from '../../../design';
import setupUser from '../../../design/testing/setupUser';
import { setCurrentToken } from '../../../app/http';
import { defaultPaper, pdfFileName } from '../../../app/sheetPdf';
import { setLanguage } from '../../../i18n';
import MemberPanel from '../MemberPanel';
import CharacterSheetModal from '../../../components/CharacterSheetModal';

const campaign = { id: 5, game_system: 'vampire', rules_edition: 'v5' };
const character = { id: 9, name: 'Κωνσταντίνος Κατακουζηνός', rules_edition: 'v5', wod_meta: { hunger: 1 } };

let clicked;
let realCreate;
let realRevoke;

beforeEach(() => {
  setCurrentToken('jwt-abc');
  clicked = [];
  jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function click() {
    clicked.push({ href: this.href, download: this.download });
  });
  realCreate = URL.createObjectURL;
  realRevoke = URL.revokeObjectURL;
  URL.createObjectURL = jest.fn(() => 'blob:sheet');
  URL.revokeObjectURL = jest.fn();
  global.fetch = jest.fn(async () => ({ ok: true, status: 200, blob: async () => new Blob(['%PDF-1.4']) }));
});

afterEach(async () => {
  jest.restoreAllMocks();
  URL.createObjectURL = realCreate;
  URL.revokeObjectURL = realRevoke;
  setCurrentToken(null);
  await act(async () => {
    await setLanguage('en', { remember: false, save: false });
  });
});

function mountPanel() {
  return render(
    <DesignProvider>
      <ToastProvider>
        <MemberPanel campaign={campaign} character={character} members={[]} user={{ id: 2 }} onOpenSheet={() => {}} onPortrait={() => {}} toast={() => {}} />
      </ToastProvider>
    </DesignProvider>
  );
}

test('the character card offers Export PDF next to sheet and portrait', () => {
  mountPanel();
  const names = screen.getAllByRole('button').map((b) => b.textContent);
  expect(names).toEqual(expect.arrayContaining(['Character sheet', 'Portrait', 'Export PDF']));
});

test('Export PDF fetches with the Bearer token and downloads under the character name', async () => {
  const user = setupUser();
  mountPanel();
  await user.click(screen.getByRole('button', { name: 'Export PDF' }));
  await waitFor(() => expect(clicked).toHaveLength(1));
  expect(global.fetch).toHaveBeenCalledTimes(1);
  const [url, init] = global.fetch.mock.calls[0];
  expect(url).toMatch(/^\/api\/characters\/9\/sheet\.pdf(\?paper=letter)?$/);
  expect(init.headers.Authorization).toBe('Bearer jwt-abc');
  expect(clicked[0]).toEqual({ href: 'blob:sheet', download: 'Κωνσταντίνος Κατακουζηνός.pdf' });
  expect(URL.createObjectURL).toHaveBeenCalled();
});

test('a refused export shows an error and downloads nothing', async () => {
  global.fetch = jest.fn(async () => ({ ok: false, status: 404, json: async () => ({ error: 'Character not found' }) }));
  const user = setupUser();
  mountPanel();
  await user.click(screen.getByRole('button', { name: 'Export PDF' }));
  expect(await screen.findByText('Could not export the PDF.')).toBeInTheDocument();
  expect(clicked).toHaveLength(0);
});

test('the sheet modal has the same action, in Greek too', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false, save: false });
  });
  render(
    <DesignProvider>
      <ToastProvider>
        <CharacterSheetModal character={{ ...character, attributes: {}, skills: {} }} gameSystem="vampire" onClose={() => {}} />
      </ToastProvider>
    </DesignProvider>
  );
  expect(screen.getByRole('button', { name: 'Εξαγωγή PDF' })).toBeInTheDocument();
});

test('a download that breaks off mid-body shows an error', async () => {
  global.fetch = jest.fn(async () => ({
    ok: true,
    status: 200,
    blob: async () => {
      throw new TypeError('network error');
    },
  }));
  const user = setupUser();
  mountPanel();
  await user.click(screen.getByRole('button', { name: 'Export PDF' }));
  expect(await screen.findByText('Could not export the PDF.')).toBeInTheDocument();
  expect(clicked).toHaveLength(0);
});

test('file names drop bidi controls', () => {
  expect(pdfFileName('evil\u202Efdp.exe')).toBe('evilfdp.exe.pdf');
  expect(pdfFileName('\u2067Κων\u200fσταντίνος\u2069')).toBe('Κωνσταντίνος.pdf');
});

test('file names keep Greek and drop path characters', () => {
  expect(pdfFileName('Κωνσταντίνος / Κ.')).toBe('Κωνσταντίνος Κ.pdf');
  expect(pdfFileName('a:b*c?"d"<e>|')).toBe('a b c d e.pdf');
  expect(pdfFileName('  ..  ')).toBe('character.pdf');
});

test('paper follows the locale', () => {
  expect(defaultPaper(['en-US'])).toBe('letter');
  expect(defaultPaper(['el-GR'])).toBe('a4');
  expect(defaultPaper(['en-GB'])).toBe('a4');
  expect(defaultPaper([])).toBe('a4');
});
