/**
 * Translated caption under a message (docs/VOICE.md §6.3): the body in the player's language, the
 * other text as a two-line italic caption with an EL / EN chip, and "Show original" to swap them
 * (row state only, not saved).
 */
import { useState } from 'react';
import { t } from '../../i18n';
import { captionView, useTranslationsContext } from './translations';
import './voice.css';

const LONG = 140;

/** {view, swapped, toggle, bodyText} for a message row; view null when there is no caption. */
export function useCaption(message) {
  const ctx = useTranslationsContext();
  const [swapped, setSwapped] = useState(false);
  const view = ctx && message && message.id != null ? captionView(message, ctx.map[message.id], ctx.hearLang, ctx.userId) : null;
  return {
    view,
    swapped,
    toggle: () => setSwapped((v) => !v),
    bodyText: view ? (swapped ? view.caption : view.body) : null,
  };
}

const chip = (lang) => (lang === 'el' ? 'EL' : 'EN');

function buttonLabel(view, swapped) {
  if (swapped) return view.label === 'sent' ? t('voice:caption.showOriginal', 'Show original') : t('voice:caption.showTranslation', 'Show translation');
  if (view.label === 'sent') return t('voice:caption.showSent', 'Show as sent');
  if (view.label === 'yourOriginal') return t('voice:caption.showYourOriginal', 'Show your original');
  return t('voice:caption.showOriginal', 'Show original');
}

export function Caption({ cap }) {
  const [open, setOpen] = useState(false);
  const { view, swapped } = cap;
  if (!view) return null;
  const text = swapped ? view.body : view.caption;
  const lang = swapped ? view.bodyLang : view.captionLang;
  const langName = lang === 'el' ? 'Ελληνικά' : 'English';
  return (
    <div className="sr-msg__caption" data-testid="msg-caption">
      <span className="sr-msg__langchip" title={langName} aria-label={langName}>{chip(lang)}</span>
      <p className={`sr-msg__caption-text${open ? ' is-open' : ''}`} lang={lang}>
        {!swapped && view.label === 'yourOriginal' ? <span className="sr-msg__caption-label">{t('voice:caption.yourOriginal', 'Your original:')} </span> : null}
        {text}
      </p>
      {!open && String(text || '').length > LONG ? (
        <button type="button" className="sr-msg__more" onClick={() => setOpen(true)}>{t('voice:caption.more', 'more')}</button>
      ) : null}
      <button type="button" className="sr-msg__orig" aria-pressed={swapped} onClick={cap.toggle}>{buttonLabel(view, swapped)}</button>
    </div>
  );
}
