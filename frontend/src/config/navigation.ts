import pages from './pages.json';

const aliases: Record<string, string[]> = {
  workbench: ['收银', '入场', '离场', '制作', '做饮品', '今天待办'],
  orders: ['游玩记录', '历史游玩订单'],
  'catering-orders': ['饮品订单', '历史餐饮订单'],
  'game-service-orders': [
    '租借',
    '租赁订单',
    '卖桌游',
    '退押金',
    '归还',
    '发货',
    '确认订单',
  ],
  games: [
    '桌游库存',
    '上架',
    '改租金',
    '改售价',
    '押金',
    '可租数量',
    '可售数量',
  ],
  'game-library': ['桌游信息库', '桌游封面', '桌游规则'],
  'game-services': [
    '收货地址',
    '邮寄归还地址',
    '配送',
    '顺丰',
    '长租折扣',
    '租期',
  ],
  'game-community': ['想玩', '玩家分享', '社区', '优质分享'],
  'play-pricing': [
    '收费',
    '计费设置',
    '小时价格',
    '入场价格',
    '全天封顶',
    '桌游计价管理',
  ],
  'dish-categories': ['菜品分类', '饮品分类', '分类排序', '分类管理'],
  users: ['用户管理', '找玩家', '手机号'],
  'month-card-open': ['赠卡', '开卡', '月卡'],
  'home-banners': ['轮播', '首页', '宣传'],
  'staff-access': ['权限', '员工', '门店授权'],
  dashboard: ['数据仪表盘', '营收', '统计'],
};

/** Only return registered pages the current account can access. */
export function searchFunctions(
  query: string,
  allowedPages: readonly string[],
) {
  const allowed = new Set(allowedPages);
  const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const visible = pages.filter((page) => allowed.has(page.id));
  if (!words.length) return visible.slice(0, 8);
  return visible
    .filter((page) => {
      const terms = [
        page.name,
        page.group?.name || '',
        ...(aliases[page.id] || []),
      ]
        .join(' ')
        .toLocaleLowerCase();
      return words.every((word) => terms.includes(word));
    })
    .slice(0, 12);
}
