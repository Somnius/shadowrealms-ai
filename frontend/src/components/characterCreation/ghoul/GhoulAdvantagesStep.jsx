import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import MeritFlawRows from '../MeritFlawRows';
import { V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { PLAYER_GHOUL, ghoulAdvantageOptions, ghoulLoresheetOptions } from '../../../characterSheet/v5/ghoul';
import { ghoulTemplateName } from '../../../characterSheet/i18nErrors';
import { t } from '../../../i18n';
import CatalogAdvantages from '../v5/CatalogAdvantages';
import { ACCENT, InlineError, noteStyle, useForge } from '../v5/forgeUi';

// what a ghoul may take from the catalog (PG p. 141): no clan, predator type or thin-blood rows
const GHOUL_RULES = {
  options: (kind, settings) => ghoulAdvantageOptions(kind, settings),
  loresheets: (settings) => ghoulLoresheetOptions(settings),
  levelAllowed: () => true,
};

// written for Kindred: on a ghoul, the Storyteller's ruling (the note says how it works)
const KINDRED_WORDED = ['flaw:bondslave', 'flaw:two-masters', 'flaw:addiction', 'flaw:bond-junkie', 'flaw:long-bond'];

/** Advantages & Flaws: the template's budget (core p. 185) or a player ghoul's 7 and 2 (PG p. 141). */
export default function GhoulAdvantagesStep() {
  const f = useForge();
  const { derived, advDots, flawDots, settings } = f;
  const player = f.template === PLAYER_GHOUL;
  const cap = settings.flaws_max_dots;
  const flawMax = derived.flaw_max_dots;
  const over =
    advDots > derived.advantage_dots || flawDots < derived.flaw_min_dots || (flawMax != null && flawDots > flawMax) || (cap != null && flawDots > cap);
  const ruled = f.sheet.flaws.filter((r) => KINDRED_WORDED.includes(r.id)).map((r) => r.name);
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.advantages}
      title="Advantages & Flaws"
      subtitle={
        player
          ? t('wizard:ghoul.advantagesPlayer', '7 dots of Advantages and at least 2 dots of Flaws, as mortals take them (Players Guide p. 141).')
          : t('wizard:ghoul.advantagesTemplate', '{{template}}: up to {{adv}} Advantage dots and up to {{flaws}} Flaw dots (core p. 185).', {
              template: ghoulTemplateName(f.template),
              adv: derived.advantage_dots,
              flaws: flawMax ?? 0,
            })
      }
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.advantages} />
      <p id="ghoul-advantages-count" style={{ color: over ? 'var(--sr-blood-300)' : 'var(--sr-ok-400)', fontSize: '12px', margin: '0 0 6px' }}>
        {player
          ? t('wizard:v5.advantagesCount', 'Advantages {{adv}}/{{advMax}} · Flaws {{flaws}} (min {{flawMin}})', { adv: advDots, advMax: derived.advantage_dots, flaws: flawDots, flawMin: derived.flaw_min_dots })
          : t('wizard:ghoul.advantagesCount', 'Advantages {{adv}}/{{advMax}} · Flaws {{flaws}}/{{flawMax}}', { adv: advDots, advMax: derived.advantage_dots, flaws: flawDots, flawMax: flawMax ?? 0 })}
        {cap != null ? ` · ${t('wizard:v5.flawCap', 'max {{n}} in this chronicle', { n: cap })}` : ''}
      </p>
      <p style={{ ...noteStyle, fontSize: '12px', margin: '0 0 10px' }}>
        {t('wizard:ghoul.advantagesNote', "Ghouls take mortals' Merits and Flaws and the ghoul-only ones, not Domain, Feeding, Herd or thin-blood entries (Players Guide p. 141). Haven and Mythic entries are your Storyteller's call.")}
      </p>
      {f.catalogAdvantages ? (
        <CatalogAdvantages rules={GHOUL_RULES} />
      ) : (
        <MeritFlawRows rows={f.meritRows} setRows={f.setMeritRows} globalNotes={f.meritNotes} setGlobalNotes={f.setMeritNotes} />
      )}
      {ruled.length ? (
        <p id="ghoul-kindred-flaws" style={{ color: 'var(--sr-gold-400)', fontSize: '12px', margin: '10px 0 0' }}>
          {t('wizard:ghoul.kindredFlaws', '{{names}}: written for Kindred. On a ghoul it is your Storyteller\'s ruling: write how it works in the note.', { names: ruled.join(', ') })}
        </p>
      ) : null}
    </ResponsiveSheetBlock>
  );
}
