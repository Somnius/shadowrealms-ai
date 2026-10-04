/**
 * Developer style guide for the design system, mounted at /showcase/design (lazy). The public,
 * translated tour of the same parts is the theme preview at /showcase (src/pages/showcase).
 */
import { useState } from 'react';
import { Link } from 'react-router';
import {
  DesignProvider,
  MotionToggle,
  Glyph,
  GLYPH_GROUPS,
  GLYPHS,
  AnimatedCandle,
  BlinkingEye,
  AiSigil,
  DrippingBlood,
  SigilDraw,
  DieFace,
  Button,
  IconButton,
  Card,
  Panel,
  Badge,
  Avatar,
  Divider,
  EmptyState,
  Kbd,
  Spinner,
  Tabs,
  Tooltip,
  DotTrack,
  Input,
  Textarea,
  Select,
  Checkbox,
  Switch,
  Modal,
  Drawer,
  ToastProvider,
  useToast,
  FogLayer,
  CandleGlow,
  SigilReveal,
  DiceRollViz,
} from './index';

const GROUP_TITLES = {
  dice: 'Dice',
  horror: 'Horror',
  moon: 'Moons',
  room: 'Rooms',
  ui: 'Interface',
  line: 'Game lines',
  clan: 'Clan sigils (original art)',
  discipline: 'Disciplines (original art)',
};

function GlyphGallery() {
  return (
    <div className="pg-stack">
      {Object.keys(GLYPH_GROUPS).map((group) => (
        <section key={group}>
          <h3>{GROUP_TITLES[group] || group}</h3>
          <ul className="pg-glyphs">
            {GLYPH_GROUPS[group].map((name) => (
              <li key={name} className="pg-glyph">
                <Glyph name={name} size={32} title={GLYPHS[name].label} />
                <code>{name}</code>
              </li>
            ))}
          </ul>
        </section>
      ))}
      <section>
        <h3>Animated</h3>
        <div className="pg-row">
          <AnimatedCandle size={48} title="Candle" />
          <BlinkingEye size={48} title="Eye" />
          <AiSigil size={48} title="AI Storyteller" />
          <DrippingBlood size={48} title="Blood" />
          <SigilDraw name="clan-tzimisce" size={48} title="Draw-on sigil" />
        </div>
      </section>
      <section>
        <h3>Die faces</h3>
        <div className="pg-row">
          {[1, 4, 6, 10].map((v) => (
            <DieFace key={`n${v}`} value={v} />
          ))}
          {[1, 7, 10].map((v) => (
            <DieFace key={`h${v}`} value={v} hunger />
          ))}
        </div>
      </section>
    </div>
  );
}

function ToastButtons() {
  const { toast } = useToast();
  return (
    <div className="pg-row">
      <Button onClick={() => toast({ title: 'The raven arrives', body: 'The Storyteller left you a note.' })}>Info toast</Button>
      <Button variant="danger" onClick={() => toast({ tone: 'danger', title: 'Connection lost', body: 'Retrying…' })}>
        Error toast
      </Button>
    </div>
  );
}

