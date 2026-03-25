/**
 * IANA time zones for profile display override.
 * Prefers Intl.supportedValuesOf('timeZone') when available.
 */

const FALLBACK_ZONES = [
  'UTC',
  'Europe/Athens',
  'Europe/Berlin',
  'Europe/London',
  'Europe/Paris',
  'Europe/Madrid',
  'Europe/Rome',
  'Europe/Warsaw',
  'Europe/Moscow',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Toronto',
  'America/Sao_Paulo',
  'Asia/Tokyo',
  'Asia/Seoul',
  'Asia/Shanghai',
  'Asia/Hong_Kong',
  'Asia/Singapore',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Australia/Sydney',
  'Pacific/Auckland',
];

/**
 * @returns {{ value: string, label: string }[]}
 */
export function getTimezoneSelectOptions() {
  let zones;
  try {
    if (typeof Intl !== 'undefined' && typeof Intl.supportedValuesOf === 'function') {
      zones = Intl.supportedValuesOf('timeZone');
    }
  } catch (_) {
    zones = null;
  }
  if (!zones || !zones.length) {
    zones = [...FALLBACK_ZONES];
  }
  const sorted = [...new Set(zones)].sort((a, b) => a.localeCompare(b));
  return sorted.map((z) => ({ value: z, label: z }));
}
