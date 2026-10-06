const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
class File extends Blob { constructor(parts, name, opts) { super(parts, opts); this.name = name; } }
let revoked = 0, canvas, outputType;
const sandbox = { exports: {}, Blob, File,
  URL: { createObjectURL: () => 'blob:mock', revokeObjectURL: () => revoked++ },
  Image: class { naturalWidth = 3200; naturalHeight = 2400; set src(value) { queueMicrotask(() => this.onload()); } },
  document: { createElement: () => (canvas = { width: 0, height: 0, getContext: () => ({ drawImage() {} }), toBlob(fn, type) { outputType = type; fn(new Blob(['small'], { type })); } }) },
};
vm.runInNewContext(ts.transpileModule(fs.readFileSync('src/utils/gameImage.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, sandbox);
(async () => {
  const { compressGameImage, runGameImageUpload } = sandbox.exports;
  const jpeg = new File(['x'.repeat(100)], 'photo.jpeg', { type: 'image/jpeg' });
  const compressed = await compressGameImage(jpeg);
  assert.equal(canvas.width, 1600); assert.equal(canvas.height, 1200);
  assert.equal(compressed.type, 'image/jpeg'); assert.ok(compressed.size < jpeg.size);
  assert.equal(revoked, 1);
  const gif = new File(['gif'], 'animation.gif');
  assert.equal(await compressGameImage(gif), gif, 'preserve animated GIF even without MIME');
  await compressGameImage(new File(['x'.repeat(100)], 'transparent.webp', { type: 'image/webp' }));
  assert.equal(outputType, 'image/png', 'preserve transparency');
  const tiny = new File(['x'], 'tiny.png', { type: 'image/png' });
  assert.equal(await compressGameImage(tiny), tiny, 'do not enlarge an image');
  let active = 0, max = 0;
  const releases = [];
  const uploads = Array.from({ length: 6 }, (_, i) => runGameImageUpload(async () => {
    active++; max = Math.max(max, active);
    await new Promise(resolve => releases.push(resolve));
    active--; if (i === 0) throw new Error('mock failure');
  }).catch(() => {}));
  for (let i = 0; i < 6; i++) {
    while (!releases.length) await Promise.resolve();
    releases.shift()();
    for (let j = 0; j < 5; j++) await Promise.resolve();
  }
  await Promise.all(uploads); assert.equal(max, 2); assert.equal(active, 0);
  console.log('Image resize, format preservation, size fallback and upload concurrency passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
