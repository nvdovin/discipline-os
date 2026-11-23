import { api } from '../api.js';
import { icon, HABIT_ICONS } from '../icons.js';
import {
  escapeHtml,
  formatDelta,
  formatMinutes,
  formatNumber,
  formatSeconds,
  plural,
} from '../format.js';
import {
  emptyState,
  formatError,
  pill,
  progressBar,
  refreshLink,
  ring,
  screenHead,
  settingsLink,
  toast,
} from '../ui.js';
import { barChart, destroyCharts, lineChart } from '../charts.js';

const HABIT_TONES = {
  sleep: 'info',
  exercise: 'accent',
  nutrition: 'warning',
  bible: 'violet',
  priority: 'success',
};

const RECORD_ITEMS = [
  { key: 'pushups', label: 'отжиманий', icon: 'trend' },
  { key: 'pullups_day', label: 'подтягиваний за день', icon: 'trend' },
  { key: 'plank_seconds', label: 'планка, рекорд', icon: 'timer' },
];

function deltaPill(delta) {
  if (!delta) return pill('как в прошлый период', 'outline');
  const tone = delta > 0 ? 'success' : 'danger';
  return pill(`${formatDelta(delta, '%')} к прошлому`, tone);
}

function habitStatHtml(item) {
  const tone = HABIT_TONES[item.key] || 'accent';
  const streak = item.streak || { current: 0, best: 0 };
  return `
    <div class="habit-stat tone-${tone}">
      <span class="habit-stat__icon">${icon(HABIT_ICONS[item.key] || 'target', 17)}</span>
      <div class="habit-stat__body">
        <div class="habit-stat__top">
          <span class="habit-stat__name">${escapeHtml(item.name)}</span>
          <span class="habit-stat__pct">${item.pct}%</span>
        </div>
        ${progressBar(item.pct, tone, { thin: true })}
        <p class="habit-stat__meta">
          ${item.completed_days} из ${item.days} ${plural(item.days, ['дня', 'дней', 'дней'])}
          · серия ${streak.current} ${plural(streak.current, ['день', 'дня', 'дней'])}
        </p>
      </div>
    </div>
  `;
}

function milestoneHtml(item) {
  const percent = Math.round((Number(item.progress) || 0) * 100);
  return `
    <div class="milestone${item.earned ? ' milestone--earned' : ''}">
      <div class="milestone__head">
        <span class="milestone__icon">${icon(item.earned ? 'trophy' : item.icon || 'medal', 18)}</span>
        <div>
          <div class="milestone__title">${escapeHtml(item.title)}</div>
          <div class="milestone__desc">${escapeHtml(item.description)}</div>
        </div>
      </div>
      <div class="milestone__progress">${progressBar(percent, item.earned ? 'success' : 'accent', { thin: true })}</div>
      <div class="milestone__meta">
        <span>${item.earned ? 'Получено' : `${formatNumber(item.value)} / ${formatNumber(item.target)} ${escapeHtml(item.unit)}`}</span>
        <span>${percent}%</span>
      </div>
    </div>
  `;
}

function recordsHtml(records) {
  return RECORD_ITEMS.map((item) => {
    const raw = records?.[item.key];
    let value = '—';
    if (raw) {
      value = item.key === 'plank_seconds' ? formatSeconds(raw) : formatNumber(raw);
    }
    return `
      <div class="record">
        <strong>${escapeHtml(value)}</strong>
        <span>${escapeHtml(item.label)}</span>
      </div>
    `;
  }).join('');
}

