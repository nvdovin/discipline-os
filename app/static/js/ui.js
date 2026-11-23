import { escapeHtml, clamp } from './format.js';
import { icon } from './icons.js';

/* ---------- Toasts ---------- */

export function toast(message, tone = 'default', { duration = 3200 } = {}) {
  const root = document.getElementById('toast-root');
  if (!root) return;

  // Keep the toast below the screen title instead of covering the H1.
  const head = document.querySelector('.screen-head');
  if (head) {
    const bottom = head.getBoundingClientRect().bottom;
    root.style.top = `${Math.max(12, Math.round(bottom + 8))}px`;
  } else {
    root.style.top = '';
  }

  const iconName = tone === 'success' ? 'check-circle' : tone === 'error' ? 'alert' : 'info';
  const element = document.createElement('div');
  element.className = `toast toast--${tone}`;
  element.setAttribute('role', tone === 'error' ? 'alert' : 'status');
  element.innerHTML = `<span class="toast__icon">${icon(iconName, 16)}</span><span>${escapeHtml(message)}</span>`;
  root.appendChild(element);

  window.setTimeout(() => {
    element.style.opacity = '0';
    element.style.transform = 'translateY(-4px)';
    window.setTimeout(() => element.remove(), 220);
  }, duration);
}

export function setFieldError(input, message) {
  if (!input) return;
  const field = input.closest('.field');
  const row = input.closest('.settings-row, .exercise-target-row');
  let error = null;
  const describedBy = input.getAttribute('aria-describedby');
  if (describedBy) {
    const candidate = document.getElementById(describedBy);
    if (candidate?.classList.contains('field__error')) error = candidate;
  }
  if (!error) {
    error = document.createElement('p');
    error.className = 'field__error';
    error.id = `${input.id || 'field'}-error`;
    if (field) field.appendChild(error);
    else if (row) row.insertAdjacentElement('afterend', error);
    else (input.parentElement || input).appendChild(error);
  }
  error.textContent = message;
  input.setAttribute('aria-invalid', 'true');
  input.setAttribute('aria-describedby', error.id);
  input.focus({ preventScroll: false });
}

export function clearFieldError(input) {
  if (!input) return;
  input.removeAttribute('aria-invalid');
  const describedBy = input.getAttribute('aria-describedby');
  if (describedBy) {
    const error = document.getElementById(describedBy);
    if (error?.classList.contains('field__error')) error.remove();
    input.removeAttribute('aria-describedby');
  }
}

export function clearFieldErrors(scope) {
  if (!scope) return;
  scope.querySelectorAll('[aria-invalid="true"]').forEach((input) => clearFieldError(input));
}

export function formatError(error) {
  if (error?.name === 'ApiError' && error.message) return error.message;
  if (error?.message) return error.message;
  return 'Что-то пошло не так. Попробуйте ещё раз.';
}

/* ---------- Haptics ---------- */

export function haptic(type = 'light') {
  try {
    const feedback = window.Telegram?.WebApp?.HapticFeedback;
    if (!feedback) return;
    if (type === 'success' || type === 'error' || type === 'warning') {
      feedback.notificationOccurred(type);
      return;
    }
    feedback.impactOccurred(type);
  } catch {
    /* Telegram WebApp may be unavailable in a browser. */
  }
}

/* ---------- Busy state ---------- */

export async function withBusy(button, task) {
  if (!button) return task();
  button.classList.add('is-busy');
  button.disabled = true;
  try {
    return await task();
  } finally {
    button.classList.remove('is-busy');
    button.disabled = false;
  }
}

/* ---------- Header helpers ---------- */

export function screenHead({ eyebrow = '', title, subtitle = '', actions = '', back = '' }) {
  const eyebrowHtml = eyebrow
    ? `<p class="eyebrow"><span class="eyebrow__dot" aria-hidden="true"></span>${escapeHtml(eyebrow)}</p>`
    : '';
  const backHtml = back
    ? `<a class="icon-btn" href="${escapeHtml(back)}" aria-label="Назад">${icon('arrow-left', 20)}</a>`
    : '';
  return `
    <header class="screen-head">
      <div class="screen-head__text">
        ${eyebrowHtml}
        <h1 class="screen-title">${escapeHtml(title)}</h1>
        ${subtitle ? `<p class="screen-subtitle">${escapeHtml(subtitle)}</p>` : ''}
      </div>
      <div class="head-actions">
        ${backHtml}
        ${actions}
      </div>
    </header>
  `;
}

export function settingsLink() {
  return `<a class="icon-btn" href="#/settings" aria-label="Настройки" title="Настройки">${icon('settings', 20)}</a>`;
}

export function refreshLink() {
  return `<button class="icon-btn" type="button" data-refresh aria-label="Обновить" title="Обновить">${icon('refresh', 20)}</button>`;
}

/* ---------- Rings / progress / pills ---------- */

export function ring({ value = 0, tone = 'accent', size = '', number = null, label = '', ariaLabel = '' }) {
  const percent = clamp(Math.round(Number(value) || 0), 0, 100);
  const sizeClass = size ? ` ring--${size}` : '';
  const display = number === null || number === undefined ? `${percent}%` : String(number);
  const accessible = ariaLabel || `${display}${label ? `, ${label}` : ''}`;
  return `
    <div class="ring ring--${tone}${sizeClass}" role="img" aria-label="${escapeHtml(accessible)}">
      <svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">
        <circle class="ring__track" cx="60" cy="60" r="52" pathLength="100"></circle>
        <circle class="ring__value" cx="60" cy="60" r="52" pathLength="100"
          stroke-dasharray="100" stroke-dashoffset="${100 - percent}"></circle>
      </svg>
      <div class="ring__center">
        <span class="ring__number">${escapeHtml(display)}</span>
        ${label ? `<span class="ring__label">${escapeHtml(label)}</span>` : ''}
      </div>
    </div>
  `;
}

