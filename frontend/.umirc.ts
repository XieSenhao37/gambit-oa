import { defineConfig } from '@umijs/max';
import { randomBytes } from 'node:crypto';
import pages from './src/config/pages.json';

export default defineConfig({
  antd: {},
  access: {},
  model: {},
  initialState: {},
  metas: [
    { name: 'oa-build-version', content: randomBytes(16).toString('hex') },
  ],
  layout: {
    title: 'Gambit后台管理系统',
    locale: false,
    footer:
      '<a href="https://beian.miit.gov.cn/" target="_blank">浙ICP备XXXXXXXX号-X</a>',
  },
  favicons: ['/favicon.ico'],
  routes: [
    { path: '/login', component: './Login', layout: false },
    { path: '/', redirect: '/workbench', wrappers: ['@/wrappers/auth'] },
    {
      path: '/catering',
      redirect: '/workbench?tab=catering',
      wrappers: ['@/wrappers/auth'],
    },
    ...pages.map(({ path, name, component }) => ({
      path,
      name,
      component,
      wrappers: ['@/wrappers/auth'],
      hideInMenu: true,
    })),
  ],
  npmClient: 'pnpm',
  proxy: {
    '/admin_api': {
      target: 'http://127.0.0.1:8080',
      changeOrigin: true,
    },
  },
  request: {
    dataField: 'data',
  },
  mock: false,
  hash: true,
  codeSplitting: { jsStrategy: 'granularChunks' },
});
