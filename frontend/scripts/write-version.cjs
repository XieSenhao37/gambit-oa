const fs = require('node:fs');
const path = require('node:path');

function writeVersion(directory) {
  const html = fs.readFileSync(path.join(directory, 'index.html'), 'utf8');
  const tag = (html.match(/<meta\b[^>]*>/gi) || []).find((item) =>
    /\bname=["']oa-build-version["']/i.test(item),
  );
  const version = tag?.match(/\bcontent=["']([a-f0-9]{32})["']/i)?.[1];
  if (!version) throw new Error('Missing OA build version in generated HTML');
  fs.writeFileSync(path.join(directory, 'version.json'), JSON.stringify({ version }) + '\n');
  return version;
}
if (require.main === module) {
  console.log(`OA build version: ${writeVersion(path.resolve(__dirname, '../dist'))}`);
}
module.exports = { writeVersion };
