import { api } from '../api.js';
import { icon } from '../icons.js';
import {
  escapeHtml,
  formatMinutes,
  formatMinutesShort,
  humanDate,
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
import { barChart, destroyCharts } from '../charts.js';

function durationBetween(bedtime, wake) {
  if (!bedtime || !wake) return null;
  const [bedHour, bedMinute] = bedtime.split(':').map(Number);
  const [wakeHour, wakeMinute] = wake.split(':').map(Number);
  let minutes = wakeHour * 60 + wakeMinute - (bedHour * 60 + bedMinute);
  if (minutes <= 0) minutes += 24 * 60;
  return minutes;
}

function clockDuration(minutes) {
  if (minutes === null || minutes === undefined) return '—';
  const hours = Math.floor(minutes / 60);
  const rest = Math.round(minutes % 60);
  return `${hours}:${String(rest).padStart(2, '0')}`;
}

function sleepHistoryRow(item) {
  return `
    <div class="history-row">
      <div class="history-row__date">
        <strong>${escapeHtml(shortDate(item.date))}</strong>
        ${escapeHtml(item.weekday_short)}
      </div>
      <div class="history-row__main">
        <div class="history-row__title">${escapeHtml(item.bedtime)} → ${escapeHtml(item.wake_up_time)}</div>
        <div class="history-row__meta">${escapeHtml(item.duration_label)}${item.on_schedule ? ' · по графику' : ''}</div>
      </div>
      ${item.on_schedule ? pill('Ритм', 'success') : pill('Свободно', 'outline')}
      <button class="icon-btn history-row__action" type="button" data-history-edit="${escapeHtml(item.date)}"
        aria-label="Изменить сон за ${escapeHtml(shortDate(item.date))}">${icon('edit', 17)}</button>
    </div>
  `;
}

function openSleepSheet({ day, ctx, entry = null }) {
  const target = day.target;
  const date = entry?.date || day.date;
  const isToday = date === day.date;
  const bedtime = entry?.bedtime || target.bedtime;
  const wake = entry?.wake_up_time || target.wake_up_time;
  const notes = entry?.notes || '';
  const initialDuration = durationBetween(bedtime, wake);

  openSheet({
    title: entry ? 'Изменить сон' : 'Записать сон',
    subtitle: isToday
      ? 'Дата пробуждения — сегодня. Время можно поправить.'
      : `Запись за ${humanDate(date, { weekday: false })}.`,
    content: `
      <form class="form" id="sleep-form" novalidate>
        <div class="field-row">
          <div class="field">
            <label class="field__label" for="sleep-bedtime">Отбой</label>
            <input class="input" id="sleep-bedtime" type="time" name="bedtime" value="${escapeHtml(bedtime)}">
          </div>
          <div class="field">
            <label class="field__label" for="sleep-wake">Подъём</label>
            <input class="input" id="sleep-wake" type="time" name="wake" value="${escapeHtml(wake)}">
          </div>
        </div>
        <div class="field">
          <div class="row row--between">
            <span class="field__label">Продолжительность</span>
            <span class="pill pill--info" id="sleep-duration">${escapeHtml(formatMinutes(initialDuration))}</span>
          </div>
          <p class="field__hint" id="sleep-hint">Цель — ${escapeHtml(target.duration_label)}. Допустимый диапазон: 2–15 часов.</p>
        </div>
        <div class="field">
          <label class="field__label" for="sleep-notes">Заметка</label>
          <textarea class="textarea" id="sleep-notes" name="notes" maxlength="1000"
            placeholder="Как спалось? Что помогло или помешало?">${escapeHtml(notes)}</textarea>
        </div>
      </form>
    `,
    footer: `
      ${entry ? `<button class="btn btn--danger btn--icon" type="button" data-sleep-delete aria-label="Удалить запись сна">${icon('trash', 18)}</button>` : ''}
      <button class="btn btn--secondary" type="button" data-sheet-cancel>Отмена</button>
      <button class="btn btn--primary" type="submit" form="sleep-form">Сохранить</button>
    `,
    onMount({ body, footer, close }) {
      const bedInput = body.querySelector('#sleep-bedtime');
      const wakeInput = body.querySelector('#sleep-wake');
      const durationPill = body.querySelector('#sleep-duration');
      const hint = body.querySelector('#sleep-hint');
      const update = () => {
        const minutes = durationBetween(bedInput.value, wakeInput.value);
        durationPill.textContent = formatMinutes(minutes);
        if (minutes !== null && (minutes < 120 || minutes > 900)) {
          hint.textContent = 'Проверьте время: сон должен быть от 2 до 15 часов.';
          hint.classList.add('text-danger');
        } else {
          hint.textContent = `Цель — ${target.duration_label}. Допустимый диапазон: 2–15 часов.`;
          hint.classList.remove('text-danger');
        }
      };
      bedInput?.addEventListener('input', update);
      wakeInput?.addEventListener('input', update);
      update();

      footer.querySelector('[data-sheet-cancel]')?.addEventListener('click', () => close());
      footer.querySelector('[data-sleep-delete]')?.addEventListener('click', () => {
        close();
        confirmSheet({
          title: 'Удалить запись сна?',
          message: isToday ? 'Сон за сегодня будет удалён.' : `Сон за ${humanDate(date, { weekday: false })} будет удалён.`,
          confirmLabel: 'Удалить',
          onConfirm: async () => {
            await api.deleteSleep(date);
            toast('Запись сна удалена', 'success');
            await ctx.refresh();
          },
        });
      });

      body.querySelector('#sleep-form')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = footer.querySelector('button[type="submit"]');
        clearFieldErrors(form);
        const bedtimeValue = form.elements.bedtime.value;
        const wakeValue = form.elements.wake.value;
        if (!bedtimeValue) {
          setFieldError(form.elements.bedtime, 'Укажите время отбоя');
          return;
        }
        if (!wakeValue) {
          setFieldError(form.elements.wake, 'Укажите время подъёма');
          return;
        }
        const minutes = durationBetween(bedtimeValue, wakeValue);
        if (minutes < 120 || minutes > 900) {
          setFieldError(form.elements.bedtime, 'Продолжительность сна должна быть от 2 до 15 часов');
          return;
        }
        await withBusy(submit, async () => {
          try {
            await api.saveSleep({
              date,
              bedtime: form.elements.bedtime.value,
              wake_up_time: form.elements.wake.value,
              notes: form.elements.notes.value.trim() || null,
            });
            haptic('success');
            close();
            toast('Сон записан', 'success');
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
  const day = await api.sleep();
  const target = day.target;
  const today = day.today;
  const consistency = day.consistency;
  const consistency30 = day.consistency_30;
  const series = (day.series || []).slice(-14);
  const hasSeries = series.some((item) => item.duration_minutes !== null);
  const durationProgress = today && target.duration_minutes
    ? (today.duration_minutes / target.duration_minutes) * 100
    : 0;

  root.innerHTML = `
    ${screenHead({
      eyebrow: 'Сон',
      title: 'Сон',
      subtitle: `${humanDate(day.date, { weekday: false })} · цель ${target.duration_label}`,
      actions: `${refreshLink()}${settingsLink()}`,
    })}

    <section class="card card--hero sleep-hero">
      ${ring({
        value: durationProgress,
        number: today ? clockDuration(today.duration_minutes) : '—',
        label: today ? `из ${target.duration_label}` : 'нет записи',
        tone: today ? (today.on_schedule ? 'success' : 'info') : 'info',
        ariaLabel: today
          ? `Сон ${today.duration_label}`
          : 'Сон за сегодня ещё не записан',
      })}
      <div>
        <div class="hero__pills">
          ${
            today
              ? today.on_schedule
                ? pill('По графику', 'success', 'check-circle')
                : pill('Вне графика', 'warning')
              : pill('Нет записи', 'outline')
          }
          ${today?.duration_label ? pill(today.duration_label, 'outline', 'clock') : ''}
        </div>
        <h2 class="sleep-hero__title">${
          today
            ? today.on_schedule
              ? 'Сон по графику'
              : 'Сон записан'
            : 'Запишите ночной сон'
        }</h2>
        <p class="sleep-hero__sub">${
          today
            ? `${today.bedtime} → ${today.wake_up_time}. ${today.on_schedule ? 'Ритм держится.' : 'Один день — просто данные.'}`
            : `Ориентир: ${target.bedtime} → ${target.wake_up_time}. Без чувства вины за отклонения.`
        }</p>
        <div class="sleep-hero__times">
          ${icon('moon', 16)} ${today ? `${today.bedtime} → ${today.wake_up_time}` : `${target.bedtime} → ${target.wake_up_time}`}
        </div>
        <div class="fitness-hero__actions">
          <button class="btn btn--primary btn--sm" type="button" data-sleep-edit>
            ${icon(today ? 'edit' : 'plus', 16)} ${today ? 'Изменить сон' : 'Записать сон'}
          </button>
        </div>
      </div>
    </section>

    <div class="stat-strip">
      <div class="stat-box">
        <div class="stat-box__label">Средний сон</div>
        <div class="stat-box__value">${escapeHtml(consistency.avg_duration_label)}</div>
        <div class="stat-box__hint">за 7 дней</div>
      </div>
      <div class="stat-box">
        <div class="stat-box__label">Средний отбой</div>
        <div class="stat-box__value">${escapeHtml(consistency.avg_bedtime || '—')}</div>
        <div class="stat-box__hint">за 7 дней</div>
      </div>
      <div class="stat-box">
        <div class="stat-box__label">Средний подъём</div>
        <div class="stat-box__value">${escapeHtml(consistency.avg_wake_up_time || '—')}</div>
        <div class="stat-box__hint">за 7 дней</div>
      </div>
      <div class="stat-box">
        <div class="stat-box__label">По графику</div>
        <div class="stat-box__value">${consistency.pct}%</div>
        <div class="stat-box__hint">${consistency.on_schedule} из ${consistency.logged} ночей</div>
      </div>
    </div>

    <div class="sleep-layout">
      <div class="col">
        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('chart', 18)} Продолжительность</h2>
              <p class="card__sub">14 дней. Пунктир — цель ${target.duration_label}.</p>
            </div>
            <span class="pill ${consistency.pct >= 70 ? 'pill--success' : 'pill--outline'}">${consistency.pct}% ритма</span>
          </div>
          <div class="chart-wrap" id="sleep-chart-wrap">
            <canvas id="sleep-chart" aria-label="График продолжительности сна" role="img"></canvas>
          </div>
          <div class="chart-legend">
            <span class="legend-item"><span class="legend-dot legend-dot--info"></span>сон</span>
            <span class="legend-item"><span class="legend-dot legend-dot--success"></span>цель достигнута</span>
            <span class="legend-item"><span class="legend-dot legend-dot--warning"></span>цель</span>
          </div>
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('clock', 18)} Стабильность</h2>
              <p class="card__sub">График сна — не экзамен. Важен общий ритм.</p>
            </div>
          </div>
          <div class="stack">
            <div>
              <div class="row row--between">
                <span class="field__label">7 дней</span>
                <span class="pill ${consistency.pct >= 70 ? 'pill--success' : 'pill--outline'}">${consistency.on_schedule} / ${consistency.logged}</span>
              </div>
              ${progressBar(consistency.pct, consistency.pct >= 70 ? 'success' : 'info')}
            </div>
            <div>
              <div class="row row--between">
                <span class="field__label">30 дней</span>
                <span class="pill ${consistency30.pct >= 70 ? 'pill--success' : 'pill--outline'}">${consistency30.on_schedule} / ${consistency30.logged}</span>
              </div>
              ${progressBar(consistency30.pct, consistency30.pct >= 70 ? 'success' : 'info')}
            </div>
            <p class="field__hint">Допуск к графику — ±${target.tolerance_minutes} минут. Средний сон за 30 дней: ${escapeHtml(consistency30.avg_duration_label)}.</p>
          </div>
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('moon', 18)} История</h2>
              <p class="card__sub">Последние 14 записей.</p>
            </div>
          </div>
          ${
            day.history?.length
              ? `<div class="history-list">${day.history.map(sleepHistoryRow).join('')}</div>`
              : emptyState({
                  iconName: 'moon',
                  title: 'Записей пока нет',
                  text: 'Начните с одной ночи — этого достаточно.',
                  action: `<button class="btn btn--secondary btn--sm" type="button" data-sleep-edit>${icon('plus', 16)} Записать сон</button>`,
                })
          }
        </section>
      </div>

      <div class="col">
        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('info', 18)} Как считается</h2>
            </div>
          </div>
          <div class="stack">
            <p class="small muted">Продолжительность — от отбоя до подъёма. Если подъём раньше отбоя, время переходит через полночь.</p>
            <p class="small muted">«По графику» — отбой и подъём в пределах ±${target.tolerance_minutes} минут от цели ${target.bedtime} → ${target.wake_up_time}.</p>
            <p class="small muted">Пропущенная ночь не обнуляет прогресс. Она просто не попадает в средние значения.</p>
          </div>
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('spark', 18)} Мягкий ориентир</h2>
            </div>
          </div>
          <p class="reflection-quote">Сон — не задача, которую нужно «сдать». Это база, к которой можно возвращаться без долгов.</p>
          <button class="btn btn--secondary btn--block mt-3" type="button" data-settings-sleep>
            ${icon('settings', 17)} Настроить график
          </button>
        </section>
      </div>
    </div>
  `;

  root.querySelector('[data-refresh]')?.addEventListener('click', () => ctx.refresh());
  root.querySelectorAll('[data-sleep-edit]').forEach((button) => {
    button.addEventListener('click', () => openSleepSheet({ day, ctx, entry: today }));
  });
  root.querySelectorAll('[data-history-edit]').forEach((button) => {
    button.addEventListener('click', () => {
      const date = button.dataset.historyEdit;
      const entry = day.history.find((item) => item.date === date);
      if (entry) openSleepSheet({ day, ctx, entry });
    });
  });
  root.querySelector('[data-settings-sleep]')?.addEventListener('click', () => ctx.navigate('#/settings'));

  if (!hasSeries) {
    const wrap = root.querySelector('#sleep-chart-wrap');
    if (wrap) {
      wrap.innerHTML = emptyState({
        iconName: 'moon',
        title: 'Графика пока нет',
        text: 'Добавьте первую запись сна — она станет точкой отсчёта.',
      });
    }
  } else {
    barChart(root.querySelector('#sleep-chart'), {
      labels: series.map((item) => item.label),
      values: series.map((item) => item.duration_minutes),
      target: target.duration_minutes,
      tone: 'info',
      ySuffix: 'мин',
      formatValue: (value) => formatMinutes(value),
      formatY: (value) => `${Math.round(value / 60)}ч`,
    });
  }


  return () => destroyCharts();
}
