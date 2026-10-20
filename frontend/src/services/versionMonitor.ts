const VERSION_PATTERN = /^[a-f0-9]{32}$/;
export const VERSION_CHECK_INTERVAL = 60_000;

export function readPageVersion(): string {
  return (
    document
      .querySelector('meta[name="oa-build-version"]')
      ?.getAttribute('content') || ''
  );
}

/** One global monitor; metadata requests never enter the business auth/error handlers. */
export function startVersionMonitor(
  current: string,
  onChange: (version: string) => void,
): () => void {
  if (!VERSION_PATTERN.test(current)) return () => {};
  let stopped = false;
  let pending: AbortController | undefined;
  let lastStarted = -Infinity;
  let announced = '';
  const check = async () => {
    if (
      stopped ||
      document.visibilityState === 'hidden' ||
      pending ||
      Date.now() - lastStarted < 1_000
    )
      return;
    lastStarted = Date.now();
    const controller = new AbortController();
    pending = controller;
    const timeout = window.setTimeout(() => controller.abort(), 10_000);
    try {
      const response = await window.fetch('/version.json', {
        cache: 'no-store',
        credentials: 'omit',
        signal: controller.signal,
      });
      if (!response.ok) return;
      const data: unknown = await response.json();
      const version =
        data && typeof data === 'object' && 'version' in data
          ? data.version
          : undefined;
      if (
        stopped ||
        typeof version !== 'string' ||
        !VERSION_PATTERN.test(version)
      )
        return;
      const next = version === current ? '' : version;
      if (next !== announced) {
        announced = next;
        onChange(next);
      }
    } catch {
      // Offline, missing metadata, timeouts and older servers stay silent.
    } finally {
      window.clearTimeout(timeout);
      if (pending === controller) pending = undefined;
    }
  };
  const update = () => {
    void check();
  };
  const interval = window.setInterval(update, VERSION_CHECK_INTERVAL);
  window.addEventListener('focus', update);
  window.addEventListener('online', update);
  document.addEventListener('visibilitychange', update);
  update();
  return () => {
    stopped = true;
    pending?.abort();
    window.clearInterval(interval);
    window.removeEventListener('focus', update);
    window.removeEventListener('online', update);
    document.removeEventListener('visibilitychange', update);
  };
}
