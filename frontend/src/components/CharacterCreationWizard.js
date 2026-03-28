import React, { useMemo, useState } from 'react';
import { GothicBox } from './GothicDecorations';

const API_URL = '/api';

const PHYSICAL = ['strength', 'dexterity', 'stamina'];
const SOCIAL = ['charisma', 'manipulation', 'appearance'];
const MENTAL = ['perception', 'intelligence', 'wits'];

const VAMPIRE_CLANS = [
  'Brujah', 'Gangrel', 'Malkavian', 'Nosferatu', 'Toreador', 'Tremere', 'Ventrue',
  'Lasombra', 'Tzimisce', 'Ravnos', 'Assamite', 'Followers of Set', 'Giovanni',
];

const WTA_BREEDS = ['Homid', 'Metis', 'Lupus'];
const WTA_AUSPICES = ['Ahroun', 'Galliard', 'Philodox', 'Ragabash', 'Theurge'];
const WTA_TRIBES = [
  'Black Furies', 'Bone Gnawers', 'Children of Gaia', 'Fianna', 'Get of Fenris',
  'Glass Walkers', 'Red Talons', 'Shadow Lords', 'Silent Striders', 'Silver Fangs',
  'Uktena', 'Wendigo', 'Stargazers',
];

const MTA_TRADITIONS = [
  'Akashic Brotherhood', 'Celestial Chorus', 'Cult of Ecstasy', 'Dream Speakers',
  'Euthanatos', 'Order of Hermes', 'Sons of Ether', 'Verbena', 'Virtual Adepts',
];

function emptyAttrMap() {
  const o = {};
  [...PHYSICAL, ...SOCIAL, ...MENTAL].forEach((k) => {
    o[k] = 1;
  });
  return o;
}

function validateAttributeSpread(attrs, pools) {
  const sum = (keys) => keys.reduce((s, k) => s + (parseInt(attrs[k], 10) || 0), 0);
  const p = sum(PHYSICAL);
  const s = sum(SOCIAL);
  const m = sum(MENTAL);
  if (p !== pools.physical) return `Physical attributes must total ${pools.physical} (currently ${p}).`;
  if (s !== pools.social) return `Social attributes must total ${pools.social} (currently ${s}).`;
  if (m !== pools.mental) return `Mental attributes must total ${pools.mental} (currently ${m}).`;
  for (const k of [...PHYSICAL, ...SOCIAL, ...MENTAL]) {
    const v = parseInt(attrs[k], 10);
    if (Number.isNaN(v) || v < 1 || v > 5) {
      return `Each attribute must be between 1 and 5 (${k}).`;
    }
  }
  return null;
}

/**
 * Multi-step oWoD-oriented character creator (Vampire / Werewolf / Mage campaigns).
 */
