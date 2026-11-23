import { api } from '../api.js';
import { icon } from '../icons.js';
import {
  escapeHtml,
  formatDelta,
  formatMinutesShort,
  formatNumber,
  humanDate,
  nowTime,
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
import { barChart, destroyCharts, lineChart } from '../charts.js';

function numberOrNull(value) {
  const text = String(value ?? '').trim().replace(',', '.');
  if (!text) return null;
  const number = Number(text);
  return Number.isFinite(number) ? number : null;
}

function macroValue(value, unit) {
  if (value === null || value === undefined) return '';
  const digits = Number.isInteger(Number(value)) ? 0 : 1;
  return `${formatNumber(value, digits)} ${unit}`;
}

function mealMacros(meal) {
  const values = [];
  if (meal.calories !== null && meal.calories !== undefined) values.push(`${meal.calories} ккал`);
  if (meal.protein_g !== null && meal.protein_g !== undefined) values.push(`${formatNumber(meal.protein_g, 1)} г белка`);
  if (meal.carbs_g !== null && meal.carbs_g !== undefined) values.push(`${formatNumber(meal.carbs_g, 1)} г углеводов`);
  if (meal.fats_g !== null && meal.fats_g !== undefined) values.push(`${formatNumber(meal.fats_g, 1)} г жиров`);
  if (!values.length) values.push('без цифр');
  return values.map((value) => `<span>${escapeHtml(value)}</span>`).join('');
}

function windowLabel(times) {
  if (!times?.length) return null;
  if (times.length === 1) return `${times[0]} · один приём`;
  const [startHour, startMinute] = times[0].split(':').map(Number);
  const [endHour, endMinute] = times[times.length - 1].split(':').map(Number);
  let minutes = endHour * 60 + endMinute - (startHour * 60 + startMinute);
  if (minutes <= 0) minutes += 24 * 60;
  return `${times[0]}–${times[times.length - 1]} · ${formatMinutesShort(minutes)}`;
}

function openMealSheet(day, ctx) {
  openSheet({
    title: 'Новый приём пищи',
    subtitle: 'Опишите еду. Цифры можно не заполнять — приложение не выдумывает значения.',
    content: `
      <form class="form" id="meal-form" novalidate>
        <div class="field">
          <label class="field__label" for="meal-description">Что вы съели?</label>
          <textarea class="textarea" id="meal-description" name="description" maxlength="300"
            placeholder="Например: курица с рисом и овощами"></textarea>
        </div>
        <div class="field">
          <label class="field__label" for="meal-time">Время</label>
          <input class="input" id="meal-time" type="time" name="time" value="${nowTime()}">
        </div>
        <div class="field-row">
          <div class="field">
            <label class="field__label" for="meal-calories">Калории</label>
            <input class="input" id="meal-calories" type="number" name="calories" min="0" max="5000"
              step="1" inputmode="numeric" placeholder="необязательно">
          </div>
          <div class="field">
            <label class="field__label" for="meal-protein">Белок, г</label>
            <input class="input" id="meal-protein" type="text" name="protein" inputmode="decimal"
              autocomplete="off" placeholder="необязательно">
          </div>
        </div>
        <div class="field-row">
          <div class="field">
            <label class="field__label" for="meal-carbs">Углеводы, г</label>
            <input class="input" id="meal-carbs" type="text" name="carbs" inputmode="decimal"
              autocomplete="off" placeholder="необязательно">
          </div>
          <div class="field">
            <label class="field__label" for="meal-fats">Жиры, г</label>
            <input class="input" id="meal-fats" type="text" name="fats" inputmode="decimal"
              autocomplete="off" placeholder="необязательно">
          </div>
        </div>
      </form>
    `,
    footer: `
      <button class="btn btn--secondary" type="button" data-sheet-cancel>Отмена</button>
      <button class="btn btn--primary" type="submit" form="meal-form">Записать</button>
    `,
    onMount({ body, footer, close }) {
      footer.querySelector('[data-sheet-cancel]')?.addEventListener('click', () => close());
      body.querySelector('#meal-form')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = footer.querySelector('button[type="submit"]');
        clearFieldErrors(form);
        const description = form.elements.description.value.trim();
        if (!description) {
          setFieldError(form.elements.description, 'Опишите приём пищи');
          return;
        }
        const fields = [
          ['calories', 'Калории', 0, 5000],
          ['protein', 'Белок', 0, 500],
          ['carbs', 'Углеводы', 0, 500],
          ['fats', 'Жиры', 0, 500],
        ];
        const values = {};
        for (const [name, label, min, max] of fields) {
          const raw = form.elements[name].value.trim();
          const value = numberOrNull(raw);
          if (raw && value === null) {
            setFieldError(form.elements[name], `${label}: введите число`);
            return;
          }
          if (value !== null && (value < min || value > max)) {
            setFieldError(form.elements[name], `${label}: значение от ${min} до ${max}`);
            return;
          }
          values[name] = value;
        }
        const { calories, protein, carbs, fats } = values;

        await withBusy(submit, async () => {
          try {
            await api.addMeal({
              date: day.date,
              time: form.elements.time.value || nowTime(),
              description,
              calories: calories === null ? null : Math.round(calories),
              protein_g: protein,
              carbs_g: carbs,
              fats_g: fats,
            });
            haptic('success');
            close();
            toast('Приём пищи записан', 'success');
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

function openMeasurementSheet(day, ctx) {
  const latest = day.measurements.latest;
  const isToday = latest?.date === day.date;
  openSheet({
    title: 'Замер тела',
    subtitle: 'Один замер в день. Вес и талия — не оценка, а данные.',
    content: `
      <form class="form" id="measure-form" novalidate>
        <div class="field-row">
          <div class="field">
            <label class="field__label" for="measure-weight">Вес, кг</label>
            <input class="input" id="measure-weight" type="text" name="weight" inputmode="decimal"
              autocomplete="off" value="${isToday && latest.weight_kg ? String(latest.weight_kg).replace('.', ',') : ''}"
              placeholder="${latest?.weight_kg ? `последний: ${formatNumber(latest.weight_kg, 1)}` : 'например 78,5'}">
          </div>
          <div class="field">
            <label class="field__label" for="measure-waist">Талия, см</label>
            <input class="input" id="measure-waist" type="text" name="waist" inputmode="decimal"
              autocomplete="off" value="${isToday && latest.waist_cm ? String(latest.waist_cm).replace('.', ',') : ''}"
              placeholder="${latest?.waist_cm ? `последний: ${formatNumber(latest.waist_cm, 1)}` : 'например 86'}">
          </div>
        </div>
        <p class="field__hint">Заполните хотя бы одно поле. Значения не сравниваются с «нормой».</p>
      </form>
    `,
    footer: `
      <button class="btn btn--secondary" type="button" data-sheet-cancel>Отмена</button>
      <button class="btn btn--primary" type="submit" form="measure-form">Сохранить</button>
    `,
    onMount({ body, footer, close }) {
      footer.querySelector('[data-sheet-cancel]')?.addEventListener('click', () => close());
      body.querySelector('#measure-form')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const submit = footer.querySelector('button[type="submit"]');
        clearFieldErrors(form);
        const weightRaw = form.elements.weight.value.trim();
        const waistRaw = form.elements.waist.value.trim();
        const weight = numberOrNull(weightRaw);
        const waist = numberOrNull(waistRaw);
        if (weightRaw && weight === null) {
          setFieldError(form.elements.weight, 'Введите число');
          return;
        }
        if (waistRaw && waist === null) {
          setFieldError(form.elements.waist, 'Введите число');
          return;
        }
        if (weight === null && waist === null) {
          setFieldError(form.elements.weight, 'Укажите вес или обхват талии');
          return;
        }
        if (weight !== null && (weight < 20 || weight > 400)) {
          setFieldError(form.elements.weight, 'Вес должен быть от 20 до 400 кг');
          return;
        }
        if (waist !== null && (waist < 30 || waist > 250)) {
          setFieldError(form.elements.waist, 'Талия должна быть от 30 до 250 см');
          return;
        }
        await withBusy(submit, async () => {
          try {
            await api.saveMeasurement({ date: day.date, weight_kg: weight, waist_cm: waist });
            haptic('success');
            close();
            toast('Замер сохранён', 'success');
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
  const day = await api.nutrition();
  const targets = day.targets;
  const totals = day.totals;
  const meals = day.meals;
  const water = day.water;
  const measurements = day.measurements;
  const mealTimes = targets.meal_times || [];
  const windowText = windowLabel(mealTimes);
  const proteinProgress = targets.protein_g ? (totals.protein_g / targets.protein_g) * 100 : 0;
  const proteinRemaining = Math.max(0, Math.round(targets.protein_g - totals.protein_g));
  const hasCalories = meals.some((meal) => meal.calories !== null && meal.calories !== undefined);
  const hasCarbs = meals.some((meal) => meal.carbs_g !== null && meal.carbs_g !== undefined);
  const hasFats = meals.some((meal) => meal.fats_g !== null && meal.fats_g !== undefined);
  const proteinSeries = day.protein_series || [];
  const weekHasMeals = proteinSeries.some((item) => item.has_meals);

  root.innerHTML = `
    ${screenHead({
      eyebrow: 'Питание',
      title: 'Питание',
      subtitle: `${humanDate(day.date, { weekday: false })} · ${meals.length} из ${targets.meals} приёмов`,
      actions: `${refreshLink()}${settingsLink()}`,
    })}

    <section class="card card--hero nutrition-hero">
      ${ring({
        value: proteinProgress,
        number: `${Math.round(totals.protein_g)} г`,
        label: `из ${targets.protein_g} г белка`,
        tone: proteinProgress >= 100 ? 'success' : 'warning',
        ariaLabel: `Белок ${Math.round(totals.protein_g)} из ${targets.protein_g} граммов`,
      })}
      <div>
        <div class="hero__pills">
          ${proteinProgress >= 100 ? pill('Белок в норме', 'success', 'check-circle') : pill(proteinRemaining ? `ещё ${proteinRemaining} г` : 'цель достигнута', 'warning')}
          ${windowText ? pill(windowText, 'outline', 'clock') : ''}
        </div>
        <h2 class="nutrition-hero__title">${
          proteinProgress >= 100
            ? 'Белок закрыт'
            : totals.protein_g > 0
              ? 'Белок набирается'
              : 'Первый приём — начало'
        }</h2>
        <p class="nutrition-hero__sub">${
          totals.has_missing_values
            ? 'Суммы считаются по заполненным значениям. Пустые поля не додумываются.'
            : 'Спокойно, без жёстких запретов и подсчёта каждой крошки.'
        }</p>
        <div class="macro-grid">
          <div class="macro">
            <strong>${hasCalories ? formatNumber(totals.calories) : '—'}</strong>
            <span><span class="macro__dot tone-accent"></span>ккал</span>
          </div>
          <div class="macro">
            <strong>${hasCarbs ? formatNumber(totals.carbs_g, 1) : '—'}</strong>
            <span><span class="macro__dot tone-warning"></span>углеводы</span>
          </div>
          <div class="macro">
            <strong>${hasFats ? formatNumber(totals.fats_g, 1) : '—'}</strong>
            <span><span class="macro__dot tone-info"></span>жиры</span>
          </div>
        </div>
      </div>
    </section>

    <div class="nutrition-layout">
      <div class="col">
        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('utensils', 18)} Приёмы пищи</h2>
              <p class="card__sub">${mealTimes.length ? `Ориентир: ${mealTimes.join(' и ')}.` : 'Добавьте первый приём.'}</p>
            </div>
            <button class="btn ${meals.length ? 'btn--primary' : 'btn--secondary'} btn--sm" type="button" data-add-meal>${icon('plus', 16)} Добавить</button>
          </div>
          ${
            meals.length
              ? `<div class="meal-list">
                  ${meals
                    .map(
                      (meal) => `
                      <div class="meal">
                        <span class="meal__time">${escapeHtml(meal.time)}</span>
                        <div class="meal__body">
                          <div class="meal__title">${escapeHtml(meal.description)}</div>
                          <div class="meal__macros">${mealMacros(meal)}</div>
                        </div>
                        <button class="meal__delete" type="button" data-meal-delete="${meal.id}"
                          aria-label="Удалить приём пищи">${icon('trash', 17)}</button>
                      </div>
                    `,
                    )
                    .join('')}
                </div>`
              : emptyState({
                  iconName: 'utensils',
                  title: 'Сегодня ещё нет приёмов',
                  text: 'Два спокойных приёма важнее идеального плана.',
                  action: `<button class="btn btn--primary btn--sm" type="button" data-add-meal>${icon('plus', 16)} Записать приём</button>`,
                })
          }
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('droplet', 18)} Вода</h2>
              <p class="card__sub">${water.entries.length ? `${water.entries.length} ${water.entries.length === 1 ? 'запись' : 'записей'} за сегодня` : 'Без давления: просто отмечайте порции.'}</p>
            </div>
            <span class="pill ${water.total_ml >= water.target_ml ? 'pill--success' : 'pill--outline'}">${Math.round((water.total_ml / water.target_ml) * 100)}%</span>
          </div>
          <div class="water-head">
            <div class="water-value">${formatNumber(water.total_ml / 1000, 1)} <small>из ${formatNumber(water.target_ml / 1000, 1)} л</small></div>
          </div>
          ${progressBar(water.target_ml ? (water.total_ml / water.target_ml) * 100 : 0, 'info')}
          <div class="water-actions">
            <button class="btn btn--secondary btn--sm" type="button" data-add-water="250">${icon('plus', 15)} 250 мл</button>
            <button class="btn btn--secondary btn--sm" type="button" data-add-water="500">${icon('plus', 15)} 500 мл</button>
            <button class="btn btn--secondary btn--sm" type="button" data-add-water="750">${icon('plus', 15)} 750 мл</button>
            ${
              water.entries.length
                ? `<button class="btn btn--ghost btn--sm" type="button" data-undo-water>${icon('refresh', 15)} Убрать последнюю</button>`
                : ''
            }
          </div>
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('scale', 18)} Вес и талия</h2>
              <p class="card__sub">${measurements.latest ? `Последний замер: ${humanDate(measurements.latest.date, { weekday: false })}` : 'Первый замер — просто точка отсчёта.'}</p>
            </div>
            <button class="btn btn--secondary btn--sm" type="button" data-measure>${icon('plus', 16)} Замер</button>
          </div>
          <div class="measure-line">
            <span class="measure-line__label">Вес</span>
            <span>
              <span class="measure-line__value">${measurements.latest?.weight_kg ? `${formatNumber(measurements.latest.weight_kg, 1)} кг` : '—'}</span>
              ${
                measurements.weight_delta_30 !== null
                  ? `<span class="measure-line__delta ${measurements.weight_delta_30 > 0 ? 'delta-up' : measurements.weight_delta_30 < 0 ? 'delta-down' : 'delta-flat'}">${formatDelta(measurements.weight_delta_30, 'кг')} за 30 дн.</span>`
                  : ''
              }
            </span>
          </div>
          <div class="measure-line">
            <span class="measure-line__label">Талия</span>
            <span>
              <span class="measure-line__value">${measurements.latest?.waist_cm ? `${formatNumber(measurements.latest.waist_cm, 1)} см` : '—'}</span>
              ${
                measurements.waist_delta_30 !== null
                  ? `<span class="measure-line__delta ${measurements.waist_delta_30 > 0 ? 'delta-up' : measurements.waist_delta_30 < 0 ? 'delta-down' : 'delta-flat'}">${formatDelta(measurements.waist_delta_30, 'см')} за 30 дн.</span>`
                  : ''
              }
            </span>
          </div>
          ${
            measurements.weight_series.length >= 2 || measurements.waist_series.length >= 2
              ? `<div class="chart-wrap chart-wrap--short" id="weight-wrap"><canvas id="weight-chart" aria-label="График веса" role="img"></canvas></div>`
              : `<p class="field__hint mt-3">Добавьте два замера, чтобы увидеть динамику.</p>`
          }
        </section>
      </div>

      <div class="col">
        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('trend', 18)} Белок за неделю</h2>
              <p class="card__sub">Дни с заполненным белком. Цель — ${targets.protein_g} г.</p>
            </div>
            <span class="pill ${proteinSeries.filter((item) => item.protein_g > 0).length >= 5 ? 'pill--success' : 'pill--outline'}">${proteinSeries.filter((item) => item.protein_g > 0).length}/7</span>
          </div>
          <div class="chart-wrap chart-wrap--short" id="protein-wrap">
            <canvas id="protein-chart" aria-label="График белка за неделю" role="img"></canvas>
          </div>
          <div class="chart-legend">
            <span class="legend-item"><span class="legend-dot legend-dot--warning"></span>белок</span>
            <span class="legend-item"><span class="legend-dot legend-dot--success"></span>цель достигнута</span>
          </div>
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('clock', 18)} Пищевое окно</h2>
              <p class="card__sub">Мягкий ориентир, а не запрет.</p>
            </div>
          </div>
          ${
            windowText
              ? `
                <div class="eating-window">
                  <div>
                    <div class="eating-window__value">${escapeHtml(windowText)}</div>
                    <div class="eating-window__label">${mealTimes.length} приёма пищи</div>
                  </div>
                  ${pill('без запретов', 'outline')}
                </div>
                <p class="field__hint mt-3">Если пропустили окно — это не ошибка. Вернитесь к ритму со следующим приёмом.</p>
              `
              : emptyState({
                  iconName: 'clock',
                  title: 'Окно не настроено',
                  text: 'Укажите время приёмов в настройках.',
                  action: '<a class="btn btn--secondary btn--sm" href="#/settings">Открыть настройки</a>',
                })
          }
        </section>

        <section class="card">
          <div class="card__head">
            <div>
              <h2 class="card__title">${icon('info', 18)} Без подсчёта всего</h2>
            </div>
          </div>
          <div class="stack">
            <p class="small muted">Белок и вода — основные ориентиры. Калории и БЖУ можно не заполнять, если это утомляет.</p>
            <p class="small muted">Приложение показывает только введённые вами значения. Оно не оценивает еду как «хорошую» или «плохую».</p>
            <p class="small muted">Вес и талия — данные для наблюдения, а не приговор. Тренд важнее одного дня.</p>
          </div>
        </section>
      </div>
    </div>
  `;

  function bind() {
    root.querySelector('[data-refresh]')?.addEventListener('click', () => ctx.refresh());

    root.querySelectorAll('[data-add-meal]').forEach((button) => {
      button.addEventListener('click', () => openMealSheet(day, ctx));
    });

    root.querySelectorAll('[data-add-water]').forEach((button) => {
      button.addEventListener('click', async () => {
        const amount = Number(button.dataset.addWater);
        await withBusy(button, async () => {
          try {
            await api.addWater({ date: day.date, amount_ml: amount });
            haptic('success');
            toast(`+${amount} мл воды`, 'success');
            await ctx.refresh();
          } catch (error) {
            haptic('error');
            toast(formatError(error), 'error');
          }
        });
      });
    });

    root.querySelector('[data-undo-water]')?.addEventListener('click', async (event) => {
      const last = water.entries[water.entries.length - 1];
      if (!last) return;
      const button = event.currentTarget;
      await withBusy(button, async () => {
        try {
          await api.deleteWater(last.id, day.date);
          haptic('light');
          toast('Последняя запись воды удалена', 'success');
          await ctx.refresh();
        } catch (error) {
          haptic('error');
          toast(formatError(error), 'error');
        }
      });
    });

    root.querySelectorAll('[data-meal-delete]').forEach((button) => {
      button.addEventListener('click', () => {
        const mealId = Number(button.dataset.mealDelete);
        const meal = meals.find((item) => item.id === mealId);
        if (!meal) return;
        confirmSheet({
          title: 'Удалить приём пищи?',
          message: `«${meal.description}»`,
          confirmLabel: 'Удалить',
          onConfirm: async () => {
            await api.deleteMeal(mealId, day.date);
            toast('Приём пищи удалён', 'success');
            await ctx.refresh();
          },
        });
      });
    });

    root.querySelector('[data-measure]')?.addEventListener('click', () => openMeasurementSheet(day, ctx));
  }

  bind();

  const proteinWrap = root.querySelector('#protein-wrap');
  if (proteinWrap) {
    if (!weekHasMeals) {
      proteinWrap.innerHTML = emptyState({
        iconName: 'apple',
        title: 'Нет данных за неделю',
        text: 'Добавьте приём пищи с белком — график появится автоматически.',
      });
    } else {
      barChart(root.querySelector('#protein-chart'), {
        labels: proteinSeries.map((item) => item.label),
        values: proteinSeries.map((item) => (item.has_meals ? item.protein_g : null)),
        target: targets.protein_g,
        tone: 'warning',
        ySuffix: 'г',
        formatValue: (value) => `${formatNumber(value, 0)} г`,
        formatY: (value) => `${Math.round(value)}г`,
      });
    }
  }

  const weightWrap = root.querySelector('#weight-wrap');
  if (weightWrap) {
    const useWeight = measurements.weight_series.length >= 2;
    const series = useWeight ? measurements.weight_series : measurements.waist_series;
    lineChart(root.querySelector('#weight-chart'), {
      labels: series.map((item) => item.label),
      values: series.map((item) => item.value),
      tone: 'info',
      ySuffix: useWeight ? 'кг' : 'см',
      formatValue: (value) => `${formatNumber(value, 1)} ${useWeight ? 'кг' : 'см'}`,
      formatY: (value) => formatNumber(value, 1),
      fill: false,
      beginAtZero: false,
    });
    const canvas = root.querySelector('#weight-chart');
    if (canvas) canvas.setAttribute('aria-label', useWeight ? 'График веса' : 'График обхвата талии');
  }


  return () => destroyCharts();
}
