import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { Avatar, Badge, Button, Card, Checkbox, EmptyState, Glyph, Input, Modal, Panel, Select, Spinner, Textarea, useToast } from '../../design';
import { PageBody, TopBar } from '../../app/AppShell';
import ButtonLink from '../../app/ButtonLink';
import { useApi, useAuth } from '../../app/AuthContext';
import { useChronicles } from '../../app/ChroniclesContext';
import { useSheet } from '../../app/SheetContext';
import { errorText } from '../../app/http';
import { canUseStaffVoice, gameSystemTitle, isStoryteller, lineGlyph, lineOf } from '../../app/hooks';
import { editionLabel } from '../../rules/rulesEdition';
import LocationManager from './LocationManager';
import { t } from '../../i18n';
import { Term } from '../../i18n/glossary';
import './chronicle.css';

function Stat({ value, label, glyph }) {
  return (
    <div className="sr-stat">
      <Glyph name={glyph} size={20} />
      <span className="sr-stat__value">{value}</span>
      <span className="sr-stat__label">{label}</span>
    </div>
  );
}

export default function ChronicleSettingsPage() {
  const { id } = useParams();
  const api = useApi();
  const navigate = useNavigate();
  const { user, isAdmin } = useAuth();
  const { toast } = useToast();
  const { byId, reload: reloadList } = useChronicles();
  const { openSheet } = useSheet();
  const [campaign, setCampaign] = useState(null);
  const [state, setState] = useState('loading');
  const [stats, setStats] = useState(null);
  const [members, setMembers] = useState([]);
  const [characters, setCharacters] = useState([]);
  const [editName, setEditName] = useState(null);
  const [editDesc, setEditDesc] = useState(null);
  const [saving, setSaving] = useState(false);
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteText, setDeleteText] = useState('');
  // Typing the chronicle's own name (any case, extra spaces ignored) confirms the delete.
  const norm = (v) => String(v || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase();
  const [addMemberId, setAddMemberId] = useState('');
  const [pcUser, setPcUser] = useState('');
  const [pcChar, setPcChar] = useState('');

  const load = useCallback(async () => {
    const [d, s, r, c] = await Promise.all([
      api(`/campaigns/${id}`),
      api(`/campaigns/${id}/stats`),
      api(`/campaigns/${id}/roster`),
      api(`/characters/?campaign_id=${id}`),
    ]);
    if (!d.ok) {
      setState(errorText(d.data, t('chronicle:loadFailed', 'Could not load this chronicle.')));
      return;
    }
    setCampaign(d.data);
    setStats(s.ok ? s.data : null);
    setMembers(r.ok && Array.isArray(r.data.members) ? r.data.members : []);
    setCharacters(c.ok && Array.isArray(c.data.characters) ? c.data.characters : []);
    setState('ready');
  }, [api, id]);

  useEffect(() => {
    setState('loading');
    load();
  }, [load]);

  const listEntry = byId(id);
  const isST = isStoryteller(user, campaign);
  const canManage = isAdmin || isST;
  const staff = canUseStaffVoice(user, campaign);
  const myCharacter = useMemo(() => {
    const playing = listEntry && listEntry.my_playing_character_id;
    return characters.find((c) => String(c.id) === String(playing)) || null;
  }, [characters, listEntry]);

  const update = async (payload, okText) => {
    setSaving(true);
    const r = await api(`/campaigns/${id}`, { method: 'PUT', body: payload });
    setSaving(false);
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('chronicle:saveFailed', 'Save failed')) });
      return false;
    }
    toast({ tone: 'ok', title: okText });
    await load();
    reloadList();
    return true;
  };

  const saveEnrollment = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const max = parseInt(String(fd.get('max_players') || ''), 10);
    await update(
      {
        listing_visibility: String(fd.get('listing_visibility') || 'private'),
        accepting_players: fd.get('accepting_players') === 'on',
        max_players: Number.isFinite(max) && max >= 0 ? max : campaign.max_players,
      },
      t('chronicle:enrollment.saved', 'Enrollment settings saved.')
    );
  };

  const leave = async () => {
    setSaving(true);
    const r = await api(`/campaigns/${id}/detach`, { method: 'POST', body: {} });
    setSaving(false);
    setLeaveOpen(false);
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('chronicle:leave.failed', 'Could not leave the chronicle')) });
      return;
    }
    toast({ tone: 'ok', title: t('chronicle:leave.done', 'You left the chronicle.') });
    await reloadList();
    navigate('/chronicles');
  };

  const deleteMatches = !!campaign && norm(deleteText) !== '' && norm(deleteText) === norm(campaign.name);

  const destroy = async () => {
    if (!deleteMatches) return;
    setSaving(true);
    const r = await api(`/campaigns/${id}`, { method: 'DELETE' });
    setSaving(false);
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('chronicle:delete.failed', 'Could not delete the chronicle')) });
      return;
    }
    setDeleteOpen(false);
    toast({ tone: 'ok', title: t('chronicle:delete.done', 'Chronicle deleted.') });
    await reloadList();
    navigate('/chronicles');
  };

  const addMember = async (e) => {
    e.preventDefault();
    const raw = String(addMemberId || '').trim();
    if (!raw) return;
    // A number is a user ID; anything else is a username (the server looks it up).
    const body = /^\d+$/.test(raw) ? { user_id: parseInt(raw, 10) } : { username: raw };
    const r = await api(`/campaigns/${id}/members`, { method: 'POST', body });
    if (!r.ok) {
      toast({
        tone: 'danger',
        title:
          r.status === 404
            ? t('chronicle:members.notFound', 'No account called “{{name}}”.', { name: raw })
            : r.status === 403
              ? t('chronicle:members.forbidden', 'Only the Storyteller or staff can add members.')
              : t('chronicle:members.addFailed', 'Could not add the member'),
      });
      return;
    }
    toast({ tone: 'ok', title: t('chronicle:members.added', 'Member added.') });
    setAddMemberId('');
    load();
  };

  const setPlaying = async (e) => {
    e.preventDefault();
    const uid = parseInt(pcUser, 10);
    const cid = parseInt(pcChar, 10);
    if (!Number.isFinite(uid) || !Number.isFinite(cid)) return;
    const r = await api(`/campaigns/${id}/players/${uid}/playing-character`, { method: 'PUT', body: { character_id: cid } });
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('chronicle:members.pcFailed', 'Could not set the playing character')) });
      return;
    }
    toast({ tone: 'ok', title: t('chronicle:members.pcDone', 'Playing character updated.') });
    setPcChar('');
    load();
    reloadList();
  };

  if (state !== 'ready') {
    return (
      <>
        <TopBar title={t('chronicle:title', 'Chronicle')} icon="settings" />
        <PageBody>
          {state === 'loading' ? <Spinner label={t('common:loading', 'Loading')} /> : <EmptyState glyph="lock-chain" title={state} />}
        </PageBody>
      </>
    );
  }

  const pcOptions = characters.filter((c) => String(c.user_id) === String(pcUser));

  return (
    <div className="sr-chronicle" data-line={lineOf(campaign.game_system) || undefined}>
      <TopBar
        title={<span className="sr-usertitle">{campaign.name}</span>}
        subtitle={t('chronicle:subtitle', 'Details & settings')}
        icon={lineGlyph(campaign.game_system)}
        actions={
          <ButtonLink to={`/c/${id}`} variant="primary" size="sm" icon="chevron-right">
            {t('chronicle:enter', 'Enter chronicle')}
          </ButtonLink>
        }
      />
      <PageBody narrow>
        <div className="sr-stack">
          <Card className="sr-pad sr-chronicle__head">
            {editName != null ? (
              <form
                className="sr-row"
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (!editName.trim()) return;
                  if (await update({ name: editName.trim() }, t('chronicle:name.saved', 'Name saved.'))) setEditName(null);
                }}
              >
                <Input label={t('chronicle:field.name', 'Name')} value={editName} onChange={(e) => setEditName(e.target.value)} autoFocus fieldClassName="sr-grow" />
                <Button type="submit" variant="primary" loading={saving}>
                  {t('common:save', 'Save')}
                </Button>
                <Button variant="ghost" onClick={() => setEditName(null)}>
                  {t('common:cancel', 'Cancel')}
                </Button>
              </form>
            ) : (
              <div className="sr-row">
                <h2 className="sr-chronicle__name sr-usertitle">{campaign.name}</h2>
                {canManage ? (
                  <Button size="sm" variant="ghost" icon="quill" onClick={() => setEditName(campaign.name || '')}>
                    {t('chronicle:name.edit', 'Rename')}
                  </Button>
                ) : null}
              </div>
            )}
            <div className="sr-row">
              <Badge tone="neutral" icon={lineGlyph(campaign.game_system)}>
                <span lang="en">{gameSystemTitle(campaign.game_system)}</span>
              </Badge>
              <Badge edition={editionLabel(campaign)} />
              {isST ? <Badge tone="gold" icon="crown-thorns">{t('chronicle:youAreST', 'You are the Storyteller')}</Badge> : null}
            </div>
            {stats ? (
              <div className="sr-stats">
                <Stat value={stats.active_players ?? 0} label={t('chronicle:stats.players', 'Players')} glyph="users" />
                <Stat value={stats.characters ?? 0} label={t('chronicle:stats.characters', 'Characters')} glyph="mask" />
                <Stat value={stats.locations ?? 0} label={t('chronicle:stats.locations', 'Locations')} glyph="room-street" />
                <Stat value={stats.messages ?? 0} label={t('chronicle:stats.messages', 'Messages')} glyph="quill" />
              </div>
            ) : null}
          </Card>

          <Panel
            title={t('chronicle:world.title', 'World & setting')}
            icon="book"
            actions={
              canManage && editDesc == null ? (
                <Button size="sm" variant="ghost" icon="quill" onClick={() => setEditDesc(campaign.description || '')}>
                  {t('common:edit', 'Edit')}
                </Button>
              ) : null
            }
          >
            {editDesc != null ? (
              <form
                className="sr-form"
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (!editDesc.trim()) return;
                  if (await update({ description: editDesc }, t('chronicle:world.saved', 'World description saved.'))) setEditDesc(null);
                }}
              >
                <p className="sr-warnbox">
                  <Glyph name="warning" size={16} />{' '}
                  {t('chronicle:world.warning', 'The AI Storyteller reads this as the world. Changing it changes world generation, NPC behaviour and how characters are treated.')}
                </p>
                <Textarea label={t('chronicle:field.description', 'World and setting')} value={editDesc} onChange={(e) => setEditDesc(e.target.value)} rows={12} />
                <div className="sr-form__actions">
                  <Button variant="ghost" onClick={() => setEditDesc(null)}>
                    {t('common:cancel', 'Cancel')}
                  </Button>
                  <Button type="submit" variant="primary" loading={saving}>
                    {t('common:save', 'Save')}
                  </Button>
                </div>
              </form>
            ) : (
              <div className="sr-chronicle__world sr-prose">{campaign.description}</div>
            )}
          </Panel>

          <Panel title={t('chronicle:you.title', 'You in this chronicle')} icon="mask">
            <div className="sr-row sr-chronicle__you">
              {myCharacter ? (
                <>
                  <Avatar src={myCharacter.portrait_url} name={myCharacter.name} size={40} alt="" sigil="mask" />
                  <span>
                    <span className="sr-muted">{t('hall:youPlay', 'You play')} </span>
                    <strong>{myCharacter.name}</strong>
                  </span>
                  <Button size="sm" variant="ghost" icon="scroll" onClick={() => openSheet(myCharacter.id, campaign.game_system)}>
                    {t('play:panel.sheet', 'Character sheet')}
                  </Button>
                </>
              ) : (
                <>
                  <span className="sr-muted">{t('hall:noCharacter', 'No character in this chronicle yet')}</span>
                  <ButtonLink to="/profile/characters/new" size="sm" icon="plus">
                    {t('profile:characters.new', 'New character')}
                  </ButtonLink>
                </>
              )}
            </div>
            <p className="sr-muted sr-small">
              {t('chronicle:leave.body', 'Leaving keeps your character sheet. Joining a different chronicle later needs approval; you can rejoin this one while it stays open.')}
            </p>
            <Button variant="secondary" size="sm" icon="logout" onClick={() => setLeaveOpen(true)}>
              {t('chronicle:leave.button', 'Leave chronicle')}
            </Button>
          </Panel>

          <Panel title={t('chronicle:members.title', 'Members')} icon="users">
            <ul className="sr-members">
              {members.map((m) => (
                <li key={m.user_id} className="sr-member">
                  <Avatar src={(m.character && m.character.portrait_url) || m.player_avatar_url} name={m.username} size={32} alt="" />
                  <span className="sr-member__text">
                    <span className="sr-member__name">
                      {m.username}
                      {m.is_storyteller ? <Badge tone="gold" className="sr-ml"><Term id="storyteller">{t('chat:badge.storyteller', 'Storyteller')}</Term></Badge> : null}
                    </span>
                    <span className="sr-member__sub">
                      {m.character ? t('chronicle:members.plays', 'plays {{name}}', { name: m.character.name }) : t('play:panel.noChar', 'no character')}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            {staff ? (
              <div className="sr-stack sr-chronicle__sttools">
                <form className="sr-row sr-row--end" onSubmit={addMember}>
                  <Input
                    label={t('chronicle:members.addByName', 'Add a member (username)')}
                    autoComplete="off"
                    spellCheck={false}
                    value={addMemberId}
                    onChange={(e) => setAddMemberId(e.target.value)}
                    fieldClassName="sr-field--short"
                  />
                  <Button type="submit" size="md" variant="secondary" icon="plus">
                    {t('chronicle:members.add', 'Add')}
                  </Button>
                </form>
                <form className="sr-row sr-row--end" onSubmit={setPlaying}>
                  <Select
                    label={t('chronicle:members.pcPlayer', 'Player')}
                    value={pcUser}
                    onChange={(e) => {
                      setPcUser(e.target.value);
                      setPcChar('');
                    }}
                    placeholder={t('chronicle:members.pickPlayer', 'Choose a player')}
                    options={members.map((m) => ({ value: String(m.user_id), label: m.username }))}
                  />
                  {pcOptions.length ? (
                    <Select
                      label={t('chronicle:members.pcCharacter', 'Playing character')}
                      value={pcChar}
                      onChange={(e) => setPcChar(e.target.value)}
                      placeholder={t('chronicle:members.pickCharacter', 'Choose a character')}
                      options={pcOptions.map((c) => ({ value: String(c.id), label: c.name }))}
                    />
                  ) : pcUser ? (
                    <p className="sr-muted sr-small">{t('chronicle:members.pcNone', 'This player has no character in this chronicle yet.')}</p>
                  ) : null}
                  <Button type="submit" variant="secondary" disabled={!pcUser || !pcChar}>
                    {t('chronicle:members.pcApply', 'Set playing character')}
                  </Button>
                </form>
                <p className="sr-muted sr-small">
                  {t('chronicle:members.pcHint', 'Players switch characters in this chronicle only with Storyteller approval.')}
                </p>
              </div>
            ) : null}
          </Panel>

          {canManage ? (
            <Panel title={t('chronicle:enrollment.title', 'Open enrollment')} icon="key">
              <form className="sr-form" onSubmit={saveEnrollment} key={`enroll-${campaign.id}-${campaign.listing_visibility}-${campaign.accepting_players}-${campaign.max_players}`}>
                <Select
                  name="listing_visibility"
                  label={t('chronicle:enrollment.visibility', 'Visibility')}
                  defaultValue={campaign.listing_visibility || 'private'}
                  options={[
                    { value: 'private', label: t('chronicle:enrollment.private', 'Private (invite / admin only)') },
                    { value: 'listed', label: t('chronicle:enrollment.listed', 'Listed under “Open chronicles”') },
                  ]}
                />
                <Checkbox name="accepting_players" defaultChecked={!!campaign.accepting_players} label={t('chronicle:enrollment.accepting', 'Accepting new players (self-serve join)')} />
                <Input
                  type="number"
                  name="max_players"
                  min={0}
                  defaultValue={campaign.max_players != null ? campaign.max_players : 6}
                  label={t('chronicle:enrollment.max', 'Max players (0 = no limit)')}
                  fieldClassName="sr-field--short"
                />
                <div className="sr-form__actions">
                  <Button type="submit" variant="primary" loading={saving}>
                    {t('chronicle:enrollment.save', 'Save enrollment')}
                  </Button>
                </div>
              </form>
            </Panel>
          ) : null}

          {staff ? <LocationManager api={api} campaign={campaign} canEditAccess={canManage} toast={toast} onChanged={load} /> : null}

          {canManage ? (
            <Panel title={t('chronicle:danger.title', 'Danger zone')} icon="skull" className="sr-danger">
              <p className="sr-muted">{t('chronicle:delete.body', 'Deleting removes every room, character, message and roll of this chronicle. This cannot be undone.')}</p>
              <Button variant="danger" icon="trash" onClick={() => setDeleteOpen(true)}>
                {t('chronicle:delete.button', 'Delete chronicle')}
              </Button>
            </Panel>
          ) : null}
        </div>
      </PageBody>

      <Modal
        open={leaveOpen}
        onClose={() => setLeaveOpen(false)}
        title={t('chronicle:leave.title', 'Leave this chronicle?')}
        icon="logout"
        size="sm"
        description={t('chronicle:leave.body', 'Leaving keeps your character sheet. Joining a different chronicle later needs approval; you can rejoin this one while it stays open.')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setLeaveOpen(false)}>
              {t('common:cancel', 'Cancel')}
            </Button>
            <Button variant="danger" onClick={leave} loading={saving}>
              {t('chronicle:leave.confirm', 'Leave')}
            </Button>
          </>
        }
      />
      <Modal
        open={deleteOpen}
        onClose={() => {
          setDeleteOpen(false);
          setDeleteText('');
        }}
        title={t('chronicle:delete.title', 'Delete “{{name}}”?', { name: campaign.name })}
        icon="skull"
        size="sm"
        description={t('chronicle:delete.body', 'Deleting removes every room, character, message and roll of this chronicle. This cannot be undone.')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteOpen(false)}>
              {t('common:cancel', 'Cancel')}
            </Button>
            <Button variant="danger" icon="trash" disabled={!deleteMatches} loading={saving} onClick={destroy}>
              {t('chronicle:delete.confirm', 'Delete forever')}
            </Button>
          </>
        }
      >
        <Input
          label={t('chronicle:delete.typeName', 'Type the chronicle’s name, {{name}}, to confirm', { name: campaign?.name || '' })}
          value={deleteText}
          onChange={(e) => setDeleteText(e.target.value)}
          autoComplete="off"
          className="sr-mono"
        />
      </Modal>
    </div>
  );
}