function Components() {
  const [modal, setModal] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [dots, setDots] = useState(3);
  const [hunger, setHunger] = useState(2);
  const [sw, setSw] = useState(true);
  return (
    <div className="pg-stack">
      <div className="pg-row">
        <Button variant="primary" icon="send">
          Send
        </Button>
        <Button>Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="danger" icon="skull">
          Delete
        </Button>
        <Button variant="arcane" icon="ai-sigil">
          Ask the Storyteller
        </Button>
        <Button variant="primary" loading>
          Saving
        </Button>
        <Button size="sm">Small</Button>
        <Button size="lg" variant="primary">
          Large
        </Button>
        <IconButton icon="settings" label="Settings" />
        <IconButton icon="menu" label="Open menu" />
        <Tooltip content="Ctrl+K opens the quick switcher">
          <Button variant="ghost" icon="search">
            Search
          </Button>
        </Tooltip>
      </div>
      <div className="pg-row">
        <Badge>Neutral</Badge>
        <Badge tone="blood" icon="blood-drop">
          Hunger 3
        </Badge>
        <Badge tone="arcane">AI</Badge>
        <Badge tone="gold">ST</Badge>
        <Badge tone="ok">Online</Badge>
        <Badge tone="danger">Banned</Badge>
        <Badge count={7} />
        <Badge edition="V5" tone="blood" icon="line-vampire" />
        <Badge edition="V20" tone="gold">
          Revised
        </Badge>
      </div>
      <div className="pg-row">
        <Avatar name="Lucita Vey" presence="online" />
        <Avatar name="Old Man" size={32} presence="idle" />
        <Avatar size={80} sigil="clan-nosferatu" name="Gary" />
        <Avatar size={24} />
        <Spinner />
        <Spinner variant="candle" />
        <Spinner variant="ring" />
        <span>
          <Kbd>Ctrl</Kbd> + <Kbd>K</Kbd>
        </span>
      </div>
      <Divider />
      <div className="pg-grid">
        <Card ornate>
          <h3>Ornate card</h3>
          <p className="sr-prose">The city sleeps; you do not.</p>
        </Card>
        <Panel title="Panel" icon="scroll" actions={<IconButton icon="plus" label="Add" size="sm" />}>
          <DotTrack label="Strength" value={dots} onChange={setDots} />
          <DotTrack label="Hunger" value={hunger} onChange={setHunger} shape="square" />
          <DotTrack label="Blood Potency" value={2} max={10} readOnly tone="gold" />
          <DotTrack label="Dominate" value={2} locked={1} onChange={() => {}} />
        </Panel>
      </div>
      <div className="pg-grid">
        <Input label="Character name" hint="As the Storyteller will call you" icon="quill" />
        <Input label="Email" error="That address is already bound to another soul." defaultValue="lef@" />
        <Select
          label="Clan"
          placeholder="Choose…"
          defaultValue=""
          options={['Brujah', 'Gangrel', 'Malkavian', 'Nosferatu', 'Toreador', 'Tremere', 'Ventrue'].map((c) => ({ value: c, label: c }))}
        />
        <Textarea label="Backstory" placeholder="Before the Embrace…" />
        <Checkbox label="Hidden roll" hint="Only the Storyteller sees the dice" />
        <Switch label="Speak in character" checked={sw} onChange={setSw} />
      </div>
      <Tabs
        label="Character sheet"
        tabs={[
          { id: 'attr', label: 'Attributes', icon: 'user', content: <p>Physical, Social, Mental.</p> },
          { id: 'disc', label: 'Disciplines', icon: 'disc-auspex', content: <p>Powers of the blood.</p> },
          { id: 'notes', label: 'Notes', icon: 'book', content: <p>Secrets.</p> },
        ]}
      />
      <div className="pg-row">
        <Button onClick={() => setModal(true)}>Open modal</Button>
        <Button onClick={() => setDrawer(true)}>Open drawer</Button>
        <ToastButtons />
      </div>
      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title="Leave the chronicle?"
        icon="coffin"
        description="Your character stays; only your seat at the table is given up."
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(false)}>
              Stay
            </Button>
            <Button variant="danger" onClick={() => setModal(false)}>
              Leave
            </Button>
          </>
        }
      >
        <Input label="Type the chronicle name to confirm" />
      </Modal>
      <Drawer open={drawer} onClose={() => setDrawer(false)} title="Rooms">
        <EmptyState glyph="room-haven" title="No rooms yet" action={<Button variant="primary">Create a room</Button>}>
          The Storyteller hasn&apos;t opened any locations.
        </EmptyState>
      </Drawer>
    </div>
  );
}

