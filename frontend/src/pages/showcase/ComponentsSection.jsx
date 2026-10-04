import { useRef, useState } from 'react';
import {
  Avatar,
  Badge,
  Button,
  Checkbox,
  DotTrack,
  Drawer,
  EmptyState,
  IconButton,
  Input,
  Kbd,
  Modal,
  Panel,
  Select,
  Spinner,
  Switch,
  Tabs,
  Textarea,
  useAmbient,
  useOptionalToast,
} from '../../design';
import { t } from '../../i18n';
import { Section } from './parts';

const CLANS = ['Brujah', 'Gangrel', 'Malkavian', 'Nosferatu', 'Toreador', 'Tremere', 'Ventrue', 'Banu Haqim', 'Hecata', 'Lasombra', 'Ministry', 'Caitiff'];

function Trackers() {
  const [hunger, setHunger] = useState(2);
  const [humanity, setHumanity] = useState(7);
  const [willpower, setWillpower] = useState(5);
  return (
    <Panel title={t('showcase:comp.trackers', 'Trackers')} icon="blood-drop" headingLevel={3} data-testid="trackers">
      <div className="sc-stack">
        <DotTrack label={t('showcase:comp.hunger', 'Hunger')} value={hunger} onChange={setHunger} max={5} shape="square" tone="blood" showValue />
        <DotTrack label={t('showcase:comp.humanity', 'Humanity')} value={humanity} onChange={setHumanity} max={10} tone="gold" showValue />
        <DotTrack label={t('showcase:comp.willpower', 'Willpower')} value={willpower} onChange={setWillpower} max={10} tone="arcane" showValue />
        <DotTrack label={t('showcase:comp.bloodPotency', 'Blood Potency')} value={2} max={10} readOnly tone="gold" />
      </div>
      <p className="sc-hint">{t('showcase:comp.trackersHint', 'Focus a track and use the arrow keys, Home, End or a digit.')}</p>
    </Panel>
  );
}

function Sheet() {
  const [str, setStr] = useState(3);
  const [dex, setDex] = useState(2);
  const [sta, setSta] = useState(2);
  const [aus, setAus] = useState(2);
  return (
    <Panel title={t('showcase:comp.sheet', 'Character sheet')} icon="scroll" headingLevel={3}>
      <Tabs
        label={t('showcase:comp.sheet', 'Character sheet')}
        tabs={[
          {
            id: 'attr',
            label: t('showcase:comp.attributes', 'Attributes'),
            icon: 'user',
            content: (
              <div className="sc-stack">
                <DotTrack label="Strength" value={str} onChange={setStr} locked={1} />
                <DotTrack label="Dexterity" value={dex} onChange={setDex} locked={1} />
                <DotTrack label="Stamina" value={sta} onChange={setSta} locked={1} />
              </div>
            ),
          },
          {
            id: 'disc',
            label: t('showcase:comp.disciplines', 'Disciplines'),
            icon: 'disc-auspex',
            content: (
              <div className="sc-stack">
                <DotTrack label="Auspex" value={aus} onChange={setAus} tone="arcane" />
                <DotTrack label="Dominate" value={1} readOnly tone="arcane" />
                <DotTrack label="Blood Sorcery" value={0} readOnly tone="arcane" />
              </div>
            ),
          },
          {
            id: 'notes',
            label: t('showcase:comp.notes', 'Notes'),
            icon: 'book',
            content: <p className="sr-prose sc-quote">{t('showcase:comp.notesText', 'Owes a boon to the Harpy. Do not go to the docks after the second bell.')}</p>,
          },
        ]}
      />
    </Panel>
  );
}

