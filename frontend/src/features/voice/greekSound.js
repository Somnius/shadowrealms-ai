// An English voice spells Greek letters one by one ("Kappa Omega…"). Before an English voice reads
// a line, Greek words are rewritten as English-looking sounds (Κατακουζηνός → Katakoozeenos).
// Same rules as speech/app/textprep.py greek_to_english_sound; keep the two in step.

const GREEK_WORD = /[Ͱ-Ͽἀ-῿]+/g;
const VOWELS = new Set('αεηιουω');
const FRONT = new Set('εηιυ');
const VOICELESS = new Set('θκξπσςτφχψ');
const SIMPLE = {
  α: 'a', β: 'v', δ: 'd', ζ: 'z', θ: 'th', κ: 'k', λ: 'l', μ: 'm', ν: 'n', ξ: 'x', ο: 'o',
  π: 'p', ρ: 'r', σ: 's', ς: 's', τ: 't', φ: 'f', χ: 'h', ψ: 'ps', ω: 'o',
};

function letters(word) {
  const out = [];
  for (const ch of word.toLowerCase().normalize('NFD')) {
    if (/\p{M}/u.test(ch)) {
      const last = out[out.length - 1];
      if (last) {
        if (ch === '́' || ch === '͂') last.stressed = true;
        if (ch === '̈') last.dia = true;
      }
      continue;
    }
    out.push({ c: ch, stressed: false, dia: false });
  }
  return out;
}

export function greekToEnglishSound(word) {
  const L = letters(word);
  const n = L.length;
  const at = (i) => (i < n ? L[i].c : '');
  const dia = (i) => (i < n ? L[i].dia : false);
  const frontNext = (i) => {
    const c = at(i);
    const d = at(i + 1);
    if ((c === 'α' || c === 'ο') && d === 'ι' && !dia(i + 1)) return true;
    return FRONT.has(c);
  };
  const out = [];
  let i = 0;
  while (i < n) {
    const { c, stressed } = L[i];
    const nx = at(i + 1);
    const nxDia = dia(i + 1);
    const start = i === 0;
    if ('αεη'.includes(c) && nx === 'υ' && !nxDia) {
      const after = at(i + 2);
      out.push({ α: 'a', ε: 'e', η: 'ee' }[c] + (!after || VOICELESS.has(after) ? 'f' : 'v'));
      i += 2;
    } else if (c === 'ο' && nx === 'υ' && !nxDia) {
      out.push('oo');
      i += 2;
    } else if (c === 'α' && nx === 'ι' && !nxDia) {
      out.push('e');
      i += 2;
    } else if (('εου'.includes(c) && nx === 'ι' && !nxDia) || 'ιηυ'.includes(c)) {
      const step = 'εου'.includes(c) && nx === 'ι' && !nxDia ? 2 : 1;
      const stressedI = L[i + step - 1].stressed || stressed;
      if (!stressedI && VOWELS.has(at(i + step))) {
        if (!(out.length && out[out.length - 1].endsWith('y'))) out.push('y');
      } else out.push('ee');
      i += step;
    } else if (c === 'μ' && nx === 'π') {
      out.push(start ? 'b' : 'mb');
      i += 2;
    } else if (c === 'ν' && nx === 'τ') {
      out.push(start ? 'd' : 'nd');
      i += 2;
    } else if (c === 'γ' && nx === 'κ') {
      out.push(start ? 'g' : 'ng');
      i += 2;
    } else if (c === 'γ' && (nx === 'γ' || nx === 'χ' || nx === 'ξ')) {
      out.push({ γ: 'ng', χ: 'nh', ξ: 'nx' }[nx]);
      i += 2;
    } else if (c === 'τ' && (nx === 'σ' || nx === 'ζ')) {
      out.push(nx === 'σ' ? 'ts' : 'dz');
      i += 2;
    } else {
      if (c === 'γ') out.push(frontNext(i + 1) ? 'y' : 'g');
      else if (c === 'ε') out.push(i === n - 1 ? 'eh' : 'e');
      else out.push(SIMPLE[c] || '');
      i += 1;
    }
  }
  const s = out.join('');
  return word[0] && word[0] !== word[0].toLowerCase() ? s[0].toUpperCase() + s.slice(1) : s;
}

export const greekWordsForEnglish = (text) => String(text || '').replace(GREEK_WORD, (w) => greekToEnglishSound(w));
