import { api } from '../api.js';
import { icon } from '../icons.js';
import {
  escapeHtml,
  formatMinutesShort,
  formatNumber,
  formatSeconds,
  plural,
  shortDate,
} from '../format.js';
import {
  clearFieldErrors,
  confirmSheet,
  emptyState,
  formatError,
  haptic,
  openSheet,
  pill,
  progressBar,
  refreshLink,
  ring,
  screenHead,
  setFieldError,
  settingsLink,
  toast,
  withBusy,
} from '../ui.js';
import { destroyCharts, lineChart } from '../charts.js';

const PROGRESSION_TABS = [
  { key: 'pushups', label: 'Отжимания', tone: 'accent', unit: 'повт.' },
  { key: 'pullups', label: 'Подтягивания', tone: 'success', unit: 'повт.' },
  { key: 'plank', label: 'Планка', tone: 'violet', unit: 'сек' },
];

function exerciseMeta(exercise) {
  const rest = exercise.rest_seconds ? ` · отдых ${exercise.rest_seconds} с` : '';
  if (exercise.kind === 'reps') {
    return `${exercise.sets} × ${exercise.reps} повт.${rest}`;
  }
  return `${exercise.target || `${exercise.sets} ${plural(exercise.sets, ['подход', 'подхода', 'подходов'])}`}${rest}`;
}

function setLabel(item, kind) {
  if (kind === 'reps' || item.repetitions) {
    return `${item.repetitions} повт.`;
  }
  return formatSeconds(item.duration_seconds);
}

function statusLabel(exercise) {
  if (exercise.done_sets >= exercise.sets) return pill('Цель', 'success', 'check');
  if (exercise.done_sets > 0) return pill(`${exercise.done_sets}/${exercise.sets}`, 'accent');
  return pill(`${exercise.sets} подх.`, 'outline');
}

function exerciseHtml(exercise, primary = false) {
  const kind = exercise.kind;
  const doneSets = Math.min(Number(exercise.done_sets) || 0, 12);
  const targetDots = Math.min(Number(exercise.sets) || 0, 12);
  const dots = Array.from({ length: Math.max(targetDots, doneSets) }, (_, index) => {
    return `<span class="set-dot${index < doneSets ? ' set-dot--done' : ''}"></span>`;
  }).join('');

  const sets = Array.isArray(exercise.logged_sets) ? exercise.logged_sets : [];
  const chips = sets.length
    ? `
      <div class="set-row">
        ${sets
          .map(
            (item) => `
            <button class="set-chip" type="button" data-delete-set="${item.id}"
              aria-label="Удалить подход ${escapeHtml(setLabel(item, kind))}">
              ${escapeHtml(setLabel(item, kind))}
              ${icon('x', 13)}
            </button>
          `,
          )
          .join('')}
      </div>
    `
    : '';

  return `
    <div class="exercise">
      <div class="exercise__head">
        <span class="exercise__icon">${icon(kind === 'reps' ? 'dumbbell' : 'timer', 19)}</span>
        <div class="exercise__text">
          <h3 class="exercise__title">${escapeHtml(exercise.name)}</h3>
          <p class="exercise__meta">${escapeHtml(exerciseMeta(exercise))}</p>
          ${exercise.note ? `<p class="exercise__note">${escapeHtml(exercise.note)}</p>` : ''}
        </div>
        <button class="btn ${primary ? 'btn--primary' : 'btn--secondary'} btn--sm exercise__action" type="button"
          data-add-set="${escapeHtml(exercise.key)}"
          aria-label="Добавить подход: ${escapeHtml(exercise.name)}">
          ${icon('plus', 16)} Подход
        </button>
      </div>
      <div class="set-dots" aria-hidden="true">${dots}</div>
      ${chips}
    </div>
  `;
}

function recordsHtml(records) {
  const items = [
    {
      value: records.pushups ? formatNumber(records.pushups) : '—',
      label: 'отжиманий',
    },
    {
      value: records.pullups_day ? formatNumber(records.pullups_day) : '—',
      label: 'подтягиваний за день',
    },
    {
      value: records.plank_seconds ? formatSeconds(records.plank_seconds) : '—',
      label: 'планка, рекорд',
    },
  ];
  return items
    .map(
      (item) => `
      <div class="record">
        <strong>${escapeHtml(item.value)}</strong>
        <span>${escapeHtml(item.label)}</span>
      </div>
    `,
    )
    .join('');
}

