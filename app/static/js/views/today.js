import { api } from '../api.js';
import { icon, HABIT_ICONS } from '../icons.js';
import {
  escapeHtml,
  formatMinutesShort,
  formatNumber,
  plural,
  uid,
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
import { destroyCharts } from '../charts.js';

const TONES = {
  sleep: 'info',
  exercise: 'accent',
  nutrition: 'warning',
  bible: 'violet',
  priority: 'success',
};

function dayHeadline(day) {
  if (day.completion >= 100) return 'День закрыт полностью';
  if (day.success) return 'Ритм держится';
  if (day.completion > 0) return 'Хорошее начало';
  return 'Один шаг сегодня';
}

function daySubline(day) {
  if (day.completion >= 100) {
    return 'Все привычки закрыты. Отдых — тоже часть дисциплины.';
  }
  if (day.success) {
    return `${day.completed_count} из ${day.habit_count} привычек уже закрыты. Остальное — без спешки.`;
  }
  const next = day.habits.find((habit) => !habit.completed);
  if (next) {
    return `Следующий шаг — ${next.name.toLowerCase()}: ${next.detail}`;
  }
  return 'Отметьте привычки или добавьте данные — прогресс посчитается сам.';
}

function habitRow(habit) {
  const tone = TONES[habit.key] || 'accent';
  const doneClass = habit.completed ? ' habit--done' : '';
  const progress = Math.round((Number(habit.progress) || 0) * 100);
  return `
    <div class="habit tone-${tone}${doneClass}" data-habit-row="${escapeHtml(habit.key)}">
      <button class="habit__body" type="button" data-habit-open="${escapeHtml(habit.key)}">
        <span class="habit__icon">${icon(HABIT_ICONS[habit.key] || 'target', 20)}</span>
        <span class="habit__text">
          <span class="habit__name">${escapeHtml(habit.name)}</span>
          <span class="habit__detail">${escapeHtml(habit.detail || '')}</span>
          <span class="habit__progress">${progressBar(progress, tone, { thin: true })}</span>
        </span>
      </button>
      <button class="habit__toggle" type="button" data-habit-toggle="${escapeHtml(habit.key)}"
        aria-pressed="${habit.completed ? 'true' : 'false'}"
        aria-label="${habit.completed ? 'Снять отметку' : 'Отметить'}: ${escapeHtml(habit.name)}">
        ${icon('check', 20)}
      </button>
    </div>
  `;
}

function priorityHtml(day) {
  const priority = day.priority || {};
  const hasMain = Boolean(priority.main_priority);
  const done = Boolean(priority.priority_completed);
  const tasks = Array.isArray(priority.secondary_tasks) ? priority.secondary_tasks : [];
  const taskLimitReached = tasks.length >= 10;

  const mainHtml = hasMain
    ? `
      <div class="priority-current">
        <button class="priority-check${done ? ' is-done' : ''}" type="button"
          data-priority-toggle aria-pressed="${done ? 'true' : 'false'}"
          aria-label="${done ? 'Снять отметку с главного дела' : 'Отметить главное дело'}">
          ${icon('check', 20)}
        </button>
        <p class="priority-text${done ? ' priority-text--done' : ''}">${escapeHtml(priority.main_priority)}</p>
      </div>
    `
    : `
      <form class="priority-form" data-priority-form>
        <input class="input" type="text" name="priority" maxlength="300"
          placeholder="Например: закончить отчёт" aria-label="Главное дело дня" autocomplete="off">
        <button class="btn btn--primary btn--icon" type="submit" aria-label="Назначить главное дело">
          ${icon('arrow-right', 20)}
        </button>
      </form>
    `;

  const tasksHtml = tasks.length
    ? `
      <div class="task-list">
        ${tasks
          .map(
            (task) => `
            <div class="task${task.done ? ' task--done' : ''}" data-task-row="${escapeHtml(task.id)}">
              <button class="task__check" type="button" data-task-toggle="${escapeHtml(task.id)}"
                aria-pressed="${task.done ? 'true' : 'false'}"
                aria-label="${task.done ? 'Снять отметку' : 'Отметить'} задачу">
                <span class="task__box">${icon('check', 16)}</span>
              </button>
              <span class="task__text">${escapeHtml(task.text)}</span>
              <button class="task__remove" type="button" data-task-remove="${escapeHtml(task.id)}"
                aria-label="Удалить задачу">${icon('x', 16)}</button>
            </div>
          `,
          )
          .join('')}
      </div>
    `
    : '';

  const addHtml = taskLimitReached
    ? '<p class="field__hint mt-2">Достигнут лимит в 10 второстепенных задач.</p>'
    : `
      <form class="task-add" data-task-form>
        <input class="input" type="text" name="task" maxlength="200"
          placeholder="Второстепенная задача" aria-label="Новая второстепенная задача" autocomplete="off">
        <button class="btn btn--secondary btn--icon btn--sm" type="submit" aria-label="Добавить задачу">
          ${icon('plus', 18)}
        </button>
      </form>
    `;

  return `
    <section class="card" id="priority-card">
      <div class="card__head">
        <div>
          <h2 class="card__title">${icon('target', 18)} Главное дело</h2>
          <p class="card__sub">${hasMain ? 'Один приоритет — остальное подождёт.' : 'Назначьте одно дело, которое сделает день.'}</p>
        </div>
        ${hasMain ? `<button class="icon-btn" type="button" data-priority-edit aria-label="Изменить главное дело">${icon('edit', 18)}</button>` : ''}
      </div>
      ${mainHtml}
      ${tasksHtml}
      ${addHtml}
    </section>
  `;
}

function quickHtml(day) {
  const quick = day.quick;
  const items = [
    {
      key: 'sleep',
      icon: 'moon',
      tone: 'info',
      value: quick.sleep_minutes === null || quick.sleep_minutes === undefined
        ? '—'
        : formatMinutesShort(quick.sleep_minutes),
      label: `Сон · цель ${formatMinutesShort(quick.sleep_target_minutes)}`,
      progress: quick.sleep_target_minutes
        ? ((quick.sleep_minutes || 0) / quick.sleep_target_minutes) * 100
        : 0,
    },
    {
      key: 'protein',
      icon: 'apple',
      tone: 'warning',
      value: `${formatNumber(quick.protein_g, 0)} г`,
      label: `Белок · цель ${quick.protein_target_g} г`,
      progress: quick.protein_target_g
        ? (quick.protein_g / quick.protein_target_g) * 100
        : 0,
    },
    {
      key: 'water',
      icon: 'droplet',
      tone: 'info',
      value: `${formatNumber(quick.water_ml / 1000, 1)} л`,
      label: `Вода · цель ${formatNumber(quick.water_target_ml / 1000, 1)} л`,
      progress: quick.water_target_ml
        ? (quick.water_ml / quick.water_target_ml) * 100
        : 0,
    },
    {
      key: 'bible',
      icon: 'book',
      tone: 'violet',
      value: `${quick.bible_minutes} мин`,
      label: `Библия · цель ${quick.bible_target_minutes} мин`,
      progress: quick.bible_target_minutes
        ? (quick.bible_minutes / quick.bible_target_minutes) * 100
        : 0,
    },
  ];

  return items
    .map(
      (item) => `
      <button class="quick tone-${item.tone}" type="button" data-quick="${item.key}"
        aria-label="${escapeHtml(item.label)}: ${escapeHtml(item.value)}">
        <span class="quick__top">
          <span class="quick__icon">${icon(item.icon, 17)}</span>
          <span class="quick__value">${escapeHtml(item.value)}</span>
        </span>
        <span class="quick__label">${escapeHtml(item.label)}</span>
        ${progressBar(item.progress, item.tone)}
      </button>
    `,
    )
    .join('');
}

function weekHtml(week) {
  const daily = Array.isArray(week?.daily) ? week.daily : [];
  const threshold = week?.streak?.threshold || 60;
  return `
    <section class="card">
      <div class="card__head">
        <div>
          <h2 class="card__title">${icon('chart', 18)} Неделя</h2>
          <p class="card__sub">Порог успешного дня — ${threshold}%.</p>
        </div>
        <span class="pill pill--accent">${week?.streak?.current || 0} ${plural(week?.streak?.current || 0, ['день', 'дня', 'дней'])}</span>
      </div>
      <div class="week-bars">
        ${daily
          .map(
            (item) => `
            <div class="week-day${item.success ? ' week-day--success' : ''}${item.date === week?.range?.end ? ' week-day--today' : ''}">
              <div class="week-day__bar" aria-hidden="true">
                <div class="week-day__fill" style="height:${Math.max(4, Number(item.completion) || 0)}%"></div>
              </div>
              <span class="week-day__label">${escapeHtml(item.label)}</span>
              <span class="week-day__value">${Math.round(item.completion)}%</span>
            </div>
          `,
          )
          .join('')}
      </div>
      <div class="week-legend">
        <span class="legend-item"><span class="legend-dot legend-dot--accent"></span>60%+</span>
        <span class="legend-item"><span class="legend-dot legend-dot--muted"></span>ниже порога</span>
      </div>
    </section>
  `;
}

function reflectionHtml(day) {
  const priority = day.priority || {};
  const positive = priority.positive_result;
  const tomorrow = priority.tomorrow_priority;
  return `
    <section class="card">
      <div class="card__head">
        <div>
          <h2 class="card__title">${icon('spark', 18)} Итоги дня</h2>
          <p class="card__sub">Короткая рефлексия без оценки себя.</p>
        </div>
        ${positive ? pill('Записано', 'success') : ''}
      </div>
      ${
        positive
          ? `<p class="reflection-quote">${escapeHtml(positive)}</p>`
          : '<p class="reflection-note">Что получилось? Что было трудно? Что важно завтра?</p>'
      }
      ${
        tomorrow
          ? `<p class="reflection-note"><strong>Завтра:</strong> ${escapeHtml(tomorrow)}</p>`
          : ''
      }
      <button class="btn ${priority.main_priority ? 'btn--primary' : 'btn--secondary'} btn--block mt-3" type="button" data-reflection>
        ${icon('edit', 18)} ${positive ? 'Изменить итоги' : 'Завершить день'}
      </button>
    </section>
  `;
}

function openPrioritySheet(day, ctx) {
  const priority = day.priority || {};
  const tasks = Array.isArray(priority.secondary_tasks) ? priority.secondary_tasks : [];
  const tasksText = tasks.map((task) => task.text).join('\n');

  openSheet({
    title: priority.main_priority ? 'Изменить главное дело' : 'Главное дело',
    subtitle: 'Один приоритет, который важнее остального.',
    content: `
      <form class="form" id="priority-sheet-form">
        <div class="field">
          <label class="field__label" for="priority-main">Главное дело</label>
          <input class="input" id="priority-main" type="text" name="main_priority" maxlength="300"
            value="${escapeHtml(priority.main_priority || '')}"
            placeholder="Например: закончить отчёт" autocomplete="off">
        </div>
        <div class="field">
          <label class="field__label" for="priority-tasks">Второстепенные задачи</label>
          <textarea class="textarea" id="priority-tasks" name="tasks" rows="4"
            placeholder="Каждая задача с новой строки">${escapeHtml(tasksText)}</textarea>
          <p class="field__hint">До 10 задач. Отметить выполнение можно на карточке дня.</p>
        </div>
      </form>
    `,
    footer: `
      <button class="btn btn--secondary" type="button" data-sheet-cancel>Отмена</button>
      <button class="btn btn--primary" type="submit" form="priority-sheet-form">Сохранить</button>
    `,
    onMount({ body, footer, close }) {
      footer.querySelector('[data-sheet-cancel]')?.addEventListener('click', () => close());
      body.querySelector('#priority-sheet-form')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = footer.querySelector('button[type="submit"]');
        const main = form.elements.main_priority.value.trim();
        const lines = form.elements.tasks.value
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean)
          .slice(0, 10);
        const secondaryTasks = lines.map((text, index) => ({
          id: tasks[index]?.id || uid('task'),
          text,
          done: Boolean(tasks[index]?.done),
        }));

        await withBusy(submit, async () => {
          try {
            await api.savePriority({
              date: day.date,
              main_priority: main,
              secondary_tasks: secondaryTasks,
            });
            haptic('success');
            close();
            toast('Главное дело сохранено', 'success');
            await ctx.refresh();
          } catch (error) {
            haptic('error');
            toast(formatError(error), 'error');
          }
        });
      });
    },
  });
}

