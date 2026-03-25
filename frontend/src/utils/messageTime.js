/**
 * Chat message time labels (user's local timezone).
 * Mirrors backend/services/message_time_format.py.
 *
 * @param {string|number|Date} createdAt - ISO string or Date
 * @param {Date} [now] - reference instant (for tests / periodic refresh)
 * @returns {string}
 */
export function formatMessageTime(createdAt, now = new Date()) {
  const then = createdAt instanceof Date ? createdAt : new Date(createdAt);
  if (Number.isNaN(then.getTime())) {
    return '';
  }

  const deltaMs = now - then;
  const secs = Math.floor(deltaMs / 1000);

  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

  const formatTime12h = (d) => {
    let h = d.getHours() % 12;
    if (h === 0) h = 12;
    const ap = d.getHours() < 12 ? 'AM' : 'PM';
    const m = String(d.getMinutes()).padStart(2, '0');
    return `${h}:${m} ${ap}`;
  };

  if (secs < 0) {
    const dayDiff = Math.round(
      (startOfDay(now) - startOfDay(then)) / 86400000
    );
    const timeStr = formatTime12h(then);
    const fullDateStr = then.toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
    const dateOnlyStr = then.toLocaleDateString(undefined, {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
    if (dayDiff === 0) {
      return `${timeStr} · ${fullDateStr}`;
    }
    if (dayDiff === 1) {
      return `Yesterday · ${timeStr} · ${fullDateStr}`;
    }
    return dateOnlyStr;
  }

  if (secs < 60) {
    return 'Just now';
  }

  const minutes = Math.floor(secs / 60);
  if (minutes <= 30) {
    if (minutes === 1) return '1 minute ago';
    if (minutes === 2) return '2 minutes ago';
    if (minutes === 5) return '5 minutes ago';
    return `${minutes} minutes ago`;
  }

  const dayDiff = Math.round(
    (startOfDay(now) - startOfDay(then)) / 86400000
  );
  const timeStr = formatTime12h(then);
  const fullDateStr = then.toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
  const dateOnlyStr = then.toLocaleDateString(undefined, {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

  if (dayDiff === 0) {
    return `${timeStr} · ${fullDateStr}`;
  }
  if (dayDiff === 1) {
    return `Yesterday · ${timeStr} · ${fullDateStr}`;
  }
  return dateOnlyStr;
}
