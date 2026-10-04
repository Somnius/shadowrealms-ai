/**
 * World of Darkness game terms stay in English in every language (owner decision): Hunger,
 * Rouse Check, Masquerade, Willpower, Blood Potency, Storyteller, clan and discipline names…
 * Where such a term is a label, show it with an explanation in the active language as a
 * tooltip (title). Terms and explanations live in locales/{en,el}/glossary.json:
 *   glossary:term.<id>  the English term (identical in el)
 *   glossary:hint.<id>  what it means (Greek in el)
 */
import React from 'react';
import { t } from './index';

/** The term itself (always English). */
export function term(id, fallback) {
  return t(`glossary:term.${id}`, fallback || id);
}

/** One-line explanation in the active language ('' if the id is unknown). */
export function termHint(id) {
  return t(`glossary:hint.${id}`, '');
}

/**
 * <Term id="hunger" /> → <span lang="en" title="…Greek explanation…">Hunger</span>.
 * `children` overrides the visible text (e.g. "Hunger 3"); the tooltip stays.
 */
export function Term({ id, children, className = '', as: Tag = 'span' }) {
  const hint = termHint(id);
  return (
    <Tag lang="en" title={hint || undefined} className={`sr-term ${className}`.trim()}>
      {children != null ? children : term(id)}
    </Tag>
  );
}

export default Term;