function openReflectionSheet(day, ctx) {
  const priority = day.priority || {};
  openSheet({
    title: 'Итоги дня',
    subtitle: 'Три вопроса, чтобы закрыть день спокойно.',
    content: `
      <form class="form" id="reflection-form">
        <div class="field">
          <label class="field__label" for="reflection-positive">Что получилось?</label>
          <textarea class="textarea" id="reflection-positive" name="positive_result" maxlength="2000"
            placeholder="Даже маленький результат имеет значение">${escapeHtml(priority.positive_result || '')}</textarea>
        </div>
        <div class="field">
          <label class="field__label" for="reflection-difficulty">Что было трудно?</label>
          <textarea class="textarea" id="reflection-difficulty" name="difficulty" maxlength="2000"
            placeholder="Без самокритики — просто наблюдение">${escapeHtml(priority.difficulty || '')}</textarea>
        </div>
        <div class="field">
          <label class="field__label" for="reflection-tomorrow">Что важно завтра?</label>
          <textarea class="textarea" id="reflection-tomorrow" name="tomorrow_priority" maxlength="300"
            placeholder="Один спокойный шаг на завтра">${escapeHtml(priority.tomorrow_priority || '')}</textarea>
        </div>
      </form>
    `,
    footer: `
      <button class="btn btn--secondary" type="button" data-sheet-cancel>Отмена</button>
      <button class="btn btn--primary" type="submit" form="reflection-form">Сохранить</button>
    `,
    onMount({ body, footer, close }) {
      footer.querySelector('[data-sheet-cancel]')?.addEventListener('click', () => close());
      body.querySelector('#reflection-form')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = footer.querySelector('button[type="submit"]');
        await withBusy(submit, async () => {
          try {
            await api.savePriority({
              date: day.date,
              positive_result: form.elements.positive_result.value,
              difficulty: form.elements.difficulty.value,
              tomorrow_priority: form.elements.tomorrow_priority.value,
            });
            haptic('success');
            close();
            toast('Итоги дня сохранены', 'success');
            await ctx.refresh();
          } catch (error) {
            haptic('error');
            toast(formatError(error), 'error');
          }
        });
      });
    },
  });
}

