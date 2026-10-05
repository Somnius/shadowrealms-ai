import { useCallback, useEffect, useState } from 'react';
import { Button, Modal, Select } from '../../design';
import { useApi, useAuth } from '../../app/AuthContext';
import { errorText } from '../../app/http';
import { editionOf } from '../../rules/rulesEdition';
import { t } from '../../i18n';

/** A character that doesn't belong to a chronicle yet (e.g. an imported sheet). */
export const isUnassigned = (ch) => !!ch && (ch.campaign_id === null || ch.campaign_id === undefined);

const WOD_LINES = ['vampire', 'werewolf', 'mage'];

/** Whether a character may go into a chronicle: same rules edition and game line (backend checks the rest). */
export function fitsChronicle(ch, chronicle) {
  if (!ch || !chronicle) return false;
  if (editionOf(ch) !== editionOf(chronicle)) return false;
  const gs = String(chronicle.game_system || '').trim().toLowerCase();
  return !WOD_LINES.includes(gs) || gs === String(ch.system_type || '').trim().toLowerCase();
}

/** Server refusals of POST /characters/<id>/assign in the interface language. */
export function assignErrorText(data) {
  switch (data && data.error_code) {
    case 'rules_edition_mismatch':
      return t('profile:bring.error.edition', 'This character uses different rules than that chronicle.');
    case 'game_line_mismatch':
      return t('profile:bring.error.line', 'This character is from a different game line than that chronicle.');
    case 'single_locked_pc_conflict':
      return t('profile:bring.error.locked', 'You already have a locked character in another chronicle. Only a site administrator can allow more.');
    case 'character_already_in_chronicle':
      return t('profile:bring.error.already', 'This character already belongs to a chronicle.');
    default:
      return errorText(data, t('profile:bring.failed', 'Could not bring the character into the chronicle.'));
  }
}

/** POST the assignment; returns the api() result. */
export function assignCharacter(api, characterId, campaignId) {
  return api(`/characters/${characterId}/assign`, { method: 'POST', body: { campaign_id: Number(campaignId) } });
}

/** Dialog: pick one of your chronicles that fits the character and bring it in. */
export function BringIntoChronicleDialog({ character, chronicles, onClose, onDone, toast }) {
  const api = useApi();
  const options = (chronicles || []).filter((c) => fitsChronicle(character, c));
  const [cid, setCid] = useState(options[0] ? String(options[0].id) : '');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!cid) return;
    setBusy(true);
    const r = await assignCharacter(api, character.id, cid);
    setBusy(false);
    if (!r.ok) {
      toast({ tone: 'danger', title: assignErrorText(r.data) });
      return;
    }
    toast({
      tone: 'ok',
      title: t('profile:bring.done', '{{name}} joined {{chronicle}}.', { name: character.name, chronicle: r.data.campaign_name || '' }),
    });
    onDone(r.data);
  };

  return (
    <Modal open onClose={onClose} title={t('profile:bring.title', 'Bring {{name}} into a chronicle', { name: character.name })} icon="quill" size="sm">
      {options.length ? (
        <form className="sr-form" onSubmit={submit}>
          <p className="sr-muted">
            {t('profile:bring.body', 'Only your chronicles with the same rules as this sheet are listed. Once in, the character stays in that chronicle.')}
          </p>
          <Select
            label={t('profile:bring.chronicle', 'Chronicle')}
            value={cid}
            onChange={(e) => setCid(e.target.value)}
            options={options.map((c) => ({ value: String(c.id), label: c.name }))}
          />
          <div className="sr-form__actions">
            <Button type="button" variant="ghost" onClick={onClose}>
              {t('common:cancel', 'Cancel')}
            </Button>
            <Button type="submit" variant="primary" loading={busy} disabled={!cid}>
              {t('profile:bring.submit', 'Bring into chronicle')}
            </Button>
          </div>
        </form>
      ) : (
        <p className="sr-muted">
          {t('profile:bring.none', 'None of your chronicles uses the same rules as this character. Join one first, or ask its Storyteller to add you.')}
        </p>
      )}
    </Modal>
  );
}

/**
 * Inside a chronicle where you have no character: offer your characters without a chronicle that fit it.
 * Renders nothing when there are none.
 */
export function UnassignedOffer({ campaign, onAssigned, toast }) {
  const api = useApi();
  const { user } = useAuth();
  const [chars, setChars] = useState([]);
  const [busy, setBusy] = useState(null);
  const load = useCallback(async () => {
    const r = await api('/characters/');
    const list = r.ok && Array.isArray(r.data.characters) ? r.data.characters : [];
    setChars(list.filter((c) => user && String(c.user_id) === String(user.id) && isUnassigned(c) && fitsChronicle(c, campaign)));
  }, [api, user, campaign]);
  useEffect(() => {
    load();
  }, [load]);

  if (!chars.length) return null;
  const bring = async (ch) => {
    setBusy(ch.id);
    const r = await assignCharacter(api, ch.id, campaign.id);
    setBusy(null);
    if (!r.ok) {
      toast({ tone: 'danger', title: assignErrorText(r.data) });
      return;
    }
    toast({ tone: 'ok', title: t('profile:bring.done', '{{name}} joined {{chronicle}}.', { name: ch.name, chronicle: campaign.name || '' }) });
    if (onAssigned) onAssigned(ch);
  };
  return (
    <div className="sr-stack sr-stack--tight">
      <p className="sr-muted sr-small">{t('profile:bring.offer', 'Or bring a character that has no chronicle yet:')}</p>
      {chars.map((ch) => (
        <Button key={ch.id} size="sm" variant="secondary" icon="mask" loading={busy === ch.id} disabled={busy != null} onClick={() => bring(ch)}>
          {t('profile:bring.here', 'Bring {{name}} here', { name: ch.name })}
        </Button>
      ))}
    </div>
  );
}
