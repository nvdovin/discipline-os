import { api } from '../api.js';
import { icon } from '../icons.js';
import { escapeHtml, formatMinutes } from '../format.js';
import {
  clearFieldError,
  clearFieldErrors,
  formatError,
  haptic,
  refreshLink,
  screenHead,
  setFieldError,
  toast,
  withBusy,
} from '../ui.js';

const EXERCISES = [
  { key: 'pushups', name: 'Отжимания', kind: 'reps' },
  { key: 'pullups', name: 'Подтягивания', kind: 'reps' },
  { key: 'squats', name: 'Приседания', kind: 'reps' },
  { key: 'lunges', name: 'Выпады', kind: 'reps' },
  { key: 'plank', name: 'Планка', kind: 'seconds' },
  { key: 'walk', name: 'Прогулка', kind: 'minutes' },
  { key: 'mobility', name: 'Мобилити', kind: 'minutes' },
  { key: 'stretch', name: 'Растяжка', kind: 'minutes' },
];

function sleepMinutes(bedtime, wake) {
  if (!bedtime || !wake) return null;
  const [bedHour, bedMinute] = bedtime.split(':').map(Number);
  const [wakeHour, wakeMinute] = wake.split(':').map(Number);
  let minutes = wakeHour * 60 + wakeMinute - (bedHour * 60 + bedMinute);
  if (minutes <= 0) minutes += 24 * 60;
  return minutes;
}

function intValue(value) {
  const number = Number.parseInt(String(value ?? ''), 10);
  return Number.isFinite(number) ? number : null;
}

function selectHtml(id, options, selected) {
  return `
    <div class="select-wrap">
      <select class="select" id="${id}" name="${id}" aria-label="Часовой пояс">
        ${options
          .map(
            (option) =>
              `<option value="${escapeHtml(option.value)}"${option.value === selected ? ' selected' : ''}>${escapeHtml(option.label)}</option>`,
          )
          .join('')}
      </select>
      ${icon('chevron-down', 18)}
    </div>
  `;
}

function mealRowHtml(time) {
  return `
    <div class="time-item" data-meal-row>
      <input class="input" type="time" value="${escapeHtml(time)}" aria-label="Время приёма пищи" data-meal-input>
      <button class="icon-btn" type="button" data-meal-remove aria-label="Удалить время приёма">
        ${icon('trash', 18)}
      </button>
    </div>
  `;
}

function exerciseRowHtml(item, target) {
  const sets = target?.sets ?? 1;
  const value =
    item.kind === 'reps'
      ? target?.reps ?? 1
      : item.kind === 'seconds'
        ? target?.duration_seconds ?? 30
        : Math.round((target?.duration_seconds ?? 600) / 60);
  const unit = item.kind === 'reps' ? 'повт.' : item.kind === 'seconds' ? 'сек' : 'мин';
  return `
    <div class="exercise-target-row">
      <span class="exercise-target-row__name">${escapeHtml(item.name)} <span class="muted">· ${unit}</span></span>
      <input class="input" type="number" min="1" max="10" step="1" inputmode="numeric"
        value="${sets}" aria-label="${escapeHtml(item.name)}: подходы" data-ex-sets="${item.key}">
      <input class="input" type="number" min="1" step="1" inputmode="numeric"
        value="${value}" aria-label="${escapeHtml(item.name)}: ${unit}" data-ex-value="${item.key}">
    </div>
  `;
}

function reminderRowHtml(reminder) {
  return `
    <div class="settings-row">
      <div class="settings-row__text">
        <div class="settings-row__title">${escapeHtml(reminder.title)}</div>
        <div class="settings-row__hint">${reminder.enabled ? 'Напоминание включено' : 'Напоминание выключено'}</div>
      </div>
      <div class="settings-row__control">
        <input class="input" type="time" value="${escapeHtml(reminder.time)}"
          aria-label="Время напоминания: ${escapeHtml(reminder.title)}" data-reminder-time="${escapeHtml(reminder.key)}">
      </div>
      <label class="switch">
        <input type="checkbox" ${reminder.enabled ? 'checked' : ''}
          aria-label="Включить напоминание: ${escapeHtml(reminder.title)}"
          data-reminder-toggle="${escapeHtml(reminder.key)}">
        <span class="switch__track" aria-hidden="true"></span>
      </label>
    </div>
  `;
}

