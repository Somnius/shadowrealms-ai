import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import CharacterSheetModal from '../components/CharacterSheetModal';
import { useToast } from '../design';
import { apiFetch, errorText, getCurrentToken } from './http';
import { t } from '../i18n';

const SheetContext = createContext(null);

/** Open the (phase 1) character sheet modal from anywhere in the shell: useSheet().openSheet(id). */
export function SheetProvider({ children }) {
  const { toast } = useToast();
  const [sheet, setSheet] = useState(null);

  const openSheet = useCallback(
    async (characterId, gameSystem) => {
      if (!characterId) return;
      const r = await apiFetch(getCurrentToken(), `/characters/${characterId}`);
      if (!r.ok || !r.data.character) {
        toast({ tone: 'danger', title: errorText(r.data, t('sheet:loadFailed', 'Could not load the character sheet.')) });
        return;
      }
      const ch = r.data.character;
      setSheet({ character: ch, gameSystem: gameSystem || ch.system_type });
    },
    [toast]
  );

  const value = useMemo(() => ({ openSheet }), [openSheet]);
  return (
    <SheetContext.Provider value={value}>
      {children}
      {sheet ? (
        <CharacterSheetModal character={sheet.character} gameSystem={sheet.gameSystem} onClose={() => setSheet(null)} />
      ) : null}
    </SheetContext.Provider>
  );
}

export function useSheet() {
  const ctx = useContext(SheetContext);
  if (!ctx) throw new Error('useSheet() needs a <SheetProvider>');
  return ctx;
}
