/** Chat timestamps in the user's display time zone and the UI locale. */
import { getLocale, t } from '../../i18n';
import { formatDateTimeTooltip } from '../../utils/userTimeFormat';
import { dayKey } from './grouping';

function fmt(ms, timeZone, opts) {
  const o = { ...opts };
  if (timeZone) o.timeZone = timeZone;
  try {
    return new Intl.DateTimeFormat(getLocale(), o).format(new Date(ms));
  } catch (e) {
    return new Date(ms).toLocaleString();
  }
}

export function formatClock(ms, timeZone) {
  if (Number.isNaN(ms)) return '';
  return fmt(ms, timeZone, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
}

function relativeDay(ms, now, timeZone) {
  const today = dayKey(now, timeZone);
  const day = dayKey(ms, timeZone);
  if (day === today) return 'today';
  if (day === dayKey(now - 86400000, timeZone)) return 'yesterday';
  return null;
}

/** Group header: "Today at 21:14", "Yesterday at 09:02", "04/10/2026 21:14". */
export function formatShort(ms, now, timeZone) {
  if (Number.isNaN(ms)) return '';
  const rel = relativeDay(ms, now, timeZone);
  const clock = formatClock(ms, timeZone);
  if (rel === 'today') return t('chat:time.today', 'Today at {{time}}', { time: clock });
  if (rel === 'yesterday') return t('chat:time.yesterday', 'Yesterday at {{time}}', { time: clock });
  return `${fmt(ms, timeZone, { day: '2-digit', month: '2-digit', year: 'numeric' })} ${clock}`;
}

/** Day separator: "Today", "Yesterday", "Sunday, 4 October 2026". */
export function formatDay(ms, now, timeZone) {
  if (Number.isNaN(ms)) return '';
  const rel = relativeDay(ms, now, timeZone);
  if (rel === 'today') return t('chat:day.today', 'Today');
  if (rel === 'yesterday') return t('chat:day.yesterday', 'Yesterday');
  return fmt(ms, timeZone, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
}

/** Hover text: full date and time. */
export function formatFull(ms, timeZone) {
  if (Number.isNaN(ms)) return '';
  return formatDateTimeTooltip(new Date(ms), timeZone);
}

export function isoOf(ms) {
  return Number.isNaN(ms) ? undefined : new Date(ms).toISOString();
}
