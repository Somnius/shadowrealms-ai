import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { t } from '../../../i18n';
import { inputStyle, useForge } from './forgeUi';

/** Last: the character's story in prose. */
export default function StoryStep() {
  const f = useForge();
  return (
    <ResponsiveSheetBlock sectionId={V5_SECTION_IDS.story} title={t('wizard:section.story', 'Story')} subtitle={t('wizard:v5.storySub', 'Background narrative.')} accent="var(--sr-arcane-500)">
      <textarea
        aria-label={t('wizard:v5.storySub', 'Background narrative.')}
        value={f.background}
        onChange={(e) => f.setBackground(e.target.value)}
        rows={6}
        placeholder={t('wizard:v5.storyPlaceholder', 'History, coterie, goals…')}
        style={{ ...inputStyle, resize: 'vertical', fontFamily: 'var(--sr-font-body)', lineHeight: 1.6 }}
      />
    </ResponsiveSheetBlock>
  );
}
