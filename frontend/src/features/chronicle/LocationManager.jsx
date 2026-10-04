import React, { useCallback, useEffect, useState } from 'react';
import { Button, Checkbox, Glyph, Modal, Panel, Spinner, Textarea } from '../../design';
import LocationSuggestions from '../../components/LocationSuggestions';
import { errorText } from '../../app/http';
import { roomGlyph } from '../play/ChannelList';
import { t } from '../../i18n';

/** Rooms of a chronicle: open/close with a reason, delete, add with AI suggestions. */
export default function LocationManager({ api, campaign, canEditAccess, toast, onChanged }) {
  const [locations, setLocations] = useState(null);
  const [edits, setEdits] = useState({});
  const [busy, setBusy] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [suggestOpen, setSuggestOpen] = useState(false);

  const load = useCallback(async () => {
    const r = await api(`/campaigns/${campaign.id}/locations`);
    const list = r.ok && Array.isArray(r.data) ? r.data : [];
    setLocations(list);
    const next = {};
    list.forEach((l) => {
      next[l.id] = { is_open: l.is_open !== false && l.is_open !== 0, closure_reason: l.closure_reason || '' };
    });
    setEdits(next);
  }, [api, campaign.id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (window.location.hash === '#locations') {
      const el = document.getElementById('locations');
      if (el) el.scrollIntoView({ block: 'start' });
    }
  }, [locations]);

  const saveAccess = async (loc) => {
    const draft = edits[loc.id];
    setBusy(loc.id);
    const r = await api(`/locations/${loc.id}`, { method: 'PUT', body: { is_open: draft.is_open, closure_reason: draft.closure_reason || '' } });
    setBusy(null);
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('chronicle:rooms.saveFailed', 'Could not save room access')) });
      return;
    }
    toast({ tone: 'ok', title: t('chronicle:rooms.saved', 'Room access updated.') });
    load();
    onChanged();
  };

  const remove = async () => {
    const loc = toDelete;
    setToDelete(null);
    setBusy(loc.id);
    const r = await api(`/campaigns/${campaign.id}/locations/${loc.id}`, { method: 'DELETE' });
    setBusy(null);
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('chronicle:rooms.deleteFailed', 'Could not delete the room')) });
      return;
    }
    toast({ tone: 'ok', title: t('chronicle:rooms.deleted', 'Room deleted.') });
    load();
    onChanged();
  };

  return (
    <Panel
      id="locations"
      title={t('chronicle:rooms.title', 'Locations')}
      icon="room-street"
      actions={
        <Button size="sm" variant="arcane" icon="ai-sigil" onClick={() => setSuggestOpen(true)}>
          {t('chronicle:rooms.suggest', 'Add with AI suggestions')}
        </Button>
      }
    >
      {locations == null ? (
        <Spinner label={t('common:loading', 'Loading')} />
      ) : (
        <ul className="sr-locs">
          {locations.map((loc) => {
            const ooc = String(loc.type).toLowerCase() === 'ooc';
            const draft = edits[loc.id] || { is_open: true, closure_reason: '' };
            return (
              <li key={loc.id} className="sr-loc">
                <div className="sr-loc__head">
                  <Glyph name={roomGlyph(loc.type)} size={20} />
                  <strong className="sr-loc__name">{loc.name}</strong>
                  <span className="sr-muted sr-small">{loc.type}</span>
                  {!ooc ? (
                    <Button size="sm" variant="ghost" icon="trash" onClick={() => setToDelete(loc)} disabled={busy === loc.id} className="sr-loc__del">
                      {t('common:delete', 'Delete')}
                    </Button>
                  ) : null}
                </div>
                {loc.description ? <p className="sr-muted sr-small sr-loc__desc">{loc.description}</p> : null}
                {canEditAccess && !ooc ? (
                  <div className="sr-loc__access">
                    <Checkbox
                      label={t('chronicle:rooms.open', 'Open to players (unchecked = closed, scene paused)')}
                      checked={draft.is_open}
                      onChange={(e) => setEdits((p) => ({ ...p, [loc.id]: { ...draft, is_open: e.target.checked } }))}
                    />
                    {!draft.is_open ? (
                      <Textarea
                        label={t('chronicle:rooms.reason', 'Reason shown to players (optional)')}
                        rows={2}
                        value={draft.closure_reason}
                        onChange={(e) => setEdits((p) => ({ ...p, [loc.id]: { ...draft, closure_reason: e.target.value } }))}
                      />
                    ) : null}
                    <Button size="sm" variant="secondary" onClick={() => saveAccess(loc)} loading={busy === loc.id}>
                      {t('chronicle:rooms.saveAccess', 'Save access')}
                    </Button>
                  </div>
                ) : null}
                {canEditAccess && ooc ? <p className="sr-muted sr-small">{t('chronicle:rooms.oocAlwaysOpen', 'The OOC lobby cannot be closed.')}</p> : null}
              </li>
            );
          })}
        </ul>
      )}
      <Modal
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        title={t('chronicle:rooms.deleteTitle', 'Delete {{name}}?', { name: toDelete?.name || '' })}
        icon="trash"
        size="sm"
        description={t('chronicle:rooms.deleteBody', 'All messages in this room are deleted too. This cannot be undone.')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setToDelete(null)}>
              {t('common:cancel', 'Cancel')}
            </Button>
            <Button variant="danger" icon="trash" onClick={remove}>
              {t('chronicle:rooms.deleteConfirm', 'Delete room')}
            </Button>
          </>
        }
      />
      <Modal open={suggestOpen} onClose={() => setSuggestOpen(false)} title={t('chronicle:rooms.suggest', 'Add with AI suggestions')} icon="ai-sigil" size="lg">
        {suggestOpen ? (
          <div className="sr-legacy">
            <LocationSuggestions
              campaignId={campaign.id}
              settingDescription={campaign.description}
              onComplete={() => {
                setSuggestOpen(false);
                toast({ tone: 'ok', title: t('chronicle:rooms.added', 'New locations added.') });
                load();
                onChanged();
              }}
              onSkip={() => setSuggestOpen(false)}
            />
          </div>
        ) : null}
      </Modal>
    </Panel>
  );
}
