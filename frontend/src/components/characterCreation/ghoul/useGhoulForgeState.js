import { useEffect, useMemo, useState } from 'react';
import { createEmptyMeritRow } from '../../../characterSheet/meritsFlaws';
import { V5_BACKGROUNDS } from '../../../characterSheet/v5/constants';
import { emptyV5Skills } from '../../../characterSheet/v5/validation';
import { advantageEntries } from '../../../characterSheet/v5/rulesData';
import { settingsForCampaign } from '../../../characterSheet/v5/creationSettings';
import {
  GHOUL_TEMPLATES,
  PLAYER_GHOUL,
  deriveGhoul,
  emptyGhoulAttributes,
  ghoulAttributeStatus,
  ghoulSkillCounts,
  ghoulSkillStatus,
} from '../../../characterSheet/v5/ghoul';
import { catalogRows, meritRowsToAdvRows } from '../v5/useV5ForgeState';

const isBackgroundName = (name) => V5_BACKGROUNDS.some((b) => String(name || '').toLowerCase().startsWith(b.toLowerCase()));

/**
 * All state of the ghoul forge and the sheet built from it (characterSheet/v5/ghoul.js has its
 * shape). It exposes the names the shared V5 steps read through useForge() (CatalogAdvantages,
 * StoryStep: advRows, loreRows, meritRows, meritNotes, settings, sheet, derived, background...)
 * plus the ghoul's own. `domitors`: the user's V5 vampires; `domitorId`: the one picked first;
 * `chronicles`: the settings are those of the domitor's chronicle (defaults without one).
 */
export default function useGhoulForgeState(chronicles, domitors, domitorId) {
  const firstOf = (l) => {
    const hit = (l || []).find((d) => String(d.id) === String(domitorId)) || (l || [])[0];
    return hit ? String(hit.id) : '';
  };
  const [domitorKey, setDomitorKey] = useState(() => firstOf(domitors));
  // the list may arrive after the first render
  useEffect(() => {
    if (!domitorKey && domitors?.length) {
      const hit = domitors.find((d) => String(d.id) === String(domitorId)) || domitors[0];
      setDomitorKey(String(hit.id));
    }
  }, [domitorKey, domitors, domitorId]);
  const list = domitors || [];
  const domitor = list.find((d) => String(d.id) === domitorKey) || null;
  const settings = settingsForCampaign(chronicles, domitor?.campaign_id);

  const [name, setName] = useState('');
  const [concept, setConcept] = useState('');
  const [ambition, setAmbition] = useState('');
  const [desire, setDesire] = useState('');
  const [template, setTemplateRaw] = useState('gifted');
  const [retainerDots, setRetainerDots] = useState(GHOUL_TEMPLATES.gifted.retainer_dots);
  const [age, setAge] = useState('');
  const [apparentAge, setApparentAge] = useState('');
  const [ghouledSince, setGhouledSince] = useState('');
  const [attributes, setAttributes] = useState(() => emptyGhoulAttributes('gifted'));
  const [skillDistribution, setSkillDistribution] = useState('balanced');
  const [skills, setSkills] = useState(emptyV5Skills);
  const [specialties, setSpecialties] = useState([]);
  const [power, setPower] = useState({ discipline: '', name: '' });
  const [meritRows, setMeritRows] = useState(() => [createEmptyMeritRow()]);
  const [meritNotes, setMeritNotes] = useState('');
  const [advRows, setAdvRows] = useState([]);
  const [loreRows, setLoreRows] = useState([]);
  const [bonds, setBonds] = useState([{ strength: null, note: '' }]);
  // when it last fed on the domitor's Blood: a note, not a track (a V5 ghoul has no vitae, core p. 234)
  const [feeding, setFeeding] = useState({ last: '', note: '' });
  const [humanityTracked, setHumanityTracked] = useState(false);
  const [convictions, setConvictions] = useState([{ conviction: '', touchstone: '' }]);
  const [background, setBackground] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});

  const catalogAdvantages = advantageEntries().length > 0;
  useEffect(() => {
    if (!catalogAdvantages) return;
    const moved = meritRowsToAdvRows(meritRows);
    if (!moved.length) return;
    setAdvRows((prev) => [...prev, ...moved]);
    setMeritRows([createEmptyMeritRow()]);
  }, [catalogAdvantages, meritRows]);
  const { advantages, flaws } = catalogAdvantages
    ? catalogRows(advRows, loreRows)
    : {
        advantages: meritRows
          .filter((r) => String(r.name || '').trim() && Number(r.points) > 0)
          .map((r) => ({ name: r.name, dots: Number(r.points), kind: isBackgroundName(r.name) ? 'background' : 'merit' })),
        flaws: meritRows
          .filter((r) => String(r.name || '').trim() && Number(r.points) < 0)
          .map((r) => ({ name: r.name, dots: -Number(r.points) })),
      };

  const sheet = {
    name,
    concept,
    ambition,
    desire,
    template,
    retainerDots,
    age,
    apparentAge,
    ghouledSince,
    attributes,
    skillDistribution,
    skills,
    specialties: specialties.filter((x) => x.skill || String(x.name || '').trim()),
    power,
    advantages,
    flaws,
    bonds,
    feeding,
    humanityTracked: template === PLAYER_GHOUL || humanityTracked,
    convictions,
  };

  /** A new template starts its Attributes and Skills over (as a new clan does the Disciplines). */
  const setTemplate = (next) => {
    setTemplateRaw(next);
    setAttributes(emptyGhoulAttributes(next));
    setSkills(emptyV5Skills());
    setSpecialties([]);
    if (GHOUL_TEMPLATES[next]) setRetainerDots(GHOUL_TEMPLATES[next].retainer_dots);
    else setRetainerDots(null);
  };
  /** Another domitor: the power is picked again from its Disciplines. */
  const setDomitorId = (id) => {
    setDomitorKey(String(id));
    setPower({ discipline: '', name: '' });
  };

  const counts = ghoulSkillCounts(template, skillDistribution) || {};
  const attrStatus = useMemo(() => ghoulAttributeStatus(attributes, template), [attributes, template]);
  return {
    settings,
    sheet,
    derived: deriveGhoul(sheet),
    domitors: list,
    domitor,
    attrStatus,
    skillStatus: ghoulSkillStatus(skills, template, skillDistribution),
    skillMax: Math.max(1, ...Object.keys(counts).map(Number)),
    attrMax: Math.max(...(GHOUL_TEMPLATES[template]?.attributes || [4])),
    attrMin: Math.min(...(GHOUL_TEMPLATES[template]?.attributes || [1])),
    advDots: advantages.reduce((s, a) => s + (Number(a.dots) || 0), 0),
    flawDots: flaws.reduce((s, a) => s + (Number(a.dots) || 0), 0),
    // values and setters
    name, setName, concept, setConcept, ambition, setAmbition, desire, setDesire,
    domitorId: domitorKey, setDomitorId, template, setTemplate, retainerDots, setRetainerDots,
    age, setAge, apparentAge, setApparentAge, ghouledSince, setGhouledSince,
    attributes, setAttributes, skillDistribution, setSkillDistribution, skills, setSkills, specialties, setSpecialties,
    power, setPower, meritRows, setMeritRows, meritNotes, setMeritNotes, catalogAdvantages, advRows, setAdvRows,
    loreRows, setLoreRows, bonds, setBonds, feeding, setFeeding, humanityTracked, setHumanityTracked,
    convictions, setConvictions, background, setBackground, fieldErrors, setFieldErrors,
  };
}