function collect(data, root) {
  const timezone = root.querySelector('#timezone')?.value;
  const bedtime = root.querySelector('#bedtime')?.value;
  const wake = root.querySelector('#wake')?.value;
  const meals = Array.from(root.querySelectorAll('[data-meal-input]'))
    .map((input) => input.value)
    .filter(Boolean);
  const protein = intValue(root.querySelector('#protein')?.value);
  const water = intValue(root.querySelector('#water')?.value);
  const bible = intValue(root.querySelector('#bible')?.value);

  const exerciseTargets = {};
  for (const item of EXERCISES) {
    const sets = intValue(root.querySelector(`[data-ex-sets="${item.key}"]`)?.value);
    const value = intValue(root.querySelector(`[data-ex-value="${item.key}"]`)?.value);
    if (item.kind === 'reps') {
      exerciseTargets[item.key] = { sets, reps: value };
    } else if (item.kind === 'seconds') {
      exerciseTargets[item.key] = { sets, duration_seconds: value };
    } else {
      exerciseTargets[item.key] = { sets, duration_seconds: value === null ? null : value * 60 };
    }
  }

  const reminders = (data.reminders || []).map((reminder) => {
    const time = root.querySelector(`[data-reminder-time="${reminder.key}"]`)?.value;
    const enabled = Boolean(
      root.querySelector(`[data-reminder-toggle="${reminder.key}"]`)?.checked,
    );
    return { key: reminder.key, time, enabled };
  });

  return {
    timezone,
    bedtime,
    wake_up_time: wake,
    meal_times: meals,
    protein_target_g: protein,
    water_target_ml: water,
    bible_target_minutes: bible,
    exercise_targets: exerciseTargets,
    reminders,
  };
}

function validate(payload) {
  if (!payload.timezone) return { message: 'Выберите часовой пояс', field: '#timezone' };
  if (!payload.bedtime || !payload.wake_up_time) {
    return { message: 'Укажите время отбоя и подъёма', field: '#bedtime' };
  }
  const duration = sleepMinutes(payload.bedtime, payload.wake_up_time);
  if (duration === null || duration < 240 || duration > 720) {
    return {
      message: 'Целевой сон должен быть от 4 до 12 часов. Проверьте отбой и подъём.',
      field: '#bedtime',
    };
  }
  if (!payload.meal_times.length || payload.meal_times.length > 4) {
    return { message: 'Укажите от 1 до 4 приёмов пищи', field: '[data-meal-input]' };
  }
  if (new Set(payload.meal_times).size !== payload.meal_times.length) {
    return { message: 'Время приёмов пищи не должно повторяться', field: '[data-meal-input]' };
  }
  if (!payload.protein_target_g || payload.protein_target_g < 40 || payload.protein_target_g > 300) {
    return { message: 'Белок: от 40 до 300 г', field: '#protein' };
  }
  if (!payload.water_target_ml || payload.water_target_ml < 500 || payload.water_target_ml > 6000) {
    return { message: 'Вода: от 500 до 6000 мл', field: '#water' };
  }
  if (!payload.bible_target_minutes || payload.bible_target_minutes < 5 || payload.bible_target_minutes > 240) {
    return { message: 'Библия: от 5 до 240 минут', field: '#bible' };
  }
  for (const item of EXERCISES) {
    const target = payload.exercise_targets[item.key];
    if (!target.sets || target.sets < 1 || target.sets > 10) {
      return { message: `${item.name}: подходов от 1 до 10`, field: `[data-ex-sets="${item.key}"]` };
    }
    const value = item.kind === 'reps' ? target.reps : target.duration_seconds;
    if (!value || value < 1) {
      return { message: `${item.name}: укажите положительное значение`, field: `[data-ex-value="${item.key}"]` };
    }
    if (item.kind === 'reps' && value > 100) {
      return { message: `${item.name}: не больше 100 повторений`, field: `[data-ex-value="${item.key}"]` };
    }
    if (item.kind === 'minutes' && value > 7200) {
      return { message: `${item.name}: не больше 120 минут`, field: `[data-ex-value="${item.key}"]` };
    }
    if (item.kind === 'seconds' && value > 7200) {
      return { message: `${item.name}: не больше 7200 секунд`, field: `[data-ex-value="${item.key}"]` };
    }
  }
  for (const reminder of payload.reminders) {
    if (!reminder.time) {
      return { message: 'У каждого напоминания должно быть время', field: `[data-reminder-time="${reminder.key}"]` };
    }
  }
  return null;
}

