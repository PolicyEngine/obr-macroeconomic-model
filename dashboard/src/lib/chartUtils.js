const NICE_STEPS = [1, 2, 2.5, 5, 10];

function niceStep(roughStep) {
  if (roughStep <= 0) {
    return 1;
  }

  const exponent = Math.floor(Math.log10(roughStep));
  const magnitude = 10 ** exponent;
  const normalized = roughStep / magnitude;
  const nice = NICE_STEPS.find((step) => step >= normalized - 1e-10) ?? 10;

  return nice * magnitude;
}

export function getNiceTicks(domain, count = 5) {
  const [domainMin, domainMax] = domain;

  if (domainMin === domainMax) {
    return [domainMin];
  }

  const rawStep = (domainMax - domainMin) / Math.max(count - 1, 1);
  const step = niceStep(rawStep);
  const start = Math.floor(domainMin / step) * step;
  const ticks = [];

  for (let value = start; value <= domainMax + step * 0.01; value += step) {
    const rounded = Math.round(value * 1e10) / 1e10 || 0;
    ticks.push(rounded);
  }

  if (ticks.length >= 2 && ticks[ticks.length - 1] < domainMax) {
    const lastTick = Math.round((ticks[ticks.length - 1] + step) * 1e10) / 1e10 || 0;
    ticks.push(lastTick);
  }

  return ticks;
}

export function getTickDomain(ticks) {
  if (!ticks.length) {
    return [0, 0];
  }

  return [ticks[0], ticks[ticks.length - 1]];
}
