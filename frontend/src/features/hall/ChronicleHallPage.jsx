import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Avatar, Badge, Button, Card, ChronicleSigil, EmptyState, Spinner, useToast } from '../../design';
import { PageBody, TopBar } from '../../app/AppShell';
import ButtonLink from '../../app/ButtonLink';
import { useApi } from '../../app/AuthContext';
import { useChronicles } from '../../app/ChroniclesContext';
import { errorText } from '../../app/http';
import { lineOf } from '../../app/hooks';
import { editionLabel, editionOf } from '../../rules/rulesEdition';
import Footer from '../../components/Footer';
import { t } from '../../i18n';
import './hall.css';

function firstLine(text, max = 140) {
  const line = String(text || '').split('\n')[0];
  return line.length > max ? `${line.slice(0, max - 1)}…` : line;
}

function ChronicleCard({ c }) {
  const hasChar = !!(c.my_playing_character_name || '').trim();
  return (
    <li data-line={lineOf(c.game_system) || undefined}>
      <Card className="sr-hall__card sr-sigil-host" interactive>
        <div className="sr-hall__card-head">
          <span className="sr-hall__sigil" aria-hidden="true">
            <ChronicleSigil line={lineOf(c.game_system)} edition={editionOf(c)} size={52} />
          </span>
          <div className="sr-hall__card-title">
            <h2 className="sr-hall__name">
              <Link to={`/c/${c.id}`} className="sr-hall__link">
                {c.name}
              </Link>
            </h2>
            <div className="sr-hall__meta">
              <span className="sr-hall__system">{c.game_system}</span>
              <Badge edition={editionLabel(c)} tone="neutral" />
            </div>
          </div>
        </div>
        {c.description ? <p className="sr-hall__desc sr-prose">{firstLine(c.description)}</p> : null}
        <div className="sr-hall__char">
          {hasChar ? (
            <>
              <Avatar src={c.my_playing_character_portrait_url} name={c.my_playing_character_name} size={32} alt="" />
              <span>
                <span className="sr-muted">{t('hall:youPlay', 'You play')} </span>
                <strong>{c.my_playing_character_name}</strong>
              </span>
            </>
          ) : (
            <span className="sr-muted">{t('hall:noCharacter', 'No character in this chronicle yet')}</span>
          )}
        </div>
        <div className="sr-hall__actions">
          <ButtonLink to={`/c/${c.id}`} variant="primary" size="sm" icon="chevron-right">
            {t('hall:enter', 'Enter')}
          </ButtonLink>
          <ButtonLink to={`/chronicles/${c.id}`} variant="ghost" size="sm" icon="settings">
            {t('hall:details', 'Details & settings')}
          </ButtonLink>
        </div>
      </Card>
    </li>
  );
}

export default function ChronicleHallPage() {
  const api = useApi();
  const { toast } = useToast();
  const { chronicles, loaded, reload } = useChronicles();
  const [open, setOpen] = useState([]);
  const [joining, setJoining] = useState(null);

  const loadOpen = useCallback(async () => {
    const r = await api('/campaigns/discover');
    setOpen(r.ok && Array.isArray(r.data) ? r.data : []);
  }, [api]);

  useEffect(() => {
    reload();
    loadOpen();
  }, [reload, loadOpen]);

  const join = async (id) => {
    setJoining(id);
    const r = await api(`/campaigns/${id}/join`, { method: 'POST' });
    setJoining(null);
    if (!r.ok) {
      toast({
        tone: 'danger',
        title:
          r.data.error_code === 'join_requires_storyteller_approval'
            ? t('hall:join.needsApproval', 'Joining a new chronicle needs Storyteller approval.')
            : errorText(r.data, t('hall:join.failed', 'Could not join this chronicle')),
      });
      return;
    }
    toast({ tone: 'ok', title: t('hall:join.done', 'You joined the chronicle.') });
    reload();
    loadOpen();
  };

  return (
    <>
      <TopBar
        title={t('hall:title', 'Chronicle hall')}
        icon="logo-mark"
        actions={
          <ButtonLink to="/chronicles/new" variant="secondary" size="sm" icon="plus">
            {t('hall:create', 'New chronicle')}
          </ButtonLink>
        }
      />
      <PageBody>
        <section aria-labelledby="hall-mine">
          <h2 id="hall-mine" className="sr-section-title">
            {t('hall:mine', 'Your chronicles')}
          </h2>
          {!loaded ? (
            <Spinner label={t('common:loading', 'Loading')} />
          ) : chronicles.length === 0 ? (
            <EmptyState
              glyph="web"
              ambient
              title={t('hall:empty.title', 'No chronicles yet')}
              action={
                <ButtonLink to="/chronicles/new" variant="primary">
                  {t('hall:create', 'New chronicle')}
                </ButtonLink>
              }
            >
              {t('hall:empty.body', 'Create one, or join an open chronicle below.')}
            </EmptyState>
          ) : (
            <ul className="sr-hall__grid">
              {chronicles.map((c) => (
                <ChronicleCard key={c.id} c={c} />
              ))}
            </ul>
          )}
        </section>

        {open.length > 0 ? (
          <section aria-labelledby="hall-open" className="sr-hall__open">
            <h2 id="hall-open" className="sr-section-title">
              {t('hall:open.title', 'Open chronicles you can join')}
            </h2>
            <p className="sr-muted">
              {t('hall:open.body', 'Listed by their Storyteller and accepting players. Joining lets you create a character there.')}
            </p>
            <ul className="sr-hall__openlist">
              {open.map((dc) => (
                <li key={dc.id} className="sr-hall__openrow sr-sigil-host" data-line={lineOf(dc.game_system) || undefined}>
                  <ChronicleSigil line={lineOf(dc.game_system)} edition={editionOf(dc)} size={36} />
                  <div className="sr-hall__openinfo">
                    <strong>{dc.name}</strong>
                    <span className="sr-muted">
                      {dc.game_system} · {editionLabel(dc)}
                      {dc.max_players != null ? ` · ${t('hall:open.max', 'max {{n}} players', { n: dc.max_players })}` : ''}
                    </span>
                  </div>
                  <Button size="sm" variant="secondary" loading={joining === dc.id} onClick={() => join(dc.id)}>
                    {t('hall:open.join', 'Join')}
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        <div className="sr-hall__footer">
          <Footer />
        </div>
      </PageBody>
    </>
  );
}
