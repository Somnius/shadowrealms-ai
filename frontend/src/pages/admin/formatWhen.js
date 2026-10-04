import { getLanguage, getLocale } from '../../i18n';

/** Date + time in the admin's display timezone (browser zone when unset), in the UI language. */
export default function formatWhen(value, timeZone) {
  if (!value) return '—';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  const opts = { year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit' };
  if (getLanguage() === 'el') opts.hourCycle = 'h23';
  else opts.hour12 = true;
  if (timeZone) opts.timeZone = timeZone;
  try {
    return new Intl.DateTimeFormat(getLocale(), opts).format(d);
  } catch {
    return d.toLocaleString();
  }
}
