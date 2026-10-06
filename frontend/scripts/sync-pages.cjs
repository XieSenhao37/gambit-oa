const fs = require('fs');
const path = require('path');
const pages = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, '../../backend/app/security/pages.json'),
    'utf8',
  ),
);
if (
  new Set(pages.map((p) => p.id)).size !== pages.length ||
  new Set(pages.map((p) => p.path)).size !== pages.length
)
  throw Error('页面标识和路由不得重复');
fs.writeFileSync(
  path.join(__dirname, '../src/config/pages.json'),
  JSON.stringify(pages, null, 2) + '\n',
);
