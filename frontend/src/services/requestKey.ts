// randomUUID is unavailable on the HTTP test OA. Keys identify retries, not secrets.
export function newRequestKey(): string {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  if (globalThis.crypto?.getRandomValues) {
    return Array.from(
      globalThis.crypto.getRandomValues(new Uint8Array(16)),
      (v) => v.toString(16).padStart(2, '0')
    ).join('');
  }
  return `oa-${Date.now().toString(36)}-${(++requestSequence).toString(
    36
  )}-${Math.random().toString(36).slice(2, 12)}`;
}
let requestSequence = 0;