function weekHtml(week) {
  const items = Array.isArray(week) ? week : [];
  return items
    .map((item) => {
      const statusClass = item.status === 'done'
        ? ' week-chip--done'
        : item.status === 'partial'
          ? ' week-chip--partial'
          : item.status === 'planned'
            ? ' week-chip--planned'
            : '';
      const todayClass = item.is_today ? ' week-chip--today' : '';
      return `
        <div class="week-chip${statusClass}${todayClass}" title="${escapeHtml(item.title)}">
          <span class="week-chip__day">${escapeHtml(item.weekday_short)}</span>
          <span class="week-chip__num">${item.day}</span>
          <span class="week-chip__dot" aria-hidden="true"></span>
        </div>
      `;
    })
    .join('');
}

function historyHtml(history) {
  if (!history?.length) {
    return emptyState({
      iconName: 'dumbbell',
      title: 'Пока нет завершённых тренировок',
      text: 'Любая активность считается: прогулка, растяжка или один подход.',
    });
  }
  return history
    .slice(0, 8)
    .map(
      (item) => `
      <div class="history-row">
        <div class="history-row__date">
          <strong>${escapeHtml(shortDate(item.date))}</strong>
          ${escapeHtml(item.weekday_short)}
        </div>
        <div class="history-row__main">
          <div class="history-row__title">${escapeHtml(item.title)}</div>
          <div class="history-row__meta">
            ${item.sets_count ? `${item.sets_count} ${plural(item.sets_count, ['подход', 'подхода', 'подходов'])}` : 'без подходов'}
            ${item.duration_minutes ? ` · ${formatMinutesShort(item.duration_minutes)}` : ''}
            ${item.mode === 'minimum' ? ' · минимум' : ''}
          </div>
        </div>
        ${item.status === 'completed' ? pill('Готово', 'success') : pill('В работе', 'outline')}
      </div>
    `,
    )
    .join('');
}

function openSetSheet({ day, exercise, mode, ctx, refresh }) {
  const kind = exercise.kind;
  const isLongDuration = kind === 'duration' && (exercise.duration_seconds || 0) >= 300;
  const durationUnit = isLongDuration ? 'минуты' : 'секунды';
  const durationValue = isLongDuration
    ? Math.round((exercise.duration_seconds || 300) / 60)
    : exercise.duration_seconds || 30;
  const quickValues = kind === 'reps'
    ? [exercise.reps, Math.max(1, (exercise.reps || 10) - 2), (exercise.reps || 10) + 2]
    : isLongDuration
      ? [5, 10, 20, 30]
      : [20, 30, 40, 60, 90];

  openSheet({
    title: `Подход · ${exercise.name}`,
    subtitle: kind === 'reps'
      ? `Цель: ${exercise.sets} × ${exercise.reps} повторений.`
      : `Цель: ${exercise.target}.`,
    content: `
      <form class="form" id="set-form" novalidate>
        <div class="field">
          <label class="field__label" for="set-value">
            ${kind === 'reps' ? 'Повторения' : durationUnit}
          </label>
          <div class="stepper">
            <button class="stepper__btn" type="button" data-step="-1" aria-label="Уменьшить">${icon('minus', 20)}</button>
            <input class="stepper__input" id="set-value" type="number" name="value"
              min="1" max="${kind === 'reps' ? 200 : isLongDuration ? 120 : 7200}"
              step="1" value="${durationValue}" inputmode="numeric">
            <button class="stepper__btn" type="button" data-step="1" aria-label="Увеличить">${icon('plus', 20)}</button>
          </div>
          <div class="chip-row mt-2">
            ${quickValues
              .map(
                (value) => `<button class="chip" type="button" data-quick-value="${value}">${value}</button>`,
              )
              .join('')}
          </div>
        </div>
        <div class="field">
          <label class="field__label" for="set-rest">Отдых после подхода, секунды</label>
          <input class="input" id="set-rest" type="number" name="rest" min="0" max="600"
            step="5" value="${exercise.rest_seconds || 0}" inputmode="numeric">
          <p class="field__hint">Можно оставить 0, если отдых не важен.</p>
        </div>
      </form>
    `,
    footer: `
      <button class="btn btn--secondary" type="button" data-sheet-cancel>Отмена</button>
      <button class="btn btn--primary" type="submit" form="set-form">Записать</button>
    `,
    onMount({ body, footer, close }) {
      const input = body.querySelector('#set-value');
      const step = kind === 'reps' ? 1 : 5;
      const adjust = (delta) => {
        const max = kind === 'reps' ? 200 : isLongDuration ? 120 : 7200;
        input.value = String(Math.max(1, Math.min(max, (Number(input.value) || 0) + delta)));
      };
      body.querySelectorAll('[data-step]').forEach((button) => {
        button.addEventListener('click', () => adjust(Number(button.dataset.step) * step));
      });
      body.querySelectorAll('[data-quick-value]').forEach((button) => {
        button.addEventListener('click', () => {
          input.value = button.dataset.quickValue;
        });
      });
      footer.querySelector('[data-sheet-cancel]')?.addEventListener('click', () => close());

      body.querySelector('#set-form')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = footer.querySelector('button[type="submit"]');
        clearFieldErrors(form);
        const raw = Number(form.elements.value.value);
        const rest = Math.max(0, Math.min(600, Math.round(Number(form.elements.rest.value) || 0)));
        if (!Number.isFinite(raw) || raw < 1) {
          setFieldError(input, 'Укажите положительное значение');
          return;
        }
        const payload = {
          date: day.date,
          exercise_key: exercise.key,
          rest_seconds: rest,
          mode,
        };
        if (kind === 'reps') {
          payload.repetitions = Math.round(raw);
        } else {
          payload.duration_seconds = Math.round(isLongDuration ? raw * 60 : raw);
        }

        await withBusy(submit, async () => {
          try {
            await api.addSet(payload);
            haptic('success');
            close();
            toast('Подход записан', 'success');
            await refresh();
          } catch (error) {
            haptic('error');
            toast(formatError(error), 'error');
          }
        });
      });
    },
  });
}