export async function render(root, ctx) {
  const data = await api.settings();
  const schedule = data.schedule;
  const targets = data.targets;
  const profile = data.profile;
  const telegram = data.telegram;
  const app = data.app;
  const initialSleep = sleepMinutes(schedule.bedtime, schedule.wake_up_time);

  root.innerHTML = `
    ${screenHead({
      eyebrow: 'Личные правила',
      title: 'Настройки',
      subtitle: 'Ритм, цели и напоминания. Всё можно изменить без потери истории.',
      actions: refreshLink(),
    })}

    <div class="settings-grid">
      <div class="settings-col">
        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('clock', 18)} Ритм дня</h2>
              <p class="card__sub">Часовой пояс влияет на «сегодня», статистику и напоминания.</p>
            </div>
          </div>

          <div class="settings-row settings-row--stack">
            <div class="settings-row__text">
              <div class="settings-row__title">Часовой пояс</div>
              <div class="settings-row__hint">Локальное время для всех расчётов.</div>
            </div>
            <div class="settings-row__control settings-row__control--wide">
              ${selectHtml('timezone', data.timezones || [], profile.timezone)}
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__text">
              <div class="settings-row__title">Отбой</div>
              <div class="settings-row__hint">Целевое время, не дедлайн.</div>
            </div>
            <div class="settings-row__control">
              <input class="input" id="bedtime" type="time" value="${escapeHtml(schedule.bedtime)}" aria-label="Целевое время отбоя">
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__text">
              <div class="settings-row__title">Подъём</div>
              <div class="settings-row__hint">Целевое время пробуждения.</div>
            </div>
            <div class="settings-row__control">
              <input class="input" id="wake" type="time" value="${escapeHtml(schedule.wake_up_time)}" aria-label="Целевое время подъёма">
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__text">
              <div class="settings-row__title">Целевой сон</div>
              <div class="settings-row__hint" id="sleep-summary">${formatMinutes(initialSleep)} · норма 4–12 ч</div>
            </div>
            <span class="pill pill--info" id="sleep-pill">${formatMinutes(initialSleep)}</span>
          </div>

          <div class="divider"></div>

          <div class="row row--between">
            <div>
              <div class="settings-row__title">Приёмы пищи</div>
              <div class="settings-row__hint">От 1 до 4 ориентировочных времён.</div>
            </div>
            <button class="btn btn--secondary btn--sm" type="button" data-meal-add>
              ${icon('plus', 15)} Время
            </button>
          </div>
          <div class="time-list mt-2" data-meal-list>
            ${(schedule.meal_times || []).map(mealRowHtml).join('')}
          </div>
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('target', 18)} Дневные цели</h2>
              <p class="card__sub">Ориентиры, а не жёсткие нормативы.</p>
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__text">
              <div class="settings-row__title">Белок</div>
              <div class="settings-row__hint">Основной ориентир питания.</div>
            </div>
            <div class="settings-row__control">
              <div class="input-wrap">
                <input class="input" id="protein" type="number" min="40" max="300" step="5"
                  inputmode="numeric" value="${targets.protein_target_g}" aria-label="Цель по белку, граммы">
                <span class="input-suffix">г</span>
              </div>
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__text">
              <div class="settings-row__title">Вода</div>
              <div class="settings-row__hint">Спокойный дневной ориентир.</div>
            </div>
            <div class="settings-row__control">
              <div class="input-wrap">
                <input class="input" id="water" type="number" min="500" max="6000" step="100"
                  inputmode="numeric" value="${targets.water_target_ml}" aria-label="Цель по воде, миллилитры">
                <span class="input-suffix">мл</span>
              </div>
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__text">
              <div class="settings-row__title">Библия</div>
              <div class="settings-row__hint">Время в Слове, без гонки за минутами.</div>
            </div>
            <div class="settings-row__control">
              <div class="input-wrap">
                <input class="input" id="bible" type="number" min="5" max="240" step="5"
                  inputmode="numeric" value="${targets.bible_target_minutes}" aria-label="Цель по чтению Библии, минуты">
                <span class="input-suffix">мин</span>
              </div>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('dumbbell', 18)} Тренировка</h2>
              <p class="card__sub">Базовые цели. Минимум и восстановительные дни учтены отдельно.</p>
            </div>
          </div>

          <details class="details" open>
            <summary>
              Настроить упражнения
              ${icon('chevron-down', 18)}
            </summary>
            <div class="exercise-target-head">
              <span>Упражнение</span>
              <span>Подх.</span>
              <span>Цель</span>
            </div>
            ${EXERCISES.map((item) => exerciseRowHtml(item, targets.exercise_targets?.[item.key])).join('')}
            <p class="field__hint">Прогулка, мобилити и растяжка задаются в минутах, планка — в секундах.</p>
          </details>
        </section>
      </div>

      <div class="settings-col">
        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('send', 18)} Напоминания</h2>
              <p class="card__sub">Приходят в Telegram. После перезапуска восстанавливаются без дублей.</p>
            </div>
            <span class="pill pill--outline">${(data.reminders || []).filter((item) => item.enabled).length} вкл.</span>
          </div>
          ${(data.reminders || []).map(reminderRowHtml).join('')}
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('download', 18)} Данные</h2>
              <p class="card__sub">Полная выгрузка в JSON: настройки, сон, тренировки, питание, рефлексии.</p>
            </div>
          </div>
          <button class="btn btn--secondary btn--block" type="button" data-export>
            ${icon('download', 17)} Скачать выгрузку
          </button>
          <p class="field__hint mt-2">Файл содержит личные данные. Храните его в надёжном месте.</p>
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('lock', 18)} Доступ</h2>
              <p class="card__sub">Приложение личное: только ваш Telegram-аккаунт.</p>
            </div>
          </div>
          <div class="about-list">
            <div class="about-row"><span>Владелец</span><strong>${profile.telegram_user_id ? `ID ${profile.telegram_user_id}` : 'первый /start'}</strong></div>
            <div class="about-row"><span>Проверка initData</span><strong>${profile.dev_mode ? 'dev-режим' : 'включена'}</strong></div>
            <div class="about-row"><span>Бот</span><strong>${telegram.bot_configured ? 'подключён' : 'не настроен'}</strong></div>
            <div class="about-row"><span>Mini App URL</span><strong>${telegram.webapp_url ? escapeHtml(telegram.webapp_url) : 'не задан'}</strong></div>
            <div class="about-row"><span>Версия</span><strong>${escapeHtml(app.version)}</strong></div>
            <div class="about-row"><span>Среда</span><strong>${escapeHtml(app.environment)}</strong></div>
          </div>
          ${
            telegram.webapp_url
              ? ''
              : `<p class="field__hint mt-3">Пока URL не задан, кнопка «Открыть приложение» в боте скрыта. Укажите WEBAPP_URL в .env.</p>`
          }
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('info', 18)} Как это работает</h2>
            </div>
          </div>
          <div class="stack">
            <p class="small muted">День считается успешным, когда закрыто 60% привычек — это 3 из 5.</p>
            <p class="small muted">Привычки можно отмечать вручную или добавлять данные: сон, подходы, приёмы пищи, минуты Библии. Прогресс посчитается сам.</p>
            <p class="small muted">Пропущенный день не обнуляет историю. Серия продолжается со следующего шага.</p>
          </div>
        </section>
      </div>
    </div>

    <div class="save-bar">
      <button class="btn btn--secondary btn--sm" type="button" data-reset>Сбросить</button>
      <button class="btn btn--primary" type="button" data-save>Сохранить настройки</button>
    </div>
  `;

  const sleepSummary = root.querySelector('#sleep-summary');
  const sleepPill = root.querySelector('#sleep-pill');
  const updateSleep = () => {
    const minutes = sleepMinutes(
      root.querySelector('#bedtime')?.value,
      root.querySelector('#wake')?.value,
    );
    if (sleepPill) sleepPill.textContent = formatMinutes(minutes);
    if (sleepSummary) {
      const invalid = minutes === null || minutes < 240 || minutes > 720;
      sleepSummary.textContent = invalid
        ? 'Проверьте время: норма 4–12 часов'
        : `${formatMinutes(minutes)} · норма 4–12 ч`;
      sleepSummary.classList.toggle('text-danger', invalid);
    }
  };
  root.querySelector('#bedtime')?.addEventListener('input', updateSleep);
  root.querySelector('#wake')?.addEventListener('input', updateSleep);

  const mealList = root.querySelector('[data-meal-list]');
  const addMeal = root.querySelector('[data-meal-add]');
  const syncMealControls = () => {
    const rows = mealList ? Array.from(mealList.querySelectorAll('[data-meal-row]')) : [];
    if (addMeal) addMeal.disabled = rows.length >= 4;
    rows.forEach((row) => {
      const remove = row.querySelector('[data-meal-remove]');
      if (remove) remove.disabled = rows.length <= 1;
    });
  };

  root.querySelectorAll('[data-meal-remove]').forEach((button) => {
    button.addEventListener('click', () => {
      const rows = mealList ? Array.from(mealList.querySelectorAll('[data-meal-row]')) : [];
      if (rows.length <= 1) return;
      button.closest('[data-meal-row]')?.remove();
      syncMealControls();
    });
  });

  addMeal?.addEventListener('click', () => {
    const rows = mealList ? Array.from(mealList.querySelectorAll('[data-meal-row]')) : [];
    if (rows.length >= 4) return;
    const last = rows[rows.length - 1]?.querySelector('input')?.value || '12:00';
    const [hour, minute] = last.split(':').map(Number);
    const next = `${String((hour + 4) % 24).padStart(2, '0')}:${String(minute || 0).padStart(2, '0')}`;
    mealList.insertAdjacentHTML('beforeend', mealRowHtml(next));
    const newRow = mealList.lastElementChild;
    newRow?.querySelector('[data-meal-remove]')?.addEventListener('click', () => {
      const currentRows = mealList ? Array.from(mealList.querySelectorAll('[data-meal-row]')) : [];
      if (currentRows.length <= 1) return;
      newRow.remove();
      syncMealControls();
    });
    syncMealControls();
    newRow?.querySelector('input')?.focus();
  });

  syncMealControls();

  root.querySelectorAll('[data-reminder-toggle]').forEach((input) => {
    input.addEventListener('change', () => {
      const hint = input.closest('.settings-row')?.querySelector('.settings-row__hint');
      if (hint) hint.textContent = input.checked ? 'Напоминание включено' : 'Напоминание выключено';
    });
  });

  root.querySelector('[data-refresh]')?.addEventListener('click', () => ctx.refresh());
  root.querySelector('[data-reset]')?.addEventListener('click', () => ctx.refresh());

  root.querySelector('[data-export]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    await withBusy(button, async () => {
      try {
        await api.downloadExport();
        haptic('success');
        toast('Выгрузка готова', 'success');
      } catch (error) {
        haptic('error');
        toast(formatError(error), 'error');
      }
    });
  });

  root.addEventListener('input', (event) => {
    const target = event.target;
    if (target instanceof HTMLElement && target.matches('input, textarea, select')) {
      clearFieldError(target);
    }
  });

  root.querySelector('[data-save]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    clearFieldErrors(root);
    const payload = collect(data, root);
    const problem = validate(payload);
    if (problem) {
      const field = root.querySelector(problem.field);
      if (field) setFieldError(field, problem.message);
      else toast(problem.message, 'error');
      return;
    }
    await withBusy(button, async () => {
      try {
        await api.saveSettings(payload);
        haptic('success');
        toast('Настройки сохранены', 'success');
        await ctx.refresh();
      } catch (error) {
        haptic('error');
        toast(formatError(error), 'error');
      }
    });
  });

  ctx.setFab(null);

  return null;
}