function Overlays() {
  const toast = useOptionalToast();
  const [modal, setModal] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const say = (opts) => toast && toast.toast(opts);
  return (
    <Panel title={t('showcase:comp.overlays', 'Dialogs and notices')} icon="bell" headingLevel={3}>
      <div className="sc-row">
        <Button onClick={() => setModal(true)} icon="coffin" data-testid="open-modal">
          {t('showcase:comp.openModal', 'Open a dialog')}
        </Button>
        <Button onClick={() => setDrawer(true)} icon="menu">
          {t('showcase:comp.openDrawer', 'Open a drawer')}
        </Button>
      </div>
      <div className="sc-row">
        <Button
          size="sm"
          variant="ghost"
          icon="raven"
          onClick={() => say({ title: t('showcase:comp.toastInfoTitle', 'A raven arrives'), body: t('showcase:comp.toastInfoBody', 'The Storyteller left you a note.') })}
        >
          {t('showcase:comp.toastInfo', 'Notice')}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          icon="check"
          onClick={() => say({ tone: 'ok', title: t('showcase:comp.toastOkTitle', 'Character saved'), body: t('showcase:comp.toastOkBody', 'Mara Voss is ready for tonight.') })}
        >
          {t('showcase:comp.toastOk', 'Success')}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          icon="skull"
          onClick={() => say({ tone: 'danger', title: t('showcase:comp.toastErrTitle', 'Connection lost'), body: t('showcase:comp.toastErrBody', 'Trying again in a few seconds…') })}
        >
          {t('showcase:comp.toastErr', 'Error')}
        </Button>
      </div>
      <div className="sc-row sc-row--center">
        <Avatar name="Mara Voss" presence="online" />
        <Avatar name="Jonah Crane" size={32} presence="idle" />
        <Avatar size={48} sigil="clan-nosferatu" name="Gary" />
        <Spinner label={t('showcase:comp.loading', 'Loading')} />
        <Spinner variant="candle" label={t('showcase:comp.loading', 'Loading')} />
        <Spinner variant="ring" label={t('showcase:comp.loading', 'Loading')} />
      </div>
      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title={t('showcase:comp.modalTitle', 'Leave the chronicle?')}
        icon="coffin"
        description={t('showcase:comp.modalBody', 'Your character stays; only your seat at the table is given up.')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(false)}>
              {t('showcase:comp.stay', 'Stay')}
            </Button>
            <Button variant="danger" onClick={() => setModal(false)}>
              {t('showcase:comp.leave', 'Leave')}
            </Button>
          </>
        }
      >
        <Input label={t('showcase:comp.confirm', 'Type the chronicle name to confirm')} />
      </Modal>
      <Drawer open={drawer} onClose={() => setDrawer(false)} title={t('showcase:comp.drawerTitle', 'Rooms')}>
        <EmptyState glyph="room-haven" title={t('showcase:comp.drawerEmpty', 'No rooms yet')} action={<Button variant="primary">{t('showcase:comp.drawerAction', 'Create a room')}</Button>}>
          {t('showcase:comp.drawerBody', 'The Storyteller hasn’t opened any locations.')}
        </EmptyState>
      </Drawer>
    </Panel>
  );
}