export function progressBar(value, tone = '', { thin = false } = {}) {
  const percent = clamp(Number(value) || 0, 0, 100);
  const toneClass = tone ? ` progress--${tone}` : '';
  const thinClass = thin ? ' progress--thin' : '';
  return `
    <div class="progress${toneClass}${thinClass}" role="progressbar"
      aria-valuenow="${Math.round(percent)}" aria-valuemin="0" aria-valuemax="100">
      <div class="progress__bar" style="width:${percent}%"></div>
    </div>
  `;
}

export function pill(text, tone = '', iconName = '') {
  const toneClass = tone ? ` pill--${tone}` : '';
  return `<span class="pill${toneClass}">${iconName ? icon(iconName, 13) : ''}${escapeHtml(text)}</span>`;
}

/* ---------- Empty state ---------- */

export function emptyState({ iconName = 'info', title, text = '', action = '' }) {
  return `
    <div class="empty">
      <span class="empty__icon">${icon(iconName, 22)}</span>
      <p class="empty__title">${escapeHtml(title)}</p>
      ${text ? `<p class="empty__text">${escapeHtml(text)}</p>` : ''}
      ${action}
    </div>
  `;
}

/* ---------- Sheets ---------- */

let currentClose = null;

function focusable(container) {
  return Array.from(
    container.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => element.offsetParent !== null || element === document.activeElement);
}

export function openSheet({ title, subtitle = '', content = '', footer = '', onMount = null }) {
  const root = document.getElementById('sheet-root');
  if (!root) return () => {};

  if (currentClose) currentClose({ silent: true });

  const previousFocus = document.activeElement;
  const titleId = `sheet-title-${Date.now()}`;
  root.className = 'sheet-root is-open';
  root.innerHTML = `
    <button class="sheet-backdrop" type="button" aria-label="Закрыть" data-sheet-backdrop></button>
    <section class="sheet" role="dialog" aria-modal="true" aria-labelledby="${titleId}">
      <div class="sheet__grab" aria-hidden="true"></div>
      <div class="sheet__head">
        <div>
          <h2 class="sheet__title" id="${titleId}">${escapeHtml(title)}</h2>
          ${subtitle ? `<p class="sheet__sub">${escapeHtml(subtitle)}</p>` : ''}
        </div>
        <button class="icon-btn" type="button" data-sheet-close aria-label="Закрыть">${icon('x', 20)}</button>
      </div>
      <div class="sheet__body" data-sheet-body>${content}</div>
      ${footer ? `<div class="sheet__footer" data-sheet-footer>${footer}</div>` : ''}
    </section>
  `;

  const sheet = root.querySelector('.sheet');
  const body = root.querySelector('[data-sheet-body]');
  const footerElement = root.querySelector('[data-sheet-footer]');
  let closed = false;

  const close = ({ silent = false } = {}) => {
    if (closed) return;
    closed = true;
    currentClose = null;
    document.removeEventListener('keydown', onKeyDown);
    root.classList.remove('is-visible');
    document.body.classList.remove('is-locked');
    window.setTimeout(() => {
      if (!root.classList.contains('is-open')) return;
      root.className = '';
      root.innerHTML = '';
    }, 280);
    if (!silent && previousFocus instanceof HTMLElement) {
      previousFocus.focus({ preventScroll: true });
    }
  };

  const onKeyDown = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== 'Tab') return;
    const items = focusable(sheet);
    if (!items.length) {
      event.preventDefault();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  root.querySelector('[data-sheet-close]')?.addEventListener('click', () => close());
  root.querySelector('[data-sheet-backdrop]')?.addEventListener('click', () => close());
  document.addEventListener('keydown', onKeyDown);
  document.body.classList.add('is-locked');
  currentClose = close;

  window.requestAnimationFrame(() => {
    root.classList.add('is-visible');
    const target = focusable(body)[0] || focusable(footerElement || sheet)[0] || sheet;
    target?.focus?.({ preventScroll: true });
  });

  body.addEventListener('input', (event) => {
    const target = event.target;
    if (target instanceof HTMLElement && target.matches('input, textarea, select')) {
      clearFieldError(target);
    }
  });

  if (typeof onMount === 'function') {
    onMount({ body, footer: footerElement, close, sheet });
  }

  return close;
}

export function closeSheet() {
  if (currentClose) currentClose({ silent: true });
}

export function confirmSheet({
  title,
  message,
  confirmLabel = 'Удалить',
  cancelLabel = 'Отмена',
  tone = 'danger',
  onConfirm,
}) {
  const buttonClass = tone === 'danger' ? 'btn--danger' : 'btn--primary';
  return openSheet({
    title,
    content: `<p class="small muted">${escapeHtml(message)}</p>`,
    footer: `
      <button class="btn btn--secondary" type="button" data-confirm-cancel>${escapeHtml(cancelLabel)}</button>
      <button class="btn ${buttonClass}" type="button" data-confirm-ok>${escapeHtml(confirmLabel)}</button>
    `,
    onMount({ footer, close }) {
      footer.querySelector('[data-confirm-cancel]')?.addEventListener('click', () => close());
      footer.querySelector('[data-confirm-ok]')?.addEventListener('click', async (event) => {
        const button = event.currentTarget;
        await withBusy(button, async () => {
          try {
            await onConfirm();
            haptic('success');
            close();
          } catch (error) {
            haptic('error');
            toast(formatError(error), 'error');
          }
        });
      });
    },
  });
}
