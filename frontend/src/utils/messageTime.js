/**
 * Chat message time labels. Optional IANA `timeZone` overrides browser local.
 * Mirrors backend/services/message_time_format.py intent.
 *
 * @param {string|number|Date} createdAt - ISO string or Date
 * @param {Date} [now] - reference instant (for tests / periodic refresh)
 * @param {string|null|undefined} [timeZone] - user.display_timezone
 * @returns {string}
 */
import { getLanguage, getLocale, t } from '../i18n';

export function formatMessageTime(createdAt, now = new Date(), timeZone = null) {
  const then = createdAt instanceof Date ? createdAt : new Date(createdAt);
  if (Number.isNaN(then.getTime())) {
    return '';
  }

  const deltaMs = now - then;
  const secs = Math.floor(deltaMs / 1000);

  const calendarDateKeyInTz = (date, tz) => {
    const d = date instanceof Date ? date : new Date(date);
    if (!tz) {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      return `${y}-${m}-${day}`;
    }
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: tz,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(d);
    const get = (t) => parts.find((p) => p.type === t)?.value;
    return `${get('year')}-${get('month')}-${get('day')}`;
  };

  const daysBetweenCalendarKeys = (earlierKey, laterKey) => {
    const da = new Date(`${earlierKey}T12:00:00Z`);
    const db = new Date(`${laterKey}T12:00:00Z`);
    return Math.round((db - da) / 86400000);
  };

  const localeDateOpts = {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  };
  if (timeZone) {
    localeDateOpts.timeZone = timeZone;
  }

  const localeDateShortOpts = {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  };
  if (timeZone) {
    localeDateShortOpts.timeZone = timeZone;
  }

  const formatTime12h = (d) => {
    const opts =
      getLanguage() === 'el'
        ? { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }
        : { hour: 'numeric', minute: '2-digit', hour12: true };
    if (timeZone) opts.timeZone = timeZone;
    return new Intl.DateTimeFormat(getLocale(), opts).format(d instanceof Date ? d : new Date(d));
  };

  const nowKey = calendarDateKeyInTz(now, timeZone);
  const thenKey = calendarDateKeyInTz(then, timeZone);

  if (secs < 0) {
    const dayDiff = daysBetweenCalendarKeys(thenKey, nowKey);
    const timeStr = formatTime12h(then);
    const fullDateStr = then.toLocaleDateString(getLocale(), localeDateOpts);
    const dateOnlyStr = then.toLocaleDateString(getLocale(), localeDateShortOpts);
    if (dayDiff === 0) {
      return `${timeStr} · ${fullDateStr}`;
    }
    if (dayDiff === 1) {
      return t('common:time.yesterdayAt', 'Yesterday · {{time}} · {{date}}', { time: timeStr, date: fullDateStr });
    }
    return dateOnlyStr;
  }

  if (secs < 60) {
    return t('common:time.justNow', 'Just now');
  }

  const minutes = Math.floor(secs / 60);
  if (minutes <= 30) {
    return t('common:time.minutesAgo', { one: '{{count}} minute ago', other: '{{count}} minutes ago' }, { count: minutes });
  }

  const dayDiff = daysBetweenCalendarKeys(thenKey, nowKey);
  const timeStr = formatTime12h(then);
  const fullDateStr = then.toLocaleDateString(getLocale(), localeDateOpts);
  const dateOnlyStr = then.toLocaleDateString(getLocale(), localeDateShortOpts);

  if (dayDiff === 0) {
    return `${timeStr} · ${fullDateStr}`;
  }
  if (dayDiff === 1) {
    return t('common:time.yesterdayAt', 'Yesterday · {{time}} · {{date}}', { time: timeStr, date: fullDateStr });
  }
  return dateOnlyStr;
}
