const MONTHS_GENITIVE = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

const MONTHS_SHORT = [
  'янв.', 'февр.', 'мар.', 'апр.', 'мая', 'июн.',
  'июл.', 'авг.', 'сент.', 'окт.', 'нояб.', 'дек.',
];

const WEEKDAYS = [
  'воскресенье', 'понедельник', 'вторник', 'среда',
  'четверг', 'пятница', 'суббота',
];

const WEEKDAYS_SHORT = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function parseLocalDate(iso) {
  if (!iso) return null;
  return new Date(`${iso}T00:00:00`);
}

export function todayISO() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export function nowTime() {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
}

export function capitalize(value) {
  const text = String(value ?? '');
  return text ? text[0].toUpperCase() + text.slice(1) : '';
}

export function weekdayShort(iso) {
  const date = parseLocalDate(iso);
  return date ? WEEKDAYS_SHORT[date.getDay()] : '';
}

export function weekdayLong(iso) {
  const date = parseLocalDate(iso);
  return date ? capitalize(WEEKDAYS[date.getDay()]) : '';
}

export function humanDate(iso, { weekday = true } = {}) {
  const date = parseLocalDate(iso);
  if (!date) return '';
  const base = `${date.getDate()} ${MONTHS_GENITIVE[date.getMonth()]}`;
  return weekday ? `${weekdayLong(iso)}, ${base}` : base;
}

export function shortDate(iso) {
  const date = parseLocalDate(iso);
  if (!date) return '';
  return `${date.getDate()} ${MONTHS_SHORT[date.getMonth()]}`;
}

export function relativeDay(iso) {
  if (!iso) return '';
  const today = todayISO();
  if (iso === today) return 'Сегодня';
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const offset = yesterday.getTimezoneOffset() * 60000;
  const y = new Date(yesterday.getTime() - offset).toISOString().slice(0, 10);
  if (iso === y) return 'Вчера';
  return shortDate(iso);
}

export function greeting() {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return 'Доброе утро';
  if (hour >= 12 && hour < 18) return 'Добрый день';
  if (hour >= 18 && hour < 23) return 'Добрый вечер';
  return 'Спокойной ночи';
}

export function plural(number, forms) {
  const n = Math.abs(Number(number));
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return forms[1];
  return forms[2];
}

export function formatMinutes(minutes) {
  if (minutes === null || minutes === undefined || Number.isNaN(Number(minutes))) {
    return '—';
  }
  const total = Math.max(0, Math.round(Number(minutes)));
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  if (hours && rest) return `${hours} ч ${rest} мин`;
  if (hours) return `${hours} ч`;
  return `${rest} мин`;
}

export function formatMinutesShort(minutes) {
  if (minutes === null || minutes === undefined) return '—';
  const total = Math.max(0, Math.round(Number(minutes)));
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  if (hours && rest) return `${hours}ч ${rest}м`;
  if (hours) return `${hours}ч`;
  return `${rest}м`;
}

export function formatSeconds(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const total = Math.max(0, Math.round(Number(seconds)));
  if (total < 60) return `${total} сек`;
  return formatMinutes(Math.round(total / 60));
}

export function formatDelta(value, unit = '', { signed = true } = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  const number = Number(value);
  const sign = signed && number > 0 ? '+' : '';
  const rounded = Number.isInteger(number) ? number : number.toFixed(1);
  return `${sign}${String(rounded).replace('.', ',')}${unit ? ` ${unit}` : ''}`;
}

export function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return new Intl.NumberFormat('ru-RU', {
    maximumFractionDigits: digits,
  }).format(Number(value));
}

export function percent(value) {
  return `${clamp(Math.round(Number(value) || 0), 0, 100)}%`;
}

export function uid(prefix = 'id') {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

export function truncate(value, length = 80) {
  const text = String(value ?? '');
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}
