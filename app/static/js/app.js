import { icon } from './icons.js';
import { escapeHtml } from './format.js';
import { destroyCharts } from './charts.js';
import { formatError, toast } from './ui.js';
import { render as renderToday } from './views/today.js';
import { render as renderFitness } from './views/fitness.js';
import { render as renderNutrition } from './views/nutrition.js';
import { render as renderSleep } from './views/sleep.js';
import { render as renderStats } from './views/stats.js';
import { render as renderSettings } from './views/settings.js';

const ROUTES = {
  today: { render: renderToday, title: 'Сегодня', nav: 'today' },
  fitness: { render: renderFitness, title: 'Тренировка', nav: 'fitness' },
  nutrition: { render: renderNutrition, title: 'Питание', nav: 'nutrition' },
  sleep: { render: renderSleep, title: 'Сон', nav: 'sleep' },
  stats: { render: renderStats, title: 'Статистика', nav: 'stats' },
  settings: { render: renderSettings, title: 'Настройки', nav: null },
};

const NAV_ITEMS = [
  { key: 'today', label: 'Сегодня', icon: 'today', href: '#/today' },
  { key: 'fitness', label: 'Спорт', icon: 'dumbbell', href: '#/fitness' },
  { key: 'nutrition', label: 'Питание', icon: 'apple', href: '#/nutrition' },
  { key: 'sleep', label: 'Сон', icon: 'moon', href: '#/sleep' },
  { key: 'stats', label: 'Статистика', icon: 'chart', href: '#/stats' },
];

const screen = document.getElementById('screen');
const nav = document.getElementById('bottom-nav');
const fab = document.getElementById('fab');

const state = {
  cleanup: null,
  route: null,
  renderId: 0,
  lastRenderedAt: 0,
};

