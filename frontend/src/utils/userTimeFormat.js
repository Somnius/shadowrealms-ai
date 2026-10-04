import { getLanguage, getLocale } from '../i18n';

/** Greek uses the 24-hour clock; English keeps 12-hour (as before). */
function clockOpts(opts) {
  if (getLanguage() !== 'el') return opts;
  const { hour12, ...rest } = opts;
  return { ...rest, hourCycle: 'h23' };
}

/**
 * Format instants in the user's chosen IANA zone (or browser local if zone is null/empty).
 * @param {string|number|Date} isoOrDate
 * @param {string|null|undefined} timeZone - user.display_timezone
 * @param {Intl.DateTimeFormatOptions} [extra]
 */
export function formatDateTimeInZone(isoOrDate, timeZone, extra = {}) {
  const d = isoOrDate instanceof Date ? isoOrDate : new Date(isoOrDate);
  if (Number.isNaN(d.getTime())) {
    return '—';
  }
  const opts = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
    ...extra,
  };
  if (timeZone) {
    opts.timeZone = timeZone;
  }
  return new Intl.DateTimeFormat(getLocale(), clockOpts(opts)).format(d);
}

/**
 * Full tooltip-style string (long date + time).
 */
export function formatDateTimeTooltip(isoOrDate, timeZone) {
  return formatDateTimeInZone(isoOrDate, timeZone, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
}