function openBibleSheet(day, ctx) {
  const bible = day.bible || {};
  const currentMinutes = Number(bible.minutes) || 0;
  openSheet({
    title: currentMinutes ? 'Изменить чтение' : 'Чтение Библии',
    subtitle: 'Сколько минут сегодня читали?',
    content: `
      <form class="form" id="bible-form">
        <div class="field">
          <label class="field__label" for="bible-minutes">Минуты</label>
          <div class="stepper">
            <button class="stepper__btn" type="button" data-bible-minus aria-label="Минус пять минут">${icon('minus', 20)}</button>
            <input class="stepper__input" id="bible-minutes" type="number" name="duration_minutes"
              min="1" max="600" step="1" value="${currentMinutes || bible.target_minutes || 30}"
              inputmode="numeric">
            <button class="stepper__btn" type="button" data-bible-plus aria-label="Плюс пять минут">${icon('plus', 20)}</button>
          </div>
          <p class="field__hint">Цель — ${bible.target_minutes || 30} минут. Любое время уже считается.</p>
        </div>
        <div class="field">
          <label class="field__label" for="bible-notes">Заметка</label>
          <textarea class="textarea" id="bible-notes" name="notes" maxlength="2000"
            placeholder="Мысль, вопрос или стих, который зацепил">${escapeHtml(bible.notes || '')}</textarea>
        </div>
      </form>
    `,
    footer: `
      ${currentMinutes ? `<button class="btn btn--danger btn--icon" type="button" data-bible-delete aria-label="Удалить запись">${icon('trash', 18)}</button>` : ''}
      <button class="btn btn--secondary" type="button" data-sheet-cancel>Отмена</button>
      <button class="btn btn--primary" type="submit" form="bible-form">Сохранить</button>
    `,
    onMount({ body, footer, close }) {
      const input = body.querySelector('#bible-minutes');
      const adjust = (delta) => {
        const next = Math.max(1, Math.min(600, (Number(input.value) || 0) + delta));
        input.value = String(next);
      };
      body.querySelector('[data-bible-minus]')?.addEventListener('click', () => adjust(-5));
      body.querySelector('[data-bible-plus]')?.addEventListener('click', () => adjust(5));
      footer.querySelector('[data-sheet-cancel]')?.addEventListener('click', () => close());
      footer.querySelector('[data-bible-delete]')?.addEventListener('click', () => {
        close();
        confirmSheet({
          title: 'Удалить запись?',
          message: 'Минуты чтения за сегодня будут удалены.',
          confirmLabel: 'Удалить',
          onConfirm: async () => {
            await api.deleteBible(day.date);
            toast('Запись удалена', 'success');
            await ctx.refresh();
          },
        });
      });
      body.querySelector('#bible-form')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = footer.querySelector('button[type="submit"]');
        clearFieldErrors(form);
        const minutes = Number(form.elements.duration_minutes.value);
        if (!Number.isFinite(minutes) || minutes < 1 || minutes > 600) {
          setFieldError(input, 'Укажите от 1 до 600 минут');
          return;
        }
        await withBusy(submit, async () => {
          try {
            await api.saveBible({
              date: day.date,
              duration_minutes: Math.round(minutes),
              notes: form.elements.notes.value.trim() || null,
            });
            haptic('success');
            close();
            toast('Чтение записано', 'success');
            await ctx.refresh();
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
  const [day, week] = await Promise.all([api.dashboard(), api.stats('week')]);

  root.innerHTML = `
    ${screenHead({
      eyebrow: day.greeting,
      title: 'Сегодня',
      subtitle: `${day.human_date} · ${day.weekday}`,
      actions: `${refreshLink()}${settingsLink()}`,
    })}

    <section class="card card--hero hero">
      ${ring({
        value: day.completion,
        number: `${day.completion}%`,
        label: `${day.completed_count} из ${day.habit_count}`,
        tone: day.success ? 'success' : 'accent',
        ariaLabel: `Дисциплина дня ${day.completion} процентов`,
      })}
      <div class="hero__body">
        <div class="hero__pills">
          ${day.success ? pill('День закрыт', 'success', 'check-circle') : pill('Порог 60%', 'outline')}
          ${pill(`${day.streak.current} ${plural(day.streak.current, ['день', 'дня', 'дней'])} подряд`, 'accent', 'flame')}
        </div>
        <h2 class="hero__title">${escapeHtml(dayHeadline(day))}</h2>
        <p class="hero__sub">${escapeHtml(daySubline(day))}</p>
        <div class="hero__stats">
          <div class="hero__stat">
            <strong>${day.completed_count}/${day.habit_count}</strong>
            <span>привычек</span>
          </div>
          <div class="hero__stat">
            <strong>${day.streak.best}</strong>
            <span>лучшая серия</span>
          </div>
          <div class="hero__stat">
            <strong>${day.weight_kg ? formatNumber(day.weight_kg, 1) : '—'}</strong>
            <span>вес, кг</span>
          </div>
        </div>
      </div>
    </section>

    <div class="today-layout">
      <div class="col">
        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('check-circle', 18)} Привычки</h2>
              <p class="card__sub">Отмечайте вручную или добавляйте данные — прогресс посчитается сам.</p>
            </div>
            <span class="pill ${day.success ? 'pill--success' : 'pill--outline'}">${day.completed_count} / ${day.habit_count}</span>
          </div>
          <div class="habit-list">
            ${day.habits.map(habitRow).join('')}
          </div>
        </section>

        ${weekHtml(week)}
      </div>

      <div class="col">
        ${priorityHtml(day)}
        <div class="quick-grid">
          ${quickHtml(day)}
        </div>
        ${reflectionHtml(day)}
      </div>
    </div>
  `;

  const bindHabitToggle = (button) => {
    button.addEventListener('click', async () => {
      const key = button.dataset.habitToggle;
      const habit = day.habits.find((item) => item.key === key);
      if (!habit) return;
      if (key === 'priority' && !day.priority.main_priority) {
        toast('Сначала назначьте главное дело', 'error');
        root.querySelector('[data-priority-form] input')?.focus();
        return;
      }
      await withBusy(button, async () => {
        try {
          await api.toggleHabit(key, { date: day.date, completed: !habit.completed });
          haptic('success');
          toast(habit.completed ? 'Отметка снята' : 'Привычка закрыта', 'success');
          await ctx.refresh();
        } catch (error) {
          haptic('error');
          toast(formatError(error), 'error');
        }
      });
    });
  };

  root.querySelectorAll('[data-habit-toggle]').forEach(bindHabitToggle);

  root.querySelectorAll('[data-habit-open]').forEach((button) => {
    button.addEventListener('click', () => {
      const key = button.dataset.habitOpen;
      if (key === 'bible') {
        openBibleSheet(day, ctx);
        return;
      }
      if (key === 'priority') {
        openPrioritySheet(day, ctx);
        return;
      }
      if (key === 'sleep') {
        ctx.navigate('#/sleep');
        return;
      }
      if (key === 'exercise') {
        ctx.navigate('#/fitness');
        return;
      }
      if (key === 'nutrition') {
        ctx.navigate('#/nutrition');
      }
    });
  });

  root.querySelector('[data-priority-form]')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.priority;
    const value = input.value.trim();
    clearFieldErrors(form);
    if (!value) {
      setFieldError(input, 'Напишите главное дело');
      return;
    }
    const submit = form.querySelector('button[type="submit"]');
    await withBusy(submit, async () => {
      try {
        await api.savePriority({ date: day.date, main_priority: value });
        haptic('success');
        toast('Главное дело назначено', 'success');
        await ctx.refresh();
      } catch (error) {
        haptic('error');
        toast(formatError(error), 'error');
      }
    });
  });

  root.querySelector('[data-priority-toggle]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    await withBusy(button, async () => {
      try {
        await api.savePriority({
          date: day.date,
          priority_completed: !day.priority.priority_completed,
        });
        haptic('success');
        toast(day.priority.priority_completed ? 'Отметка снята' : 'Главное дело выполнено', 'success');
        await ctx.refresh();
      } catch (error) {
        haptic('error');
        toast(formatError(error), 'error');
      }
    });
  });

  root.querySelector('[data-priority-edit]')?.addEventListener('click', () => openPrioritySheet(day, ctx));

  root.querySelectorAll('[data-task-toggle]').forEach((button) => {
    button.addEventListener('click', async () => {
      const taskId = button.dataset.taskToggle;
      const tasks = day.priority.secondary_tasks.map((task) =>
        task.id === taskId
          ? { id: task.id, text: task.text, done: !task.done }
          : { id: task.id, text: task.text, done: task.done },
      );
      await withBusy(button, async () => {
        try {
          await api.savePriority({ date: day.date, secondary_tasks: tasks });
          haptic('light');
          await ctx.refresh();
        } catch (error) {
          haptic('error');
          toast(formatError(error), 'error');
        }
      });
    });
  });

  root.querySelectorAll('[data-task-remove]').forEach((button) => {
    button.addEventListener('click', () => {
      const taskId = button.dataset.taskRemove;
      const task = day.priority.secondary_tasks.find((item) => item.id === taskId);
      if (!task) return;
      confirmSheet({
        title: 'Удалить задачу?',
        message: `«${task.text}»`,
        confirmLabel: 'Удалить',
        onConfirm: async () => {
          const tasks = day.priority.secondary_tasks
            .filter((item) => item.id !== taskId)
            .map((item) => ({ id: item.id, text: item.text, done: item.done }));
          await api.savePriority({ date: day.date, secondary_tasks: tasks });
          toast('Задача удалена', 'success');
          await ctx.refresh();
        },
      });
    });
  });

  root.querySelector('[data-task-form]')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.task;
    const text = input.value.trim();
    clearFieldErrors(form);
    if (!text) {
      setFieldError(input, 'Напишите задачу');
      return;
    }
    if (day.priority.secondary_tasks.length >= 10) {
      toast('Можно добавить не больше 10 задач', 'error');
      return;
    }
    const submit = form.querySelector('button[type="submit"]');
    const tasks = [
      ...day.priority.secondary_tasks.map((item) => ({
        id: item.id,
        text: item.text,
        done: item.done,
      })),
      { id: uid('task'), text, done: false },
    ];
    await withBusy(submit, async () => {
      try {
        await api.savePriority({ date: day.date, secondary_tasks: tasks });
        haptic('success');
        toast('Задача добавлена', 'success');
        await ctx.refresh();
      } catch (error) {
        haptic('error');
        toast(formatError(error), 'error');
      }
    });
  });

  root.querySelectorAll('[data-quick]').forEach((button) => {
    button.addEventListener('click', () => {
      const key = button.dataset.quick;
      if (key === 'bible') {
        openBibleSheet(day, ctx);
        return;
      }
      if (key === 'sleep') {
        ctx.navigate('#/sleep');
        return;
      }
      ctx.navigate('#/nutrition');
    });
  });

  root.querySelector('[data-reflection]')?.addEventListener('click', () => {
    openReflectionSheet(day, ctx);
  });

  root.querySelector('[data-refresh]')?.addEventListener('click', () => ctx.refresh());


  return () => destroyCharts();
}
