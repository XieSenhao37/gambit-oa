import dayjs from 'dayjs';

// 生成模拟数据
const genList = (current: number, pageSize: number) => {
  const list: API.PlayOrder[] = [];
  const total = 100;

  for (let i = 0; i < pageSize; i++) {
    const index = (current - 1) * pageSize + i;
    if (index >= total) break;

    const inTime = dayjs().subtract(Math.floor(Math.random() * 48), 'hour');

    list.push({
      Id: index + 1,
      OpenId: `user_${Math.floor(Math.random() * 1000)}`,
      InTime: inTime.format('YYYY-MM-DD HH:mm:ss'),
      OutTime:
        index % 3 === 0
          ? inTime
              .add(Math.floor(Math.random() * 5), 'hour')
              .format('YYYY-MM-DD HH:mm:ss')
          : undefined,
      PlayTime: index % 3 === 0 ? Math.floor(Math.random() * 5) + 1 : undefined,
      UnitPrice: index % 3 === 0 ? 2000 : undefined, // 20元/小时
      Amount:
        index % 3 === 0
          ? (Math.floor(Math.random() * 5) + 1) * 2000
          : undefined,
      SettleStatus: index % 3 === 0 ? 1 : 0,
      Comment: index % 4 === 0 ? '这是一条测试备注' : undefined,
      CreatedAt: inTime.format('YYYY-MM-DD HH:mm:ss'),
      UpdatedAt: inTime.format('YYYY-MM-DD HH:mm:ss'),
      User: {
        NickName: `用户${index + 1}`,
        Id: index + 1,
        OpenId: `user_${index + 1}`,
      },
    });
  }

  return { list, total };
};

export default {
  // 查询订单列表
  'GET /admin_api/order/v1/list': (req: any, res: any) => {
    const current = Number(req.query.current) || 1;
    const pageSize = Number(req.query.pageSize) || 10;
    const settleStatus = req.query.SettleStatus;

    const { list, total } = genList(current, pageSize);

    // 如果有状态筛选
    const filteredList =
      settleStatus !== undefined
        ? list.filter((item) => item.SettleStatus === Number(settleStatus))
        : list;

    setTimeout(() => {
      res.json({
        Code: 0,
        Msg: 'success',
        Data: {
          List: filteredList,
          Total: total,
          Current: current,
          PageSize: pageSize,
        },
      });
    }, 500); // 增加 500ms 延迟模拟网络请求
  },

  // 批量结算订单
  'PUT /admin_api/order/v1/batch-settle': (req: any, res: any) => {
    const { OrderIds } = req.body;

    setTimeout(() => {
      if (Array.isArray(OrderIds) && OrderIds.length > 0) {
        res.json({
          Code: 0,
          Msg: 'success',
          Data: null,
        });
      } else {
        res.json({
          Code: 400,
          Msg: '无效的订单ID列表',
          Data: null,
        });
      }
    }, 500);
  },
};