export async function render(root, ctx) {
  const day = await api.fitness();
  let mode = day.mode === 'minimum' ? 'minimum' : 'full';
  let progressionKey = 'pushups';

  function currentExercises() {
    return day.modes?.[mode] || day.modes?.full || [];
  }

  function drawProgression() {
    destroyCharts();
    const wrap = root.querySelector('#progression-wrap');
    if (!wrap) return;
    const legend = root.querySelector('[data-progression-legend]');
    const tab = PROGRESSION_TABS.find((item) => item.key === progressionKey) || PROGRESSION_TABS[0];
    const series = day.progression?.[progressionKey] || [];
    const hasData = series.some((point) => point.value !== null && point.value !== undefined);
    if (!hasData) {
      wrap.innerHTML = emptyState({
        iconName: tab.key === 'plank' ? 'timer' : 'trend',
        title: 'Данных пока нет',
        text: 'Запишите подходы — график появится автоматически.',
      });
      if (legend) legend.hidden = true;
      return;
    }
    if (legend) legend.hidden = false;
    wrap.innerHTML = '<canvas id="progression-chart" aria-label="График прогрессии" role="img"></canvas>';
    const canvas = wrap.querySelector('canvas');
    lineChart(canvas, {
      labels: series.map((point) => point.label),
      values: series.map((point) => point.value),
      tone: tab.tone,
      ySuffix: tab.unit,
      formatValue: (value) =>
        tab.key === 'plank' ? formatSeconds(value) : `${value} повт.`,
      formatY: (value) => (tab.key === 'plank' ? `${Math.round(value)}с` : value),
    });
  }

  function paint() {
    destroyCharts();
    const exercises = currentExercises();
    const targetSets = exercises.reduce((sum, item) => sum + (Number(item.sets) || 0), 0);
    const doneSets = exercises.reduce((sum, item) => sum + (Number(item.done_sets) || 0), 0);
    const progress = targetSets ? Math.min(100, (doneSets / targetSets) * 100) : 0;
    const completed = day.workout?.status === 'completed';
    const workout = day.workout;
    const customSets = Array.isArray(day.custom_sets) ? day.custom_sets : [];

    root.innerHTML = `
      ${screenHead({
        eyebrow: 'Тренировка',
        title: day.plan.title,
        subtitle: day.plan.subtitle,
        actions: `${refreshLink()}${settingsLink()}`,
      })}

      <div class="segmented" role="group" aria-label="Режим тренировки">
        <button class="segmented__btn${mode === 'full' ? ' is-active' : ''}" type="button"
          data-mode="full" aria-pressed="${mode === 'full'}">Полная</button>
        <button class="segmented__btn${mode === 'minimum' ? ' is-active' : ''}" type="button"
          data-mode="minimum" aria-pressed="${mode === 'minimum'}">Минимум</button>
      </div>

      <section class="card card--hero fitness-hero">
        ${ring({
          value: progress,
          number: `${doneSets}/${targetSets}`,
          label: 'подходов',
          tone: completed ? 'success' : 'accent',
          ariaLabel: `Выполнено ${doneSets} из ${targetSets} подходов`,
        })}
        <div>
          <div class="hero__pills">
            ${completed ? pill('Тренировка засчитана', 'success', 'check-circle') : pill(mode === 'minimum' ? 'Минимум' : 'Полный режим', mode === 'minimum' ? 'warning' : 'accent')}
            ${workout?.duration_minutes ? pill(formatMinutesShort(workout.duration_minutes), 'outline', 'clock') : ''}
          </div>
          <h2 class="fitness-hero__title">${completed ? 'Работа сделана' : doneSets ? 'Продолжайте спокойно' : 'Начните с одного подхода'}</h2>
          <p class="fitness-hero__sub">${escapeHtml(day.plan.subtitle)}. ${completed ? 'Отдых — часть плана.' : 'Без работы до отказа.'}</p>
          <div class="fitness-hero__actions">
            ${
              completed
                ? `<button class="btn btn--secondary btn--sm" type="button" data-workout-undo>${icon('refresh', 16)} Снять отметку</button>`
                : `<button class="btn btn--primary btn--sm" type="button" data-workout-complete aria-label="Засчитать тренировку">${icon('check', 16)} Засчитать</button>`
            }
          </div>
        </div>
      </section>

      <section class="card">
        <div class="card__head">
          <div>
            <h2 class="card__title">${icon('calendar', 18)} Неделя</h2>
            <p class="card__sub">Активность важнее идеальной тренировки.</p>
          </div>
          <span class="pill pill--outline">${day.activity_days_30 || 0} ${plural(day.activity_days_30 || 0, ['день', 'дня', 'дней'])} за месяц</span>
        </div>
        <div class="week-strip">${weekHtml(day.week)}</div>
        <div class="week-legend">
          <span class="legend-item"><span class="legend-dot legend-dot--success"></span>засчитано</span>
          <span class="legend-item"><span class="legend-dot legend-dot--warning"></span>частично</span>
          <span class="legend-item"><span class="legend-dot legend-dot--muted"></span>план</span>
        </div>
      </section>

      <div class="fitness-layout">
        <div class="col">
          <section class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title">${icon('dumbbell', 18)} Упражнения</h2>
                <p class="card__sub">${mode === 'minimum' ? 'Минимальный объём, чтобы сохранить ритм.' : 'Комфортный объём, без работы до отказа.'}</p>
              </div>
              <span class="pill pill--accent">${doneSets} / ${targetSets}</span>
            </div>
            <div class="exercise-list">
              ${exercises.map((item, index) => exerciseHtml(item, index === 0 && completed)).join('')}
            </div>
            ${
              customSets.length
                ? `
                <div class="divider"></div>
                <p class="field__label">Своя активность</p>
                <div class="set-row">
                  ${customSets
                    .map(
                      (item) => `
                      <button class="set-chip" type="button" data-delete-set="${item.id}"
                        aria-label="Удалить подход ${escapeHtml(item.exercise_name)}">
                        ${escapeHtml(item.exercise_name)} · ${escapeHtml(setLabel(item, item.repetitions ? 'reps' : 'duration'))}
                        ${icon('x', 13)}
                      </button>
                    `,
                    )
                    .join('')}
                </div>
              `
                : ''
            }
          </section>

          <section class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title">${icon('trend', 18)} Прогрессия</h2>
                <p class="card__sub">30 дней. Смотрите на тренд, а не на каждый день.</p>
              </div>
            </div>
            <div class="chart-tabs" role="group" aria-label="Упражнение для графика">
              ${PROGRESSION_TABS.map(
                (tab) => `
                <button class="chart-tab${progressionKey === tab.key ? ' is-active' : ''}" type="button"
                  data-progression="${tab.key}" aria-pressed="${progressionKey === tab.key}">${tab.label}</button>
              `,
              ).join('')}
            </div>
            <div class="chart-wrap chart-wrap--short" id="progression-wrap">
              <canvas id="progression-chart" aria-label="График прогрессии" role="img"></canvas>
            </div>
            <div class="chart-legend" data-progression-legend>
              <span class="legend-item"><span class="legend-dot legend-dot--accent"></span>лучший результат дня</span>
            </div>
          </section>

          <section class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title">${icon('clock', 18)} История</h2>
                <p class="card__sub">Последние тренировки и активные дни.</p>
              </div>
              <span class="pill pill--outline">${day.total_workouts || 0} ${plural(day.total_workouts || 0, ['тренировка', 'тренировки', 'тренировок'])}</span>
            </div>
            <div class="history-list">${historyHtml(day.history)}</div>
          </section>
        </div>

        <div class="col">
          <section>
            <div class="section-head">
              <div>
                <h2 class="section-title">Личные рекорды</h2>
                <p class="section-sub">Не для сравнения — для ориентира.</p>
              </div>
            </div>
            <div class="record-grid">${recordsHtml(day.records)}</div>
          </section>

          <section class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title">${icon('info', 18)} Как это работает</h2>
                <p class="card__sub">Тренировка засчитывается, даже если сделан минимум.</p>
              </div>
            </div>
            <div class="stack">
              <p class="small muted">Каждый подход записывается отдельно. Полный режим — комфортный объём, минимум — один подход на упражнение.</p>
              <p class="small muted">Восстановительные дни считаются активностью: прогулка, мобилити и растяжка.</p>
              <p class="small muted">Если сегодня тяжело, выберите «Минимум» и засчитайте тренировку. Ритм важнее объёма.</p>
            </div>
          </section>
        </div>
      </div>
    `;

    bind();
    drawProgression();

  }

  function bind() {
    root.querySelector('[data-refresh]')?.addEventListener('click', () => ctx.refresh());

    root.querySelectorAll('[data-mode]').forEach((button) => {
      button.addEventListener('click', () => {
        if (button.dataset.mode === mode) return;
        mode = button.dataset.mode;
        haptic('light');
        paint();
      });
    });

    root.querySelectorAll('[data-add-set]').forEach((button) => {
      button.addEventListener('click', () => {
        const exercise = currentExercises().find((item) => item.key === button.dataset.addSet);
        if (!exercise) return;
        openSetSheet({ day, exercise, mode, ctx, refresh: ctx.refresh });
      });
    });

    root.querySelectorAll('[data-delete-set]').forEach((button) => {
      button.addEventListener('click', () => {
        const setId = Number(button.dataset.deleteSet);
        confirmSheet({
          title: 'Удалить подход?',
          message: 'Запись подхода будет удалена, прогресс пересчитается.',
          confirmLabel: 'Удалить',
          onConfirm: async () => {
            await api.deleteSet(setId, day.date);
            toast('Подход удалён', 'success');
            await ctx.refresh();
          },
        });
      });
    });

    root.querySelectorAll('[data-progression]').forEach((button) => {
      button.addEventListener('click', () => {
        if (button.dataset.progression === progressionKey) return;
        progressionKey = button.dataset.progression;
        root.querySelectorAll('[data-progression]').forEach((item) => {
          const active = item.dataset.progression === progressionKey;
          item.classList.toggle('is-active', active);
          item.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        drawProgression();
      });
    });

    root.querySelector('[data-workout-complete]')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      await withBusy(button, async () => {
        try {
          await api.completeWorkout({ date: day.date, mode, completed: true });
          haptic('success');
          toast('Тренировка засчитана', 'success');
          await ctx.refresh();
        } catch (error) {
          haptic('error');
          toast(formatError(error), 'error');
        }
      });
    });

    root.querySelector('[data-workout-undo]')?.addEventListener('click', () => {
      confirmSheet({
        title: 'Снять отметку?',
        message: 'Тренировка вернётся в статус «в работе». Подходы останутся.',
        confirmLabel: 'Снять',
        tone: 'primary',
        onConfirm: async () => {
          await api.completeWorkout({ date: day.date, mode, completed: false });
          toast('Отметка снята', 'success');
          await ctx.refresh();
        },
      });
    });
  }

  paint();

  return () => destroyCharts();
}