export default function ComponentsSection() {
  const [ic, setIc] = useState(true);
  const gridRef = useRef(null);
  const { paused } = useAmbient(gridRef); // spinners and animated glyphs stop off-screen
  return (
    <Section
      id="components"
      numeral="IV"
      kicker={t('showcase:comp.kicker', 'Built to be used, not just looked at')}
      title={t('showcase:comp.title', 'The tools of the night')}
      lede={t(
        'showcase:comp.lede',
        'Buttons, fields, tabs, badges, trackers, dialogs and notices. Each one has a visible focus ring, works with the keyboard and reads well with a screen reader.'
      )}
    >
      <p className="sc-keys">
        <Kbd>Tab</Kbd> <Kbd>←</Kbd> <Kbd>→</Kbd> <Kbd>Home</Kbd> <Kbd>End</Kbd> <Kbd>Esc</Kbd>
        <span>{t('showcase:comp.keys', 'Everything below works without a mouse.')}</span>
      </p>
      <div className="sc-comp-grid" ref={gridRef} data-paused={paused ? 'true' : undefined}>
        <Panel title={t('showcase:comp.buttons', 'Buttons')} icon="dagger" headingLevel={3}>
          <div className="sc-row">
            <Button variant="primary" icon="send">
              {t('showcase:comp.send', 'Send')}
            </Button>
            <Button variant="arcane" icon="ai-sigil">
              {t('showcase:comp.ask', 'Ask the Storyteller')}
            </Button>
            <Button>{t('showcase:comp.secondary', 'Secondary')}</Button>
            <Button variant="ghost">{t('showcase:comp.ghost', 'Ghost')}</Button>
            <Button variant="danger" icon="trash">
              {t('showcase:comp.delete', 'Delete')}
            </Button>
            <Button variant="primary" loading loadingLabel={t('showcase:comp.saving', 'Saving')}>
              {t('showcase:comp.saving', 'Saving')}
            </Button>
            <Button disabled>{t('showcase:comp.disabled', 'Disabled')}</Button>
          </div>
          <div className="sc-row sc-row--center">
            <Button size="sm">{t('showcase:comp.small', 'Small')}</Button>
            <Button size="md">{t('showcase:comp.medium', 'Medium')}</Button>
            <Button size="lg" variant="primary">
              {t('showcase:comp.large', 'Large')}
            </Button>
            <IconButton icon="settings" label={t('showcase:comp.settings', 'Settings')} />
            <IconButton icon="bell" label={t('showcase:comp.notifications', 'Notifications')} />
            <IconButton icon="search" label={t('showcase:comp.search', 'Search')} />
          </div>
        </Panel>

        <Panel title={t('showcase:comp.badges', 'Badges and editions')} icon="crown" headingLevel={3}>
          <div className="sc-row">
            <Badge lang="en" edition="V5" tone="blood" icon="line-vampire" />
            <Badge lang="en" edition="V20" tone="gold" icon="book" />
            <Badge lang="en" edition="Revised" tone="neutral" icon="scroll" />
            <Badge lang="en" edition="W20" tone="gold" icon="line-werewolf" />
            <Badge lang="en" edition="M20" tone="arcane" icon="line-mage" />
          </div>
          <div className="sc-row">
            <Badge tone="blood" icon="blood-drop">
              {t('showcase:comp.badgeHunger', 'Hunger 3')}
            </Badge>
            <Badge tone="arcane" icon="ai-sigil">
              {t('showcase:comp.badgeAi', 'AI')}
            </Badge>
            <Badge tone="gold" icon="crown-thorns">
              {t('showcase:comp.badgeSt', 'Storyteller')}
            </Badge>
            <Badge tone="ok">{t('showcase:comp.badgeOnline', 'Online')}</Badge>
            <Badge tone="warn">{t('showcase:comp.badgeAway', 'Away')}</Badge>
            <Badge tone="danger">{t('showcase:comp.badgeBanned', 'Banned')}</Badge>
            <Badge count={7} tone="blood" />
            <Badge count={128} />
          </div>
        </Panel>

        <Trackers />
        <Sheet />

        <Overlays />
        <Panel title={t('showcase:comp.fields', 'Fields')} icon="quill" headingLevel={3}>
          <div className="sc-stack">
            <Input label={t('showcase:comp.charName', 'Character name')} hint={t('showcase:comp.charNameHint', 'As the Storyteller will call you')} icon="quill" defaultValue="Mara Voss" />
            <Input label={t('showcase:comp.email', 'Email')} error={t('showcase:comp.emailError', 'That address is already bound to another soul.')} defaultValue="mara@" />
            <Select
              label={t('showcase:comp.clan', 'Clan')}
              defaultValue="Toreador"
              options={CLANS.map((c) => ({ value: c, label: c }))}
            />
            <Textarea label={t('showcase:comp.backstory', 'Backstory')} placeholder={t('showcase:comp.backstoryPh', 'Before the Embrace…')} rows={3} />
            <Checkbox label={t('showcase:comp.hidden', 'Hidden roll')} hint={t('showcase:comp.hiddenHint', 'Only the Storyteller sees the dice')} />
            <Switch label={t('showcase:comp.ic', 'Speak in character')} checked={ic} onChange={setIc} />
          </div>
        </Panel>

      </div>
    </Section>
  );
}