function AtmosphereDemo() {
  const [key, setKey] = useState(0);
  return (
    <div className="pg-stack">
      <div className="pg-atmo">
        <FogLayer intensity={0.12} />
        <CandleGlow x="20%" y="60%" size={260} />
        <div style={{ position: 'relative', zIndex: 1, display: 'flex', alignItems: 'center', gap: 24 }}>
          <SigilReveal size={140} replayKey={key} />
          <Button onClick={() => setKey((k) => k + 1)}>Replay sigil</Button>
        </div>
      </div>
      <div className="pg-grid">
        <DiceRollViz edition="v5" normal={[10, 7, 3, 6]} hunger={[10, 2]} difficulty={3} rollKey={key} title="V5 — messy critical" />
        <DiceRollViz edition="v5" normal={[4, 3, 5]} hunger={[1, 2]} difficulty={2} rollKey={key} title="V5 — bestial failure" />
        <DiceRollViz edition="v5" normal={[10, 10, 8, 2, 6, 9]} hunger={[]} difficulty={4} rollKey={key} title="V5 — critical win" />
        <DiceRollViz edition="classic" dice={[1, 3, 4, 1, 2]} difficulty={6} rollKey={key} title="Classic — botch" />
        <DiceRollViz edition="classic" dice={[8, 9, 10, 7, 6, 6]} difficulty={6} rollKey={key} title="Classic — exceptional" />
      </div>
    </div>
  );
}

const PG_CSS = `
.pg { min-height: 100dvh; padding: 24px 16px 64px; max-width: 1200px; margin: 0 auto; }
.pg-stack { display: flex; flex-direction: column; gap: 24px; }
.pg-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.pg-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; align-items: start; }
.pg-glyphs { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: 8px; }
.pg-glyph { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 10px 4px; border: 1px solid var(--sr-border); border-radius: var(--sr-radius-md); color: var(--sr-text); }
.pg-glyph code { font-size: 11px; color: var(--sr-text-muted); text-align: center; overflow-wrap: anywhere; }
.pg-atmo { position: relative; overflow: hidden; min-height: 220px; padding: 32px; border: 1px solid var(--sr-border); border-radius: var(--sr-radius-lg); background: var(--sr-bg-deep); }
`;

export default function DesignPlayground() {
  const [line, setLine] = useState('vampire');
  const [lang, setLang] = useState('en');
  return (
    <DesignProvider line={line} lang={lang} className="pg">
      <ToastProvider>
        <style>{PG_CSS}</style>
        <header className="pg-row" style={{ justifyContent: 'space-between' }}>
          <h1 className="sr-caps">{lang === 'el' ? 'Σκιώδη Βασίλεια — οδηγός ύφους' : 'ShadowRealms style guide'}</h1>
          <div className="pg-row">
            <Link to="/showcase">{lang === 'el' ? 'Προεπισκόπηση θέματος' : 'Theme preview'}</Link>
            <MotionToggle />
            <Select
              label="Game line"
              hideLabel
              value={line}
              onChange={(e) => setLine(e.target.value)}
              options={['vampire', 'werewolf', 'mage'].map((v) => ({ value: v, label: v }))}
            />
            <Button variant="ghost" icon="globe" onClick={() => setLang((l) => (l === 'en' ? 'el' : 'en'))}>
              {lang === 'en' ? 'Ελληνικά' : 'English'}
            </Button>
          </div>
        </header>
        <p className="sr-prose">
          {lang === 'el'
            ? 'Καλησπέρα. Η νύχτα είναι νέα και η πόλη πεινάει· άυλα όνειρα, ευφυΐα και αίμα.'
            : 'Good evening. The night is young and the city is hungry.'}
        </p>
        <Divider label={lang === 'el' ? 'Σύμβολα' : 'Glyphs'} />
        <GlyphGallery />
        <Divider label={lang === 'el' ? 'Στοιχεία' : 'Components'} />
        <Components />
        <Divider label={lang === 'el' ? 'Ατμόσφαιρα' : 'Atmosphere'} />
        <AtmosphereDemo />
      </ToastProvider>
    </DesignProvider>
  );
}