function weightCardHtml(data) {
  const weight = data.weight || { series: [] };
  const waist = data.waist || { series: [] };
  const hasWeight = (weight.series?.length || 0) >= 2;
  const hasWaist = (waist.series?.length || 0) >= 2;
  const hasAny = hasWeight || hasWaist;

  const line = (label, item, unit) => `
    <div class="measure-line">
      <span class="measure-line__label">${label}</span>
      <span>
        <span class="measure-line__value">${item.latest !== null && item.latest !== undefined ? `${formatNumber(item.latest, 1)} ${unit}` : '—'}</span>
        ${
          item.delta !== null && item.delta !== undefined
            ? `<span class="measure-line__delta ${item.delta > 0 ? 'delta-up' : item.delta < 0 ? 'delta-down' : 'delta-flat'}">${formatDelta(item.delta, unit)} за период</span>`
            : ''
        }
      </span>
    </div>
  `;

  return `
    <section class="card">
      <div class="card__head">
        <div>
          <h2 class="card__title">${icon('scale', 18)} Тело</h2>
          <p class="card__sub">Данные для наблюдения, а не оценка.</p>
        </div>
      </div>
      ${line('Вес', weight, 'кг')}
      ${line('Талия', waist, 'см')}
      ${
        hasAny
          ? `
            <div class="chart-tabs" role="group" aria-label="Что показать на графике">
              <button class="chart-tab${hasWeight ? ' is-active' : ''}" type="button" data-body="weight"
                aria-pressed="${hasWeight ? 'true' : 'false'}"${hasWeight ? '' : ' disabled'}>Вес</button>
              <button class="chart-tab${!hasWeight && hasWaist ? ' is-active' : ''}" type="button" data-body="waist"
                aria-pressed="${!hasWeight && hasWaist ? 'true' : 'false'}"${hasWaist ? '' : ' disabled'}>Талия</button>
            </div>
            <div class="chart-wrap chart-wrap--short" id="body-wrap">
              <canvas id="body-chart" aria-label="График веса" role="img"></canvas>
            </div>
          `
          : `<p class="field__hint mt-3">Добавьте два замера, чтобы увидеть динамику.</p>`
      }
    </section>
  `;
}

