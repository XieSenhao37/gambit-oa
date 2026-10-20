// Serve precompressed JavaScript/CSS without compressing on every request.
const fs = require('node:fs');
const path = require('node:path');
const { gzipSync } = require('node:zlib');
const root = path.resolve(__dirname, '../dist');
let count = 0;
function compress(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) compress(filename);
    else if (/\.(js|css)$/.test(entry.name)) {
      const raw = fs.readFileSync(filename);
      const gzip = gzipSync(raw, { level: 9 });
      if (gzip.length < raw.length) {
        fs.writeFileSync(`${filename}.gz`, gzip);
        count++;
      }
    }
  }
}
compress(root);
console.log(`Precompressed ${count} JavaScript/CSS assets`);