export default function CharacterCreationWizard({
  token,
  campaigns,
  onDone,
  onCancel,
  showError,
  showSuccess,
}) {
  const eligible = useMemo(
    () =>
      (campaigns || []).filter((c) =>
        ['vampire', 'werewolf', 'mage'].includes(
          String(c.game_system || '').toLowerCase()
        )
      ),
    [campaigns]
  );

  const [step, setStep] = useState(0);
  const [campaignId, setCampaignId] = useState(
    eligible[0]?.id != null ? String(eligible[0].id) : ''
  );
  const [name, setName] = useState('');
  const [concept, setConcept] = useState('');
  const [priority, setPriority] = useState('physical'); // which category gets 7 dots
  const [attrs, setAttrs] = useState(() => emptyAttrMap());
  const [skillsNotes, setSkillsNotes] = useState('');
  const [background, setBackground] = useState('');

  const [clan, setClan] = useState(VAMPIRE_CLANS[0]);
  const [nature, setNature] = useState('');
  const [demeanor, setDemeanor] = useState('');
  const [generation, setGeneration] = useState('13');

  const [breed, setBreed] = useState(WTA_BREEDS[0]);
  const [auspice, setAuspice] = useState(WTA_AUSPICES[0]);
  const [tribe, setTribe] = useState(WTA_TRIBES[0]);

  const [tradition, setTradition] = useState(MTA_TRADITIONS[0]);

  const [submitting, setSubmitting] = useState(false);

  const campaign = eligible.find((c) => String(c.id) === String(campaignId));
  const gs = String(campaign?.game_system || '').toLowerCase();
  const systemType = gs;

  const pools = useMemo(() => {
    if (priority === 'physical') {
      return { physical: 7, social: 5, mental: 3 };
    }
    if (priority === 'social') {
      return { physical: 5, social: 7, mental: 3 };
    }
    return { physical: 3, social: 5, mental: 7 };
  }, [priority]);

  const wodMeta = () => {
    const base = { concept: concept.trim() };
    if (systemType === 'vampire') {
      return {
        ...base,
        clan,
        nature,
        demeanor,
        generation,
      };
    }
    if (systemType === 'werewolf') {
      return {
        ...base,
        breed,
        auspice,
        tribe,
      };
    }
    if (systemType === 'mage') {
      return {
        ...base,
        tradition,
        arete: 1,
      };
    }
    return base;
  };

  const handleSubmit = async () => {
    if (!campaign) {
      showError?.('Choose a chronicle.');
      return;
    }
    const nm = name.trim();
    if (!nm) {
      showError?.('Character name is required.');
      return;
    }
    const err = validateAttributeSpread(attrs, pools);
    if (err) {
      showError?.(err);
      return;
    }

    const skillsPayload = {
      notes: skillsNotes.trim(),
      allocation_hint: 'Assign Ability dots per your Storyteller and corebook (Revised charts).',
    };

    setSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/characters/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: nm,
          campaign_id: parseInt(campaignId, 10),
          system_type: systemType,
          attributes: attrs,
          skills: skillsPayload,
          background: background.trim(),
          merits_flaws: {},
          wod_meta: wodMeta(),
          sheet_locked: true,
          is_active: true,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        showError?.(body.error || 'Could not create character.');
        return;
      }
      showSuccess?.('Character forged. Select them in Player Profile if needed.');
      onDone?.(body);
    } catch (e) {
      showError?.('Network error while creating character.');
    } finally {
      setSubmitting(false);
    }
  };

  const renderAttrs = (label, keys) => (
    <div style={{ marginBottom: '16px' }}>
      <div
        style={{
          color: '#e94560',
          fontFamily: 'Cinzel, serif',
          fontSize: '14px',
          marginBottom: '8px',
        }}
      >
        {label} (pool {label === 'Physical' ? pools.physical : label === 'Social' ? pools.social : pools.mental})
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
          gap: '10px',
        }}
      >
        {keys.map((k) => (
          <label key={k} style={{ color: '#b5b5c3', fontSize: '13px' }}>
            <div style={{ textTransform: 'capitalize', marginBottom: '4px' }}>{k}</div>
            <input
              type="number"
              min={1}
              max={5}
              value={attrs[k]}
              onChange={(e) =>
                setAttrs((prev) => ({ ...prev, [k]: e.target.value }))
              }
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: '6px',
                border: '2px solid #2a2a4e',
                background: '#0f1729',
                color: '#e0e0e0',
              }}
            />
          </label>
        ))}
      </div>
    </div>
  );

  if (!eligible.length) {
    return (
      <GothicBox theme="vampire" style={{ padding: '24px', maxWidth: '560px', margin: '0 auto' }}>
        <p style={{ color: '#b5b5c3' }}>
          You need to be a member of at least one Vampire, Werewolf, or Mage chronicle before
          using this forge.
        </p>
        <button
          type="button"
          onClick={onCancel}
          style={{
            marginTop: '16px',
            padding: '10px 20px',
            background: '#2a2a4e',
            color: '#e0e0e0',
            border: '1px solid #9d4edd',
            borderRadius: '8px',
            cursor: 'pointer',
          }}
        >
          Back
        </button>
      </GothicBox>
    );
  }

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto', padding: '20px 16px 60px' }}>
      <GothicBox theme={systemType === 'werewolf' ? 'werewolf' : systemType === 'mage' ? 'mage' : 'vampire'}>
        <div style={{ padding: '8px 8px 0' }}>
          <h2
            style={{
              fontFamily: 'Cinzel, serif',
              color: '#e94560',
              marginTop: 0,
              fontSize: '22px',
            }}
          >
            Character creation
          </h2>
          <p style={{ color: '#8b8b9f', fontSize: '14px', lineHeight: 1.5 }}>
            Guided setup for <strong>Classic World of Darkness</strong>–style games. Exact dot
            totals and storyteller house rules belong in your table’s books — this wizard
            captures the spine of the sheet for ShadowRealms.
          </p>
        </div>

        <div style={{ padding: '16px' }}>
          {step === 0 && (
            <>
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                Chronicle
              </label>
              <select
                value={campaignId}
                onChange={(e) => setCampaignId(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  marginBottom: '20px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              >
                {eligible.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} — {c.game_system}
                  </option>
                ))}
              </select>
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                Character name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  marginBottom: '16px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              />
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                Concept (short)
              </label>
              <input
                value={concept}
                onChange={(e) => setConcept(e.target.value)}
                placeholder="e.g. weary homicide detective"
                style={{
                  width: '100%',
                  padding: '10px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              />
            </>
          )}

          {step === 1 && systemType === 'vampire' && (
            <>
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>Clan</label>
              <select
                value={clan}
                onChange={(e) => setClan(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  marginBottom: '12px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              >
                {VAMPIRE_CLANS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>Nature</label>
              <input
                value={nature}
                onChange={(e) => setNature(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  marginBottom: '12px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              />
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>Demeanor</label>
              <input
                value={demeanor}
                onChange={(e) => setDemeanor(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  marginBottom: '12px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              />
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                Generation (player tier)
              </label>
              <input
                value={generation}
                onChange={(e) => setGeneration(e.target.value)}
                placeholder="13"
                style={{
                  width: '100%',
                  padding: '10px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              />
            </>
          )}

          {step === 1 && systemType === 'werewolf' && (
            <>
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>Breed</label>
              <select
                value={breed}
                onChange={(e) => setBreed(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  marginBottom: '12px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              >
                {WTA_BREEDS.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>Auspice</label>
              <select
                value={auspice}
                onChange={(e) => setAuspice(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  marginBottom: '12px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              >
                {WTA_AUSPICES.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>Tribe</label>
              <select
                value={tribe}
                onChange={(e) => setTribe(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              >
                {WTA_TRIBES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </>
          )}

          {step === 1 && systemType === 'mage' && (
            <>
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>Tradition</label>
              <select
                value={tradition}
                onChange={(e) => setTradition(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              >
                {MTA_TRADITIONS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <p style={{ color: '#8b8b9f', fontSize: '13px', marginTop: '12px' }}>
                Arete begins at 1 in Revised; Sphere dots and freebies are resolved at the table.
              </p>
            </>
          )}

          {step === 2 && (
            <>
              <p style={{ color: '#b5b5c3', fontSize: '14px' }}>
                Prioritize a category for <strong>7 / 5 / 3</strong> dots (Revised-style attribute
                spread). Each attribute stays between 1 and 5 at creation.
              </p>
              <label style={{ color: '#c4b5fd', display: 'block', margin: '12px 0 8px' }}>
                Primary category (7 dots)
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  marginBottom: '16px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                }}
              >
                <option value="physical">Physical primary</option>
                <option value="social">Social primary</option>
                <option value="mental">Mental primary</option>
              </select>
              {renderAttrs('Physical', PHYSICAL)}
              {renderAttrs('Social', SOCIAL)}
              {renderAttrs('Mental', MENTAL)}
            </>
          )}

          {step === 3 && (
            <>
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                Abilities (notes)
              </label>
              <textarea
                value={skillsNotes}
                onChange={(e) => setSkillsNotes(e.target.value)}
                rows={4}
                placeholder="List priorities: e.g. Athletics 3, Streetwise 2, …"
                style={{
                  width: '100%',
                  padding: '10px',
                  marginBottom: '16px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                  resize: 'vertical',
                }}
              />
              <label style={{ color: '#c4b5fd', display: 'block', marginBottom: '8px' }}>
                Background & hooks
              </label>
              <textarea
                value={background}
                onChange={(e) => setBackground(e.target.value)}
                rows={6}
                style={{
                  width: '100%',
                  padding: '10px',
                  background: '#0f1729',
                  color: '#e0e0e0',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                  resize: 'vertical',
                }}
              />
            </>
          )}

          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '10px',
              marginTop: '24px',
              justifyContent: 'space-between',
            }}
          >
            <button
              type="button"
              onClick={step === 0 ? onCancel : () => setStep((s) => Math.max(0, s - 1))}
              style={{
                padding: '10px 18px',
                background: '#1e293b',
                color: '#e2e8f0',
                border: '1px solid #475569',
                borderRadius: '8px',
                cursor: 'pointer',
              }}
            >
              {step === 0 ? 'Cancel' : 'Back'}
            </button>
            {step < 3 ? (
              <button
                type="button"
                onClick={() => setStep((s) => s + 1)}
                style={{
                  padding: '10px 22px',
                  background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontFamily: 'Cinzel, serif',
                }}
              >
                Next
              </button>
            ) : (
              <button
                type="button"
                disabled={submitting}
                onClick={handleSubmit}
                style={{
                  padding: '10px 22px',
                  background: submitting ? '#4a4a5e' : '#9d4edd',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: submitting ? 'not-allowed' : 'pointer',
                  fontWeight: 'bold',
                  fontFamily: 'Cinzel, serif',
                }}
              >
                {submitting ? 'Sealing sheet…' : 'Create character'}
              </button>
            )}
          </div>
        </div>
      </GothicBox>
    </div>
  );
}
