import { V5_PREDATOR_TYPES } from '../../../characterSheet/v5/constants';
import { predatorAllowed } from '../../../characterSheet/v5/validation';
import { t } from '../../../i18n';

/** <option>s for every predator type; ones the clan or the chronicle rules out are disabled. */
export default function PredatorOptions({ clan, settings }) {
  return V5_PREDATOR_TYPES.map((p) => {
    const clanBlocked = (p.forbidden_clans || []).includes(clan);
    const chronicleBlocked = !predatorAllowed(settings, p.name);
    return (
      <option key={p.name} value={p.name} disabled={clanBlocked || chronicleBlocked}>
        {p.name}
        {clanBlocked ? ` ${t('wizard:v5.notFor', '(not for {{clan}})', { clan })}` : ''}
        {!clanBlocked && chronicleBlocked ? ` ${t('wizard:v5.notAllowed', '(not in this chronicle)')}` : ''}
      </option>
    );
  });
}
