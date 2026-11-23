const API_BASE = '/api';

export class ApiError extends Error {
  constructor(message, { status = 0, detail = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function telegramInitData() {
  try {
    return window.Telegram?.WebApp?.initData || '';
  } catch {
    return '';
  }
}

function isLocalPreview() {
  const host = window.location.hostname;
  if (host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0') {
    return true;
  }
  if (host.endsWith('.local')) return true;
  return new URLSearchParams(window.location.search).get('dev') === '1';
}

function authHeaders() {
  const headers = { Accept: 'application/json' };
  const initData = telegramInitData();
  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
    return headers;
  }
  if (isLocalPreview()) {
    headers['X-Dev-Mode'] = '1';
  }
  return headers;
}

function detailMessage(detail) {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item;
        const field = Array.isArray(item?.loc) ? item.loc.slice(1).join('.') : '';
        return `${field ? `${field}: ` : ''}${item?.msg || 'Некорректное значение'}`;
      })
      .join('; ');
  }
  if (typeof detail === 'object' && detail.message) return String(detail.message);
  return '';
}

async function request(path, { method = 'GET', body, headers: extraHeaders, raw = false } = {}) {
  const headers = { ...authHeaders(), ...(extraHeaders || {}) };
  let payload;
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: payload,
      credentials: 'same-origin',
    });
  } catch (error) {
    throw new ApiError('Нет связи с сервером. Проверьте интернет и попробуйте снова.', {
      status: 0,
      detail: error,
    });
  }

  if (response.status === 204) return null;

  if (!response.ok) {
    let detail = null;
    try {
      const data = await response.json();
      detail = data?.detail ?? data;
    } catch {
      try {
        detail = await response.text();
      } catch {
        detail = null;
      }
    }
    const message =
      detailMessage(detail) ||
      (response.status === 401
        ? 'Откройте приложение через Telegram.'
        : response.status === 403
          ? 'Это личное приложение.'
          : 'Не удалось выполнить запрос.');
    throw new ApiError(message, { status: response.status, detail });
  }

  if (raw) return response;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function dateQuery(date) {
  return date ? `?date=${encodeURIComponent(date)}` : '';
}

export const api = {
  dashboard(date) {
    return request(`/dashboard${dateQuery(date)}`);
  },

  toggleHabit(key, { date = null, completed = null } = {}) {
    return request(`/habits/${encodeURIComponent(key)}/toggle`, {
      method: 'POST',
      body: { date, completed },
    });
  },

  priority(date) {
    return request(`/priority${dateQuery(date)}`);
  },

  savePriority(payload) {
    return request('/priority', { method: 'PUT', body: payload });
  },

  fitness(date) {
    return request(`/fitness${dateQuery(date)}`);
  },

  addSet(payload) {
    return request('/fitness/sets', { method: 'POST', body: payload });
  },

  deleteSet(setId, date) {
    return request(`/fitness/sets/${setId}${dateQuery(date)}`, {
      method: 'DELETE',
    });
  },

  completeWorkout(payload) {
    return request('/fitness/complete', { method: 'POST', body: payload });
  },

  nutrition(date) {
    return request(`/nutrition${dateQuery(date)}`);
  },

  addMeal(payload) {
    return request('/nutrition/meals', { method: 'POST', body: payload });
  },

  deleteMeal(mealId, date) {
    return request(`/nutrition/meals/${mealId}${dateQuery(date)}`, {
      method: 'DELETE',
    });
  },

  addWater(payload) {
    return request('/nutrition/water', { method: 'POST', body: payload });
  },

  deleteWater(entryId, date) {
    return request(`/nutrition/water/${entryId}${dateQuery(date)}`, {
      method: 'DELETE',
    });
  },

  saveMeasurement(payload) {
    return request('/nutrition/measurements', { method: 'POST', body: payload });
  },

  sleep(date) {
    return request(`/sleep${dateQuery(date)}`);
  },

  saveSleep(payload) {
    return request('/sleep', { method: 'POST', body: payload });
  },

  deleteSleep(date) {
    return request(`/sleep${dateQuery(date)}`, { method: 'DELETE' });
  },

  bible(date) {
    return request(`/bible${dateQuery(date)}`);
  },

  saveBible(payload) {
    return request('/bible', { method: 'POST', body: payload });
  },

  deleteBible(date) {
    return request(`/bible${dateQuery(date)}`, { method: 'DELETE' });
  },

  stats(period = 'week', date = null) {
    const params = new URLSearchParams({ period });
    if (date) params.set('date', date);
    return request(`/stats?${params.toString()}`);
  },

  settings() {
    return request('/settings');
  },

  saveSettings(payload) {
    return request('/settings', { method: 'PUT', body: payload });
  },

  async downloadExport() {
    const response = await request('/export', { raw: true });
    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^";]+)"?/i);
    const filename = match?.[1] || 'discipline-os-export.json';
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  },
};
