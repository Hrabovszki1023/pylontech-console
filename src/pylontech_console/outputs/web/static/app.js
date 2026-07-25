(() => {
  "use strict";

  const CHANGE_DURATION_MS = 3000;
  const selector = "[data-cell-voltage-key][data-cell-voltage-mv]";
  let previousValues = new Map();
  const activeUntil = new Map();
  const removalTimers = new Map();
  let initialized = false;

  function currentMeasurements() {
    const measurements = new Map();
    document.querySelectorAll(selector).forEach((element) => {
      const key = element.dataset.cellVoltageKey;
      const value = Number(element.dataset.cellVoltageMv);
      if (key && Number.isInteger(value)) {
        measurements.set(key, {element, value});
      }
    });
    return measurements;
  }

  function clearRemovalTimer(key) {
    const timer = removalTimers.get(key);
    if (timer !== undefined) {
      window.clearTimeout(timer);
      removalTimers.delete(key);
    }
  }

  function showChange(key, element, until) {
    clearRemovalTimer(key);
    element.classList.add("cell-voltage-changed");
    const remaining = Math.max(0, until - Date.now());
    const timer = window.setTimeout(() => {
      element.classList.remove("cell-voltage-changed");
      activeUntil.delete(key);
      removalTimers.delete(key);
    }, remaining);
    removalTimers.set(key, timer);
  }

  function refreshMeasurements() {
    const nextValues = currentMeasurements();
    const now = Date.now();

    nextValues.forEach(({element, value}, key) => {
      const previous = previousValues.get(key);
      if (previous !== undefined && previous !== value) {
        const until = now + CHANGE_DURATION_MS;
        activeUntil.set(key, until);
        showChange(key, element, until);
        return;
      }
      const until = activeUntil.get(key);
      if (until !== undefined && until > now) {
        showChange(key, element, until);
      }
    });

    activeUntil.forEach((_until, key) => {
      if (!nextValues.has(key)) {
        activeUntil.delete(key);
        clearRemovalTimer(key);
      }
    });
    previousValues = new Map(
      Array.from(nextValues, ([key, measurement]) => [
        key,
        measurement.value,
      ]),
    );
  }

  function initialize() {
    if (initialized) {
      return;
    }
    initialized = true;
    previousValues = new Map(
      Array.from(currentMeasurements(), ([key, measurement]) => [
        key,
        measurement.value,
      ]),
    );
    document.body.addEventListener("htmx:afterSwap", refreshMeasurements);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, {once: true});
  } else {
    initialize();
  }
})();