export async function render(root, ctx) {
  let period = 'week';
  let data = null;
  let bodyKey = null;

  async function load(nextPeriod) {
    period = nextPeriod;
    data = await api.stats(period);
    paint();
  }

  function paint() {
    destroyCharts();

    const habitStats = data.habit_stats || [];
    const milestones = data.milestones || [];
    const earned = milestones.filter((item) => item.earned).length;
    const hasWeight = (data.weight?.series?.length || 0) >= 2;
    const hasWaist = (data.waist?.series?.length || 0) >= 2;
    bodyKey = bodyKey || (hasWeight ? 'weight' : hasWaist ? 'waist' : null);

    root.innerHTML = `
      ${screenHead({
        eyebrow: 'Аналитика',
        title: 'Статистика',
        subtitle: data.range.label,
        actions: `${refreshLink()}${settingsLink()}`,
      })}

      <div class="segmented" role="group" aria-label="Период статистики">
        <button class="segmented__btn${period === 'week' ? ' is-active' : ''}" type="button"
          data-period="week" aria-pressed="${period === 'week'}">Неделя</button>
        <button class="segmented__btn${period === 'month' ? ' is-active' : ''}" type="button"
          data-period="month" aria-pressed="${period === 'month'}">Месяц</button>
      </div>

      <section class="card card--hero hero">
        ${ring({
          value: data.completion,
          number: `${data.completion}%`,
          label: 'средний результат',
          tone: data.completion >= data.streak.threshold ? 'success' : 'accent',
          ariaLabel: `Средний результат ${data.completion} процентов`,
        })}
        <div class="hero__body">
          <div class="hero__pills">
            ${pill(`${data.success_days} ${plural(data.success_days, ['успешный день', 'успешных дня', 'успешных дней'])}`, data.success_days ? 'success' : 'outline', 'check-circle')}
            ${deltaPill(data.completion_delta)}
          </div>
          <h2 class="hero__title">${data.completion >= 80 ? 'Ритм стал системой' : data.completion >= data.streak.threshold ? 'Ритм держится' : 'Основа уже есть'}</h2>
          <p class="hero__sub">Порог успешного дня — ${data.streak.threshold}%. Считаются только ваши данные, без оценок и сравнений.</p>
          <div class="hero__stats">
            <div class="hero__stat">
              <strong>${data.success_days}/${data.days}</strong>
              <span>успешных</span>
            </div>
            <div class="hero__stat">
              <strong>${data.perfect_days}</strong>
              <span>идеальных</span>
            </div>
            <div class="hero__stat">
              <strong>${data.streak.current}</strong>
              <span>дней подряд</span>
            </div>
          </div>
        </div>
      </section>

      <div class="stat-tiles">
        <div class="stat-tile">
          <div class="stat-tile__label">Тренировки</div>
          <div class="stat-tile__value">${data.exercise_days}</div>
          <div class="stat-tile__hint">${plural(data.exercise_days, ['активный день', 'активных дня', 'активных дней'])} из ${data.days}</div>
        </div>
        <div class="stat-tile">
          <div class="stat-tile__label">Средний сон</div>
          <div class="stat-tile__value">${escapeHtml(data.avg_sleep_label)}</div>
          <div class="stat-tile__hint">${data.sleep_logged_days} ${plural(data.sleep_logged_days, ['ночь', 'ночи', 'ночей'])} с записью</div>
        </div>
        <div class="stat-tile">
          <div class="stat-tile__label">Библия</div>
          <div class="stat-tile__value">${formatNumber(data.bible_minutes)}</div>
          <div class="stat-tile__hint">минут за период</div>
        </div>
        <div class="stat-tile">
          <div class="stat-tile__label">Питание</div>
          <div class="stat-tile__value">${data.nutrition_pct}%</div>
          <div class="stat-tile__hint">${data.nutrition_days} ${plural(data.nutrition_days, ['день', 'дня', 'дней'])} с двумя приёмами</div>
        </div>
      </div>

      <div class="stats-layout">
        <div class="col">
          <section class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title">${icon('chart', 18)} Дисциплина</h2>
                <p class="card__sub">Средний результат по дням. Пунктир — порог ${data.streak.threshold}%.</p>
              </div>
              <span class="pill ${data.completion >= data.streak.threshold ? 'pill--success' : 'pill--outline'}">${data.completion}%</span>
            </div>
            <div class="chart-wrap" id="completion-wrap">
              <canvas id="completion-chart" aria-label="График дисциплины по дням" role="img"></canvas>
            </div>
            <div class="chart-legend">
              <span class="legend-item"><span class="legend-dot legend-dot--accent"></span>день ниже порога</span>
              <span class="legend-item"><span class="legend-dot legend-dot--success"></span>день выше порога</span>
              <span class="legend-item"><span class="legend-dot legend-dot--warning"></span>порог</span>
            </div>
          </section>

          <section class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title">${icon('check-circle', 18)} Привычки</h2>
                <p class="card__sub">Сколько дней закрыта каждая привычка.</p>
              </div>
            </div>
            ${
              habitStats.length
                ? `<div>${habitStats.map(habitStatHtml).join('')}</div>`
                : emptyState({
                    iconName: 'check-circle',
                    title: 'Нет данных за период',
                    text: 'Отметьте привычки на главном экране.',
                  })
            }
          </section>

          <section class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title">${icon('moon', 18)} Сон</h2>
                <p class="card__sub">Продолжительность по дням. Пунктир — цель.</p>
              </div>
              <span class="pill pill--outline">${escapeHtml(data.avg_sleep_label)}</span>
            </div>
            <div class="chart-wrap" id="sleep-wrap">
              <canvas id="sleep-chart" aria-label="График сна за период" role="img"></canvas>
            </div>
            <div class="chart-legend">
              <span class="legend-item"><span class="legend-dot legend-dot--info"></span>сон</span>
              <span class="legend-item"><span class="legend-dot legend-dot--success"></span>цель достигнута</span>
              <span class="legend-item"><span class="legend-dot legend-dot--warning"></span>цель</span>
            </div>
          </section>

          ${weightCardHtml(data)}
        </div>

        <div class="col">
          <section class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title">${icon('trophy', 18)} Достижения</h2>
                <p class="card__sub">${earned} из ${milestones.length} получено. Без гонки.</p>
              </div>
            </div>
            ${
              milestones.length
                ? `<div class="milestones">${milestones.map(milestoneHtml).join('')}</div>`
                : emptyState({
                    iconName: 'trophy',
                    title: 'Достижения появятся позже',
                    text: 'Они растут из обычных дней, а не из рывков.',
                  })
            }
          </section>

          <section>
            <div class="section-head">
              <div>
                <h2 class="section-title">Личные рекорды</h2>
                <p class="section-sub">Ваши лучшие результаты, не сравнение.</p>
              </div>
            </div>
            <div class="record-grid">${recordsHtml(data.records)}</div>
          </section>

          <section class="card">
            <div class="card__head">
              <div>
                <h2 class="card__title">${icon('info', 18)} Всего за всё время</h2>
              </div>
            </div>
            <div class="about-list">
              <div class="about-row"><span>Тренировок</span><strong>${data.total_workouts}</strong></div>
              <div class="about-row"><span>Минут Библии</span><strong>${formatNumber(data.total_bible_minutes)}</strong></div>
              <div class="about-row"><span>Лучшая серия</span><strong>${data.streak.best} ${plural(data.streak.best, ['день', 'дня', 'дней'])}</strong></div>
            </div>
          </section>
        </div>
      </div>
    `;

    bind();
    drawCharts();
  }

  function drawCharts() {
    const completionCanvas = root.querySelector('#completion-chart');
    if (completionCanvas) {
      barChart(completionCanvas, {
        labels: (data.daily || []).map((item) => item.label),
        values: (data.daily || []).map((item) => item.completion),
        target: data.streak.threshold,
        tone: 'accent',
        yMax: 100,
        ySuffix: '%',
        formatValue: (value) => `${Math.round(value)}%`,
        formatY: (value) => `${Math.round(value)}%`,
      });
    }

    const sleepWrap = root.querySelector('#sleep-wrap');
    const hasSleep = (data.sleep_series || []).some((item) => item.value !== null);
    if (sleepWrap) {
      if (!hasSleep) {
        sleepWrap.innerHTML = emptyState({
          iconName: 'moon',
          title: 'Нет записей сна',
          text: 'Добавьте ночь — график появится автоматически.',
        });
      } else {
        const target =
          (data.sleep_series || []).find((item) => item.target)?.target || null;
        barChart(root.querySelector('#sleep-chart'), {
          labels: (data.sleep_series || []).map((item) => item.label),
          values: (data.sleep_series || []).map((item) => item.value),
          target,
          tone: 'info',
          ySuffix: 'мин',
          formatValue: (value) => formatMinutes(value),
          formatY: (value) => `${Math.round(value / 60)}ч`,
        });
      }
    }

    drawBody();
  }

  function drawBody() {
    const wrap = root.querySelector('#body-wrap');
    if (!wrap) return;
    const weight = data.weight?.series || [];
    const waist = data.waist?.series || [];
    const useWeight = bodyKey !== 'waist';
    const series = useWeight ? weight : waist;
    if (series.length < 2) {
      wrap.innerHTML = emptyState({
        iconName: 'scale',
        title: 'Мало данных',
        text: 'Нужно хотя бы два замера.',
      });
      return;
    }
    wrap.innerHTML = `<canvas id="body-chart" aria-label="${useWeight ? 'График веса' : 'График обхвата талии'}" role="img"></canvas>`;
    lineChart(wrap.querySelector('canvas'), {
      labels: series.map((item) => item.label),
      values: series.map((item) => item.value),
      tone: 'info',
      ySuffix: useWeight ? 'кг' : 'см',
      formatValue: (value) => `${formatNumber(value, 1)} ${useWeight ? 'кг' : 'см'}`,
      formatY: (value) => formatNumber(value, 1),
      fill: false,
      beginAtZero: false,
    });
  }

  function bind() {
    root.querySelector('[data-refresh]')?.addEventListener('click', () => ctx.refresh());

    root.querySelectorAll('[data-period]').forEach((button) => {
      button.addEventListener('click', async () => {
        const next = button.dataset.period;
        if (next === period) return;
        root.querySelectorAll('[data-period]').forEach((item) => {
          const active = item.dataset.period === next;
          item.classList.toggle('is-active', active);
          item.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        try {
          await load(next);
        } catch (error) {
          // The router shows a full error screen only on first load; here a
          // toast keeps the current period visible.
          toast(formatError(error), 'error');
        }
      });
    });

    root.querySelectorAll('[data-body]').forEach((button) => {
      button.addEventListener('click', () => {
        if (button.disabled || button.dataset.body === bodyKey) return;
        bodyKey = button.dataset.body;
        root.querySelectorAll('[data-body]').forEach((item) => {
          const active = item.dataset.body === bodyKey;
          item.classList.toggle('is-active', active);
          item.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
        destroyCharts();
        drawCharts();
      });
    });
  }

  await load(period);

  ctx.setFab(null);

  return () => destroyCharts();
}
