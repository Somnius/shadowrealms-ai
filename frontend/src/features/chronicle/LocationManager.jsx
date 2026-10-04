import React, { useCallback, useEffect, useState } from 'react';
import { Button, Checkbox, Glyph, Input, Modal, Panel, Select, Spinner, Textarea } from '../../design';
import LocationSuggestions from '../../components/LocationSuggestions';
import { errorText } from '../../app/http';
import { localizeRooms, roomGlyph } from '../play/ChannelList';
import { t } from '../../i18n';

export const ROOM_TYPES = ['street', 'elysium', 'haven', 'custom'];

/** Translated name of a room type (server stores English keys; unknown custom types are shown as typed). */
export function roomTypeLabel(type) {
  const ty = String(type || '').toLowerCase();
  if (ty === 'ooc') return t('chronicle:rooms.type.ooc', 'Out of character');
  if (ty === 'elysium') return t('chronicle:rooms.type.elysium', 'Elysium');
  if (ty === 'haven') return t('chronicle:rooms.type.haven', 'Haven');
  if (ty === 'street') return t('chronicle:rooms.type.street', 'Street / city');
  if (ty === 'custom' || !ty) return t('chronicle:rooms.type.custom', 'Other');
  return type;
}

/** Server error for room actions; a 403 gets a translated explanation instead of "Unauthorized". */
function roomError(r, fallback) {
  if (r.status === 403) return t('chronicle:rooms.forbidden', 'Only the Storyteller of this chronicle or an admin can change its locations.');
  return errorText(r.data, fallback);
}

/** Add a location by hand: name, type, description. */
function NewLocationForm({ api, campaignId, onCreated, onCancel }) {
  const [name, setName] = useState('');
  const [type, setType] = useState('street');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError(t('chronicle:rooms.nameRequired', 'Give the location a name.'));
      return;
    }
    setBusy(true);
    const r = await api(`/campaigns/${campaignId}/locations`, {
      method: 'POST',
      body: { name: name.trim(), type, description: description.trim() },
    });
    setBusy(false);
    if (!r.ok) {
      setError(roomError(r, t('chronicle:rooms.createFailed', 'Could not create the location.')));
      return;
    }
    onCreated(r.data);
  };
  return (
    <form className="sr-form" onSubmit={submit} noValidate>
      <Input
        label={t('chronicle:rooms.name', 'Name')}
        value={name}
        required
        maxLength={120}
        autoFocus
        onChange={(e) => {
          setName(e.target.value);
          if (error) setError('');
        }}
        error={error || undefined}
      />
      <Select label={t('chronicle:rooms.typeLabel', 'Type')} value={type} onChange={(e) => setType(e.target.value)}>
        {ROOM_TYPES.map((ty) => (
          <option key={ty} value={ty}>
            {roomTypeLabel(ty)}
          </option>
        ))}
      </Select>
      <Textarea
        label={t('chronicle:rooms.description', 'Description (optional)')}
        hint={t('chronicle:rooms.descriptionHint', 'Shown under the room name; the AI Storyteller reads it too.')}
        rows={3}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <div className="sr-form__actions">
        <Button variant="ghost" onClick={onCancel}>
          {t('common:cancel', 'Cancel')}
        </Button>
        <Button type="submit" variant="primary" icon="plus" loading={busy}>
          {t('chronicle:rooms.create', 'Create location')}
        </Button>
      </div>
    </form>
  );
}

/** Rooms of a chronicle: open/close with a reason, delete, add by hand or with AI suggestions. */
export default function LocationManager({ api, campaign, canEditAccess, toast, onChanged }) {
  const [locations, setLocations] = useState(null);
  const [edits, setEdits] = useState({});
  const [busy, setBusy] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [newOpen, setNewOpen] = useState(false);

  const load = useCallback(async () => {
    const r = await api(`/campaigns/${campaign.id}/locations`);
    const list = r.ok && Array.isArray(r.data) ? localizeRooms(r.data) : [];
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
      toast({ tone: 'danger', title: roomError(r, t('chronicle:rooms.saveFailed', 'Could not save room access')) });
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
      toast({ tone: 'danger', title: roomError(r, t('chronicle:rooms.deleteFailed', 'Could not delete the room')) });
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
        <>
          <Button size="sm" variant="primary" icon="plus" onClick={() => setNewOpen(true)}>
            {t('chronicle:rooms.new', 'New location')}
          </Button>
          <Button size="sm" variant="arcane" icon="ai-sigil" onClick={() => setSuggestOpen(true)}>
            {t('chronicle:rooms.suggest', 'Add with AI suggestions')}
          </Button>
        </>
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
                  <span className="sr-muted sr-small">{roomTypeLabel(loc.type)}</span>
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
      <Modal open={newOpen} onClose={() => setNewOpen(false)} title={t('chronicle:rooms.new', 'New location')} icon="plus" size="sm">
        {newOpen ? (
          <NewLocationForm
            api={api}
            campaignId={campaign.id}
            onCancel={() => setNewOpen(false)}
            onCreated={(loc) => {
              setNewOpen(false);
              toast({ tone: 'ok', title: t('chronicle:rooms.created', 'Location “{{name}}” created.', { name: loc?.name || '' }) });
              load();
              onChanged();
            }}
          />
        ) : null}
      </Modal>
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