function currentRoute() {
  const raw = (window.location.hash || '').replace(/^#\/?/, '').split('?')[0];
  return ROUTES[raw] ? raw : 'today';
}

function renderNav(activeKey) {
  if (!nav) return;
  nav.innerHTML = NAV_ITEMS.map(
    (item) => `
      <a class="nav-item${item.key === activeKey ? ' is-active' : ''}" href="${item.href}"
        ${item.key === activeKey ? 'aria-current="page"' : ''}>
        ${icon(item.icon, 21)}
        <span>${escapeHtml(item.label)}</span>
      </a>
    `,
  ).join('');
}

function setFab(config) {
  if (!fab) return;
  if (!config) {
    fab.hidden = true;
    fab.onclick = null;
    fab.innerHTML = '';
    return;
  }
  fab.hidden = false;
  fab.innerHTML = icon(config.icon || 'plus', 24);
  fab.setAttribute('aria-label', config.label || 'Добавить');
  fab.setAttribute('title', config.label || 'Добавить');
  fab.onclick = (event) => {
    event.preventDefault();
    config.onClick?.();
  };
}

function loadingScreen() {
  return `
    <div class="loading-screen" aria-busy="true" aria-label="Загрузка">
      <div class="skeleton skeleton--sub"></div>
      <div class="skeleton skeleton--title"></div>
      <div class="skeleton skeleton--hero"></div>
      <div class="skeleton skeleton--row"></div>
      <div class="skeleton skeleton--card"></div>
    </div>
  `;
}

function errorScreen(error) {
  const unauthorized = error?.status === 401 || error?.status === 403;
  const title = unauthorized ? 'Откройте через Telegram' : 'Не удалось загрузить';
  const text = unauthorized
    ? 'Это личное приложение. Доступ открывается из Telegram, где проверяется подпись initData.'
    : formatError(error);
  const hint = unauthorized
    ? 'Откройте бота, нажмите /dashboard и войдите в Mini App. В локальном браузере нужен DEV_MODE=true.'
    : 'Проверьте соединение и попробуйте ещё раз. Ваши записи не потеряны.';
  return `
    <div class="error-screen">
      <span class="error-screen__icon">${icon(unauthorized ? 'lock' : 'alert', 26)}</span>
      <h1 class="error-screen__title">${title}</h1>
      <p class="error-screen__text">${escapeHtml(text)}</p>
      <p class="error-screen__hint">${escapeHtml(hint)}</p>
      <button class="btn btn--primary" type="button" data-retry>Попробовать снова</button>
    </div>
  `;
}

function telegramBackButton(visible) {
  const back = window.Telegram?.WebApp?.BackButton;
  if (!back) return;
  try {
    if (visible) back.show();
    else back.hide();
  } catch {
    /* Telegram WebApp may be unavailable in a browser. */
  }
}

function initTelegram() {
  const webApp = window.Telegram?.WebApp;
  if (!webApp) return;
  try {
    webApp.ready();
    webApp.expand();
  } catch {
    /* Older Telegram clients. */
  }
  try {
    const styles = getComputedStyle(document.documentElement);
    const background = styles.getPropertyValue('--color-bg').trim();
    const surface = styles.getPropertyValue('--color-surface').trim();
    if (background) {
      webApp.setHeaderColor(background);
      webApp.setBackgroundColor(background);
    }
    if (surface) webApp.setBottomBarColor?.(surface);
  } catch {
    /* Color setters are optional. */
  }
  try {
    webApp.disableVerticalSwipes?.();
  } catch {
    /* Not supported. */
  }
  try {
    webApp.BackButton?.onClick(() => {
      if (window.history.length > 1) window.history.back();
      else window.location.hash = '#/today';
    });
  } catch {
    /* Not supported. */
  }
}

async function renderRoute({ refresh = false } = {}) {
  const routeKey = currentRoute();
  const route = ROUTES[routeKey];
  const isNewRoute = routeKey !== state.route;
  const token = ++state.renderId;

  if (state.cleanup) {
    try {
      state.cleanup();
    } catch {
      /* A view cleanup must never block the next screen. */
    }
    state.cleanup = null;
  }
  destroyCharts();

  if (!screen) return;
  const previousScroll = window.scrollY;

  renderNav(route.nav);
  telegramBackButton(routeKey !== 'today');
  document.title = `${route.title} · Discipline OS`;

  if (!refresh || isNewRoute) {
    screen.innerHTML = loadingScreen();
    if (isNewRoute) window.scrollTo({ top: 0, behavior: 'auto' });
  }

  const ctx = {
    navigate(hash) {
      if (!hash) return;
      if (window.location.hash === hash) {
        renderRoute({ refresh: true });
        return;
      }
      window.location.hash = hash;
    },
    refresh() {
      return renderRoute({ refresh: true });
    },
    setFab(config) {
      setFab(config);
    },
  };

  try {
    const cleanup = await route.render(screen, ctx);
    if (token !== state.renderId) {
      if (typeof cleanup === 'function') cleanup();
      return;
    }
    state.cleanup = typeof cleanup === 'function' ? cleanup : null;
    state.route = routeKey;
    state.lastRenderedAt = Date.now();
    if (refresh) {
      window.scrollTo({ top: previousScroll, behavior: 'auto' });
    }
  } catch (error) {
    if (token !== state.renderId) return;
    if (refresh && screen.querySelector('.screen-head')) {
      toast(formatError(error), 'error');
      return;
    }
    screen.innerHTML = errorScreen(error);
    setFab(null);
    screen.querySelector('[data-retry]')?.addEventListener('click', () => {
      renderRoute({ refresh: false });
    });
  }
}

window.addEventListener('hashchange', () => {
  renderRoute();
});

initTelegram();
renderNav('today');
renderRoute();

// Keep the Mini App fresh after a long pause without interrupting forms.
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState !== 'visible') return;
  if (Date.now() - state.lastRenderedAt < 90_000) return;
  if (screen?.querySelector('input:focus, textarea:focus, select:focus')) return;
  renderRoute({ refresh: true });
});
