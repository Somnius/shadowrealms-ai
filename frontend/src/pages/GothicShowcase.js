import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  GothicBox,
  SkullDivider,
  OrnateDivider,
  GothicButton,
  FloatingParticles,
  MagicCircle,
  BloodSplatter,
} from '../components/GothicDecorations';
import { GothicPageLoadingOverlay, SessionRevealOverlay } from '../components/ThemeOverlays';
import DemoDiceRollerModal from '../components/DemoDiceRollerModal';

/** Small portrait placeholder — matches dashboard campaign cards. */
function ShowcaseCharAvatar({ name }) {
  return (
    <div
      style={{
        width: 36,
        height: 36,
        borderRadius: 8,
        flexShrink: 0,
        border: '1px solid #2a2a4e',
        background: 'linear-gradient(135deg, #334155 0%, #1e293b 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '18px',
      }}
      aria-hidden
    >
      {name ? name.trim().charAt(0).toUpperCase() : '?'}
    </div>
  );
}

const GothicShowcase = ({ onBack }) => {
  const [loadingVeil, setLoadingVeil] = useState({ visible: false, label: '' });
  const [sessionReveal, setSessionReveal] = useState({
    visible: false,
    title: '',
    subtitle: '',
  });
  const [diceModalOpen, setDiceModalOpen] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  const timersRef = useRef([]);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach((id) => window.clearTimeout(id));
    timersRef.current = [];
  }, []);

  useEffect(() => () => clearTimers(), [clearTimers]);

  const schedule = (fn, ms) => {
    const id = window.setTimeout(fn, ms);
    timersRef.current.push(id);
    return id;
  };

  const runLoginVeilDemo = () => {
    if (demoBusy) return;
    setDemoBusy(true);
    setLoadingVeil({ visible: true, label: 'The gates recognize your name…' });
    schedule(() => {
      setLoadingVeil({ visible: true, label: 'Summoning your chronicles…' });
    }, 1400);
    schedule(() => {
      setLoadingVeil({ visible: false, label: '' });
      setDemoBusy(false);
    }, 3200);
  };

  const runWelcomeRevealDemo = () => {
    if (demoBusy) return;
    setDemoBusy(true);
    setSessionReveal({
      visible: true,
      title: 'Welcome back, storyteller',
      subtitle: 'Your chronicles stir in the dark.',
    });
    schedule(() => {
      setSessionReveal({ visible: false, title: '', subtitle: '' });
      setDemoBusy(false);
    }, 1650);
  };

  const runEnterChronicleDemo = () => {
    if (demoBusy) return;
    setDemoBusy(true);
    setLoadingVeil({ visible: true, label: 'Crossing into the chronicle…' });
    schedule(() => {
      setLoadingVeil({ visible: true, label: 'Gathering places and whispers…' });
    }, 1100);
    schedule(() => {
      setLoadingVeil({ visible: false, label: '' });
      setSessionReveal({
        visible: true,
        title: 'The chronicle opens',
        subtitle: 'Same veil & reveal as when you hit Enter on a campaign.',
      });
    }, 2800);
    schedule(() => {
      setSessionReveal({ visible: false, title: '', subtitle: '' });
      setDemoBusy(false);
    }, 4500);
  };

  return (
    <div className="sr-showcase-page">
      <GothicPageLoadingOverlay visible={loadingVeil.visible} label={loadingVeil.label} />
      <SessionRevealOverlay
        visible={sessionReveal.visible}
        title={sessionReveal.title}
        subtitle={sessionReveal.subtitle}
      />
      {diceModalOpen && <DemoDiceRollerModal onClose={() => setDiceModalOpen(false)} />}

      <div className="sr-showcase-bg-wrap" aria-hidden>
        <div className="sr-login-gate-bg" />
        <div className="sr-login-gate-vignette" />
        <div className="sr-login-gate-orbs" />
      </div>

      <FloatingParticles count={18} />
      <BloodSplatter style={{ top: '8%', left: '4%', width: '48px', height: '48px', opacity: 0.85 }} />
      <BloodSplatter style={{ top: '28%', right: '8%', width: '38px', height: '38px', opacity: 0.75 }} />
      <BloodSplatter style={{ bottom: '18%', left: '12%', width: '56px', height: '56px', opacity: 0.7 }} />
      <MagicCircle style={{ top: '12%', right: '6%' }} />
      <MagicCircle style={{ bottom: '26%', left: '6%' }} />

      <div className="sr-showcase-inner">
        <header className="sr-showcase-hero">
          <h1>
            <i className="fas fa-skull" /> ShadowRealms AI — Gothic theme preview
          </h1>
          <p>
            Live demos use the same overlays and CSS as the app: login veil, post-auth welcome card, chronicle
            entry, and colors from <code style={{ color: '#a78bfa' }}>gothic-theme.css</code> (login gate, session
            reveal, dashboard entrance).
          </p>
          <button
            type="button"
            onClick={onBack}
            style={{
              marginTop: '8px',
              padding: '12px 28px',
              background: 'rgba(22, 33, 62, 0.9)',
              border: '2px solid #e94560',
              color: '#e94560',
              borderRadius: '10px',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '16px',
              fontFamily: 'Cinzel, serif',
              boxShadow: '0 4px 20px rgba(233, 69, 96, 0.25)',
            }}
          >
            ← Back to login
          </button>
        </header>

        <div className="sr-showcase-demo-strip">
          <span>Interactive demos</span>
          <button
            type="button"
            disabled={demoBusy}
            onClick={runLoginVeilDemo}
            style={demoBtnStyle(demoBusy)}
          >
            Login loading veil
          </button>
          <button
            type="button"
            disabled={demoBusy}
            onClick={runWelcomeRevealDemo}
            style={demoBtnStyle(demoBusy)}
          >
            Post-login welcome
          </button>
          <button
            type="button"
            disabled={demoBusy}
            onClick={runEnterChronicleDemo}
            style={demoBtnStyle(demoBusy)}
          >
            Enter chronicle (veil + reveal)
          </button>
          <button
            type="button"
            onClick={() => setDiceModalOpen(true)}
            style={demoBtnStyle(false, '#9d4edd')}
          >
            Dice roller (demo modal)
          </button>
        </div>

        {/* Mini login gate — same layers as / login */}
        <section style={{ marginBottom: '2.5rem' }}>
          <h2
            style={{
              fontFamily: 'Cinzel, serif',
              color: '#e94560',
              fontSize: '1.35rem',
              marginBottom: '12px',
              textAlign: 'center',
            }}
          >
            Login screen atmosphere (current build)
          </h2>
          <p style={{ textAlign: 'center', color: '#94a3b8', marginBottom: '16px', maxWidth: '40rem', marginLeft: 'auto', marginRight: 'auto', lineHeight: 1.55 }}>
            Drifting gradients, vignette, and orbs match the real gate. The form below is static (showcase only).
          </p>
          <div className="sr-showcase-login-preview">
            <div className="sr-login-gate-bg" style={{ position: 'absolute', inset: 0 }} />
            <div className="sr-login-gate-vignette" style={{ position: 'absolute', inset: 0 }} />
            <div className="sr-login-gate-orbs" style={{ position: 'absolute', inset: 0 }} />
            <div
              className="sr-login-gate-content"
              style={{ position: 'relative', zIndex: 2, minHeight: 280, justifyContent: 'center' }}
            >
              <div className="sr-login-brand" style={{ textAlign: 'center', padding: '24px 20px' }}>
                <h3
                  style={{
                    color: '#e94560',
                    fontFamily: 'Cinzel, serif',
                    fontSize: '1.5rem',
                    margin: '0 0 8px',
                    textShadow: '0 0 20px rgba(233, 69, 96, 0.35)',
                  }}
                >
                  ShadowRealms AI
                </h3>
                <p style={{ color: '#94a3b8', margin: 0, fontFamily: 'Crimson Text, serif', fontSize: '1.05rem' }}>
                  Step through the veil — chronicles, dice, and an AI Storyteller await.
                </p>
              </div>
            </div>
          </div>
        </section>

        <SkullDivider />

        <GothicBox theme="vampire" style={{ background: '#16213e', padding: '36px', borderRadius: '12px', marginBottom: '36px' }}>
          <h2 style={{ color: '#e94560', marginBottom: '8px', fontSize: '1.5rem', fontFamily: 'Cinzel, serif', textAlign: 'center' }}>
            <i className="fas fa-book-dead" /> Sign your pact
          </h2>
          <p style={{ color: '#94a3b8', textAlign: 'center', marginBottom: '22px', fontSize: '15px' }}>
            Styled like the real login card — Crimson inputs, Cinzel actions.
          </p>
          <form style={{ maxWidth: '400px', margin: '0 auto' }} onSubmit={(e) => e.preventDefault()}>
            <label style={{ display: 'block', marginBottom: '8px', color: '#b5b5c3', fontFamily: 'Crimson Text, serif' }}>
              <i className="fas fa-user-secret" /> Username
            </label>
            <input
              type="text"
              readOnly
              placeholder="Enter the shadows…"
              style={inputStyle}
            />
            <label style={{ display: 'block', marginBottom: '8px', marginTop: '16px', color: '#b5b5c3', fontFamily: 'Crimson Text, serif' }}>
              <i className="fas fa-key" /> Password
            </label>
            <input type="password" readOnly placeholder="••••••••" style={inputStyle} />
            <GothicButton
              type="button"
              style={{
                width: '100%',
                marginTop: '22px',
                padding: '14px',
                background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
                border: 'none',
                borderRadius: '8px',
                color: 'white',
                fontSize: '17px',
                fontWeight: 'bold',
                cursor: 'default',
                fontFamily: 'Cinzel, serif',
                boxShadow: '0 5px 22px rgba(233, 69, 96, 0.35)',
              }}
            >
              <i className="fas fa-sign-in-alt" /> Enter the darkness
            </GothicButton>
          </form>
        </GothicBox>

        <OrnateDivider icon="dragon" />

        <h2 style={{ fontFamily: 'Cinzel, serif', color: '#e0e0e0', textAlign: 'center', marginBottom: '20px', fontSize: '1.35rem' }}>
          Chronicle hall cards (dashboard look)
        </h2>
        <p style={{ textAlign: 'center', color: '#94a3b8', marginBottom: '22px', maxWidth: '42rem', marginLeft: 'auto', marginRight: 'auto', lineHeight: 1.55 }}>
          Ribbon, game line, description, <strong style={{ color: '#cbd5e1' }}>playing character</strong> row with portrait + name, then Settings / Enter.
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '22px',
            marginBottom: '36px',
          }}
        >
          <CampaignCardDemo
            themeColor={{ primary: '#e94560', bg: 'rgba(233, 69, 96, 0.12)', shadow: 'rgba(233, 69, 96, 0.35)' }}
            gameLine="Vampire: The Masquerade"
            title="One drop of blood rules them all"
            description="Setting: Greece, 2025 — wild lands shrinking, the Camarilla tightens its grip…"
            charName="Yorika"
            onEnterDemo={runEnterChronicleDemo}
            demoBusy={demoBusy}
          />
          <CampaignCardDemo
            themeColor={{ primary: '#9d4edd', bg: 'rgba(157, 78, 221, 0.12)', shadow: 'rgba(157, 78, 221, 0.35)' }}
            gameLine="Mage: The Ascension"
            title="Consensus fracture"
            description="Reality bends — same card chrome, different accent."
            charName={null}
            onEnterDemo={runEnterChronicleDemo}
            demoBusy={demoBusy}
          />
        </div>

        <SkullDivider />

        <GothicBox theme="werewolf" style={{ background: '#16213e', padding: '28px', borderRadius: '12px', marginBottom: '36px' }}>
          <h3 style={{ color: '#fbbf24', marginBottom: '12px', fontSize: '1.35rem', fontFamily: 'Cinzel, serif' }}>
            <i className="fas fa-wolf" /> Werewolf: The Apocalypse
          </h3>
          <p style={{ color: '#b5b5c3', lineHeight: 1.75, fontFamily: 'Crimson Text, serif', marginBottom: '16px' }}>
            Rage, Wyrm, Gaia — orange accent tokens match the live chronicle picker.
          </p>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '14px' }}>
            <span style={tagStyle('#d97706')}>
              <i className="fas fa-moon" /> Rage
            </span>
            <span style={tagStyle('#e94560')}>
              <i className="fas fa-paw" /> Garou
            </span>
          </div>
          <GothicButton
            type="button"
            onClick={runEnterChronicleDemo}
            disabled={demoBusy}
            style={{
              width: '100%',
              padding: '12px',
              background: demoBusy ? '#555' : '#d97706',
              border: 'none',
              borderRadius: '8px',
              color: 'white',
              fontWeight: 'bold',
              cursor: demoBusy ? 'not-allowed' : 'pointer',
              fontFamily: 'Cinzel, serif',
            }}
          >
            <i className="fas fa-door-open" /> Run enter-chronicle demo
          </GothicButton>
        </GothicBox>

        <OrnateDivider icon="feather-alt" />

        <GothicBox style={{ background: '#16213e', padding: '28px', borderRadius: '12px', marginBottom: '36px' }}>
          <h2 style={{ color: '#e94560', marginBottom: '18px', fontSize: '1.4rem', fontFamily: 'Cinzel, serif', textAlign: 'center' }}>
            <i className="fas fa-comments" /> In-character hall (sample)
          </h2>
          <div
            style={{
              background: '#0f1729',
              border: '2px solid #2a2a4e',
              borderRadius: '10px',
              padding: '18px',
              marginBottom: '16px',
              maxHeight: '280px',
              overflowY: 'auto',
            }}
          >
            {[
              { user: 'Storyteller', msg: '*Rain hammers the Elysium shutters.*', type: 'ai' },
              { user: 'Yorika', msg: 'I keep my voice low. "Who called this court?"', type: 'player' },
              { user: 'Marcus', msg: 'The Prince arrives within the hour.', type: 'npc' },
            ].map((m, i) => (
              <div
                key={i}
                style={{
                  marginBottom: '12px',
                  padding: '12px',
                  background:
                    m.type === 'ai' ? 'rgba(157, 78, 221, 0.1)' : m.type === 'npc' ? 'rgba(233, 69, 96, 0.1)' : 'rgba(100, 116, 139, 0.08)',
                  borderLeft: `3px solid ${m.type === 'ai' ? '#9d4edd' : m.type === 'npc' ? '#e94560' : '#14b8a6'}`,
                  borderRadius: '6px',
                }}
              >
                <div
                  style={{
                    fontWeight: 'bold',
                    color: m.type === 'ai' ? '#c4b5fd' : m.type === 'npc' ? '#e94560' : '#5eead4',
                    marginBottom: '6px',
                    fontFamily: 'Cinzel, serif',
                    fontSize: '14px',
                  }}
                >
                  {m.user}
                </div>
                <div style={{ color: '#d4d4d8', fontFamily: 'Crimson Text, serif', fontStyle: m.type === 'ai' ? 'italic' : 'normal' }}>{m.msg}</div>
              </div>
            ))}
          </div>
          <form style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }} onSubmit={(e) => e.preventDefault()}>
            <input type="text" readOnly placeholder="Whisper to the darkness…" style={{ ...inputStyle, flex: 1, minWidth: '200px' }} />
            <GothicButton
              type="button"
              style={{
                padding: '12px 22px',
                background: '#e94560',
                border: 'none',
                borderRadius: '8px',
                color: 'white',
                fontWeight: 'bold',
                fontFamily: 'Cinzel, serif',
                cursor: 'default',
              }}
            >
              <i className="fas fa-paper-plane" /> Send
            </GothicButton>
          </form>
        </GothicBox>

        <OrnateDivider icon="skull-crossbones" />

        <GothicBox style={{ background: '#16213e', padding: '28px', borderRadius: '12px', marginBottom: '36px' }}>
          <h2 style={{ color: '#e94560', marginBottom: '18px', fontSize: '1.35rem', fontFamily: 'Cinzel, serif', textAlign: 'center' }}>
            <i className="fas fa-crown" /> Admin strip (sample)
          </h2>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'Crimson Text, serif' }}>
              <thead>
                <tr style={{ background: '#0f1729' }}>
                  {['Kindred', 'Clan', 'Privileges', 'Status'].map((h) => (
                    <th key={h} style={{ padding: '12px', border: '1px solid #2a2a4e', textAlign: 'left', color: '#e94560', fontFamily: 'Cinzel, serif' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr style={{ background: '#1a1a2e' }}>
                  <td style={tdStyle}>A. Player</td>
                  <td style={tdStyle}>Toreador</td>
                  <td style={tdStyle}>
                    <span style={{ padding: '3px 8px', borderRadius: '8px', fontSize: '11px', background: 'rgba(167, 139, 250, 0.2)', color: '#e9d5ff', border: '1px solid #a78bfa' }}>
                      Helper ST
                    </span>
                  </td>
                  <td style={{ ...tdStyle, color: '#4ade80' }}>Active</td>
                </tr>
              </tbody>
            </table>
          </div>
        </GothicBox>

        <GothicBox style={{ background: '#16213e', padding: '28px', borderRadius: '12px', marginBottom: '28px', textAlign: 'center' }}>
          <h1 style={{ fontFamily: 'Cinzel, serif', color: '#e94560', fontSize: '1.75rem', marginBottom: '10px' }}>Cinzel · Crimson Text</h1>
          <p style={{ fontFamily: 'Crimson Text, serif', color: '#94a3b8', fontSize: '1.1rem', fontStyle: 'italic', margin: 0 }}>
            Titles in Cinzel, body in Crimson — matching production.
          </p>
        </GothicBox>

        <footer style={{ textAlign: 'center', marginTop: '40px', paddingTop: '28px', borderTop: '2px solid #2a2a4e' }}>
          <p style={{ color: '#94a3b8', fontSize: '17px', fontFamily: 'Crimson Text, serif', fontStyle: 'italic', margin: '0 0 12px' }}>
            Record your readme video here — demos above match the live app overlays and palette.
          </p>
          <div style={{ fontSize: '14px', color: '#64748b' }}>
            <i className="fas fa-moon" /> ShadowRealms AI
          </div>
        </footer>
      </div>
    </div>
  );
};

function demoBtnStyle(disabled, accent = '#e94560') {
  return {
    padding: '10px 16px',
    borderRadius: '10px',
    border: `2px solid ${disabled ? '#3f3f55' : accent}`,
    background: disabled ? 'rgba(30, 30, 45, 0.6)' : `linear-gradient(135deg, ${accent}22 0%, rgba(15, 23, 41, 0.95) 100%)`,
    color: disabled ? '#6b7280' : '#f1f5f9',
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontFamily: 'Cinzel, serif',
    fontWeight: 600,
    fontSize: '13px',
    boxShadow: disabled ? 'none' : `0 4px 16px ${accent}33`,
  };
}

const inputStyle = {
  width: '100%',
  padding: '12px',
  background: '#0f1729',
  border: '2px solid #2a2a4e',
  borderRadius: '8px',
  color: '#e2e8f0',
  fontSize: '16px',
  fontFamily: 'Crimson Text, serif',
  boxSizing: 'border-box',
};

const tdStyle = { padding: '12px', border: '1px solid #2a2a4e', color: '#d0d0d0' };

function tagStyle(color) {
  return {
    padding: '5px 12px',
    background: `${color}22`,
    border: `1px solid ${color}`,
    borderRadius: '15px',
    fontSize: '12px',
    color,
  };
}

function CampaignCardDemo({
  themeColor,
  gameLine,
  title,
  description,
  charName,
  onEnterDemo,
  demoBusy,
}) {
  const short = description.length > 120 ? `${description.slice(0, 118)}…` : description;
  return (
    <div
      style={{
        position: 'relative',
        background: '#16213e',
        padding: '22px',
        borderRadius: '12px',
        border: '2px solid #2a2a4e',
        boxShadow: '0 4px 18px rgba(0,0,0,0.45)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: '240px',
        transition: 'transform 0.2s, border-color 0.2s, box-shadow 0.2s',
      }}
      onMouseOver={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)';
        e.currentTarget.style.borderColor = themeColor.primary;
        e.currentTarget.style.boxShadow = `0 8px 28px ${themeColor.shadow}`;
      }}
      onMouseOut={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.borderColor = '#2a2a4e';
        e.currentTarget.style.boxShadow = '0 4px 18px rgba(0,0,0,0.45)';
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: '12px',
          left: '-8px',
          background: `linear-gradient(135deg, ${themeColor.primary} 0%, ${themeColor.primary}cc 100%)`,
          color: 'white',
          padding: '6px 20px 6px 14px',
          fontSize: '11px',
          fontWeight: 'bold',
          fontFamily: 'Cinzel, serif',
          textTransform: 'uppercase',
          letterSpacing: '1px',
          borderRadius: '0 6px 6px 0',
          boxShadow: `0 4px 12px ${themeColor.shadow}`,
        }}
      >
        {gameLine.split(':')[0].trim()}
      </div>
      <div style={{ marginTop: '36px' }}>
        <h3 style={{ color: themeColor.primary, margin: '0 0 10px', fontSize: '1.15rem', fontFamily: 'Cinzel, serif', lineHeight: 1.3 }}>{title}</h3>
        <p style={{ color: '#b5b5c3', margin: 0, fontSize: '14px', lineHeight: 1.5, fontFamily: 'Crimson Text, serif' }}>{short}</p>
      </div>
      <div
        style={{
          marginTop: '12px',
          paddingTop: '12px',
          borderTop: '1px solid #2a2a4e',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          minHeight: '40px',
        }}
      >
        {charName ? (
          <>
            <ShowcaseCharAvatar name={charName} />
            <span style={{ color: '#e2e8f0', fontSize: '14px', fontFamily: 'Crimson Text, serif', fontWeight: 600 }}>{charName}</span>
          </>
        ) : (
          <span style={{ color: '#64748b', fontSize: '13px', fontStyle: 'italic', fontFamily: 'Crimson Text, serif' }}>
            No character attached to chronicle
          </span>
        )}
      </div>
      <div style={{ display: 'flex', gap: '10px', marginTop: '14px' }}>
        <button
          type="button"
          style={{
            flex: 1,
            padding: '8px 12px',
            background: themeColor.bg,
            color: themeColor.primary,
            border: `1px solid ${themeColor.primary}`,
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 600,
            fontFamily: 'Cinzel, serif',
            cursor: 'default',
          }}
        >
          Settings
        </button>
        <button
          type="button"
          disabled={demoBusy}
          onClick={onEnterDemo}
          style={{
            flex: 1,
            padding: '8px 12px',
            background: demoBusy ? '#4a4a5e' : `linear-gradient(135deg, ${themeColor.primary} 0%, ${themeColor.primary}dd 100%)`,
            color: 'white',
            border: `2px solid ${themeColor.primary}`,
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 600,
            fontFamily: 'Cinzel, serif',
            cursor: demoBusy ? 'not-allowed' : 'pointer',
            boxShadow: demoBusy ? 'none' : `0 2px 10px ${themeColor.shadow}`,
          }}
        >
          Enter — demo
        </button>
      </div>
    </div>
  );
}

export default GothicShowcase;
