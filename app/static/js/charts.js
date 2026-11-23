const TONE_TOKENS = {
  accent: ['--color-accent', '--color-accent-soft'],
  success: ['--color-success', '--color-success-soft'],
  warning: ['--color-warning', '--color-warning-soft'],
  info: ['--color-info', '--color-info-soft'],
  violet: ['--color-violet', '--color-violet-soft'],
  danger: ['--color-danger', '--color-danger-soft'],
};

const instances = new Set();
let configured = false;

function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function toneColor(tone) {
  return token(TONE_TOKENS[tone]?.[0] || '--color-accent');
}

function toneSoft(tone) {
  return token(TONE_TOKENS[tone]?.[1] || '--color-accent-soft');
}

function chartLibrary() {
  return window.Chart || null;
}

export function configureCharts() {
  const Chart = chartLibrary();
  if (!Chart || configured) return;
  configured = true;
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 10;
  Chart.defaults.color = token('--color-muted');
  Chart.defaults.borderColor = token('--chart-grid');
}

function reducedMotion() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}

function baseOptions({ yMax = null, ySuffix = '', formatValue = null, formatY = null, beginAtZero = true } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: reducedMotion() ? false : { duration: 450 },
    interaction: { mode: 'index', intersect: false },
    layout: { padding: { top: 4, right: 2, bottom: 0, left: 0 } },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: token('--color-surface-raised'),
        titleColor: token('--color-text'),
        bodyColor: token('--color-text-soft'),
        borderColor: token('--color-border-strong'),
        borderWidth: 1,
        cornerRadius: 10,
        padding: 10,
        displayColors: false,
        titleFont: { size: 11, weight: '600' },
        bodyFont: { size: 11 },
        callbacks: {
          label(context) {
            const raw = context.parsed?.y;
            if (raw === null || raw === undefined) return 'Нет данных';
            const value = formatValue ? formatValue(raw) : `${raw}${ySuffix ? ` ${ySuffix}` : ''}`;
            const prefix = context.dataset?.label ? `${context.dataset.label}: ` : '';
            return `${prefix}${value}`;
          },
        },
      },
    },
    scales: {
      x: {
        grid: { display: false, drawBorder: false },
        border: { display: false },
        ticks: {
          color: token('--color-muted'),
          font: { size: 9.5, weight: '500' },
          maxRotation: 0,
          autoSkip: true,
          maxTicksLimit: 10,
          padding: 4,
        },
      },
      y: {
        beginAtZero,
        suggestedMax: yMax ?? undefined,
        grid: { color: token('--chart-grid'), drawTicks: false },
        border: { display: false },
        ticks: {
          color: token('--color-muted'),
          font: { size: 9.5 },
          padding: 6,
          maxTicksLimit: 5,
          callback(value) {
            if (formatY) return formatY(value);
            return Number.isInteger(value) ? value : String(value).replace('.', ',');
          },
        },
      },
    },
  };
}

function register(instance) {
  instances.add(instance);
  return instance;
}

export function destroyCharts() {
  instances.forEach((instance) => {
    try {
      instance.destroy();
    } catch {
      /* already destroyed */
    }
  });
  instances.clear();
}

export function barChart(
  canvas,
  {
    labels = [],
    values = [],
    target = null,
    tone = 'accent',
    yMax = null,
    ySuffix = '',
    formatValue = null,
    formatY = null,
  } = {},
) {
  configureCharts();
  const Chart = chartLibrary();
  if (!Chart || !canvas) return null;

  const main = toneColor(tone);
  const success = token('--color-success');
  const empty = token('--color-surface-soft');
  const colors = values.map((value) => {
    if (value === null || value === undefined) return empty;
    if (target !== null && target !== undefined && Number(value) >= Number(target)) return success;
    return main;
  });

  const datasets = [
    {
      type: 'bar',
      label: 'Значение',
      data: values,
      backgroundColor: colors,
      borderRadius: 7,
      borderSkipped: false,
      barPercentage: 0.64,
      categoryPercentage: 0.82,
    },
  ];

  if (target !== null && target !== undefined) {
    datasets.push({
      type: 'line',
      label: 'Цель',
      data: labels.map(() => target),
      borderColor: token('--color-warning'),
      borderDash: [5, 5],
      borderWidth: 1.4,
      pointRadius: 0,
      pointHitRadius: 0,
      fill: false,
      tension: 0,
    });
  }

  return register(
    new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: { labels, datasets },
      options: baseOptions({ yMax, ySuffix, formatValue, formatY }),
    }),
  );
}

export function lineChart(
  canvas,
  {
    labels = [],
    values = [],
    target = null,
    tone = 'accent',
    yMax = null,
    ySuffix = '',
    formatValue = null,
    formatY = null,
    fill = true,
    beginAtZero = true,
  } = {},
) {
  configureCharts();
  const Chart = chartLibrary();
  if (!Chart || !canvas) return null;

  const main = toneColor(tone);
  const soft = toneSoft(tone);
  const context = canvas.getContext('2d');
  const height = canvas.parentElement?.clientHeight || 200;
  const gradient = context.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, soft);
  gradient.addColorStop(1, token('--color-transparent'));
  // A line with one non-null point has no segment to draw, so make the
  // single point visible instead of showing an empty chart.
  const pointCount = values.filter((value) => value !== null && value !== undefined).length;

  const datasets = [
    {
      type: 'line',
      label: 'Значение',
      data: values,
      borderColor: main,
      backgroundColor: fill ? gradient : 'transparent',
      fill,
      tension: 0.35,
      borderWidth: 2.5,
      pointRadius: pointCount === 1 ? 4 : pointCount <= 14 ? 3 : 0,
      pointHoverRadius: 4,
      pointBackgroundColor: main,
      pointBorderColor: token('--color-bg'),
      pointBorderWidth: 2,
      spanGaps: true,
    },
  ];

  if (target !== null && target !== undefined) {
    datasets.push({
      type: 'line',
      label: 'Цель',
      data: labels.map(() => target),
      borderColor: token('--color-warning'),
      borderDash: [5, 5],
      borderWidth: 1.4,
      pointRadius: 0,
      pointHitRadius: 0,
      fill: false,
      tension: 0,
    });
  }

  return register(
    new Chart(context, {
      type: 'line',
      data: { labels, datasets },
      options: baseOptions({ yMax, ySuffix, formatValue, formatY, beginAtZero }),
    }),
  );
}
