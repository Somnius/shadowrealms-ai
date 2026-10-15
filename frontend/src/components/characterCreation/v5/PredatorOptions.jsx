import { getV5Rules } from '../../../characterSheet/v5/rulesData';
import { predatorAllowed, predatorInBooks } from '../../../characterSheet/v5/validation';
import { t } from '../../../i18n';

/**
 * <option>s for every predator type from the chronicle's books (and the `current` one, whatever
 * its book); ones the clan or the chronicle rules out are disabled.
 */
export default function PredatorOptions({ clan, settings, current }) {
  return getV5Rules().predators.filter((p) => p.name === current || predatorInBooks(settings, p.name)).map((p) => {
    const clanBlocked = (p.forbidden_clans || []).includes(clan);
    const chronicleBlocked = !predatorAllowed(settings, p.name) || !predatorInBooks(settings, p.name);
    return (
      <option key={p.name} value={p.name} disabled={clanBlocked || chronicleBlocked}>
        {p.name}
        {clanBlocked ? ` ${t('wizard:v5.notFor', '(not for {{clan}})', { clan })}` : ''}
        {!clanBlocked && chronicleBlocked ? ` ${t('wizard:v5.notAllowed', '(not in this chronicle)')}` : ''}
      </option>
    );
  });
}
