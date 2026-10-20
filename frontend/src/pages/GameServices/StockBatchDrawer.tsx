import { call, newRequestKey, Stock } from '@/services/gameServices';
import {
  Alert,
  AutoComplete,
  Button,
  Drawer,
  Input,
  InputNumber,
  message,
  Space,
  Table,
} from 'antd';
import { useRef, useState } from 'react';

export type BatchMode = 'rental' | 'purchase' | 'quantity' | 'rental_price';
const titles = {
  rental: '批量上架租赁库',
  purchase: '批量上架出售库',
  quantity: '批量设置库存',
  rental_price: '批量设置日租价',
};
export default function StockBatchDrawer({
  mode,
  games,
  stocks,
  selected,
  onClose,
  onSaved,
}: {
  mode: BatchMode;
  games: API.BoardGame[];
  stocks: Stock[];
  selected: Stock[];
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const creating = mode === 'rental' || mode === 'purchase';
  const [ids, setIDs] = useState<number[]>([]);
  const [keyword, setKeyword] = useState('');
  const [quantity, setQuantity] = useState<number | null>(1);
  const [price, setPrice] = useState<number | null>(null);
  const [deposit, setDeposit] = useState<number | null>(0);
  const [condition, setCondition] = useState('全新未拆');
  const [salePrices, setSalePrices] = useState<Record<number, number | null>>(
    {}
  );
  const [remark, setRemark] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const retry = useRef<{ signature: string; key: string }>();
  const gameName = (id: number) =>
    games.find((g) => g.Id === id)?.Name || `桌游 #${id}`;
  const available = (id: number) =>
    Math.max(
      0,
      (games.find((g) => g.Id === id)?.Count || 0) -
        stocks
          .filter((s) => s.BoardGameID === id)
          .reduce((n, s) => n + s.Quantity, 0)
    );
  const unselectable = (id: number) =>
    available(id) === 0 ||
    (mode === 'rental' &&
      stocks.some((s) => s.BoardGameID === id && s.Kind === 'rental'));
  async function save() {
    setError('');
    const chosen = creating ? ids : selected.map((s) => s.ID);
    if (!chosen.length || chosen.length > 100) {
      setError('请一次选择1至100项');
      return;
    }
    if (
      mode !== 'rental_price' &&
      (quantity === null ||
        !Number.isInteger(quantity) ||
        quantity < (creating ? 1 : 0))
    ) {
      setError('请输入合法库存数量');
      return;
    }
    if (
      (mode === 'rental' || mode === 'rental_price') &&
      (!price || price < 0.01)
    ) {
      setError('请输入日租价');
      return;
    }
    if (
      mode === 'purchase' &&
      (!condition.trim() ||
        ids.some((id) => !salePrices[id] || salePrices[id]! < 0.01))
    ) {
      setError('请填写品相，并为每款桌游分别填写售价');
      return;
    }
    const payload = {
      Mode: creating ? 'create' : mode,
      Remark: remark,
      ...(mode === 'quantity' ? { Quantity: quantity } : {}),
      ...(mode === 'rental_price' ? { Price: Math.round(price! * 100) } : {}),
      Items: creating
        ? [...ids]
            .sort((a, b) => a - b)
            .map((id) => ({
              BoardGameID: id,
              Kind: mode,
              Quantity: quantity,
              Enabled: true,
              Price: Math.round(
                (mode === 'rental' ? price! : salePrices[id]!) * 100
              ),
              Deposit: mode === 'rental' ? Math.round((deposit || 0) * 100) : 0,
              Condition: mode === 'purchase' ? condition.trim() : '',
            }))
        : selected.map((s) => ({
            ID: s.ID,
            BoardGameID: s.BoardGameID,
            Version: s.Version,
          })),
    };
    const signature = JSON.stringify(payload);
    if (retry.current?.signature !== signature)
      retry.current = { signature, key: newRequestKey() };
    setSaving(true);
    try {
      await call('stock/batch', 'POST', {
        ...payload,
        RequestKey: retry.current!.key,
      });
      message.success(`已完成${chosen.length}项${creating ? '上架' : '更新'}`);
      await onSaved();
      onClose();
    } catch (e: any) {
      const raw =
        e?.info?.errorMessage ||
        e?.response?.data?.Message ||
        e?.message ||
        '保存失败，请刷新确认后重试';
      setError(
        String(raw).replace(/桌游 #(\d+)/g, (_: string, id: string) =>
          gameName(Number(id))
        )
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <Drawer
      open
      title={titles[mode]}
      width={760}
      onClose={() => !saving && onClose()}
      closable={!saving}
      maskClosable={!saving}
      extra={
        <Button type="primary" loading={saving} onClick={save}>
          {creating ? '确认上架' : '确认设置'}
        </Button>
      }
    >
      <Space direction="vertical" size={20} style={{ width: '100%' }}>
        {error && <Alert type="error" showIcon message={error} />}
        {!creating && (
          <Alert
            type="info"
            message={
              mode === 'quantity'
                ? `已选择${selected.length}项。设置的是每项库存总量，不是增加数量；已接单、出租和待检查数量会保留。`
                : `已选择${selected.length}项租赁库存，仅更新日租价，库存和押金保持原值。`
            }
          />
        )}
        <Space wrap size={20}>
          {mode !== 'rental_price' && (
            <label>
              {creating ? '每款上架数量' : '每项库存总量'}　
              <InputNumber
                disabled={saving}
                min={creating ? 1 : 0}
                max={100000}
                precision={0}
                value={quantity}
                onChange={setQuantity}
              />
            </label>
          )}
          {(mode === 'rental' || mode === 'rental_price') && (
            <label>
              日租价（元）　
              <InputNumber
                disabled={saving}
                min={0.01}
                max={1000000}
                precision={2}
                value={price}
                onChange={setPrice}
              />
            </label>
          )}
          {mode === 'rental' && (
            <label>
              每份押金（元）　
              <InputNumber
                disabled={saving}
                min={0}
                max={1000000}
                precision={2}
                value={deposit}
                onChange={setDeposit}
              />
            </label>
          )}
          {mode === 'purchase' && (
            <label>
              品相　
              <AutoComplete
                disabled={saving}
                style={{ width: 180 }}
                value={condition}
                onChange={setCondition}
                options={[
                  '全新未拆',
                  '几乎全新',
                  '轻微使用痕迹',
                  '明显使用痕迹',
                ].map((v) => ({ value: v, label: v }))}
              />
            </label>
          )}
        </Space>
        {creating ? (
          <>
            <Input.Search
              disabled={saving}
              placeholder="搜索当前门店桌游"
              allowClear
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
            <Table<API.BoardGame>
              size="small"
              rowKey="Id"
              dataSource={games.filter((g) => g.Name.includes(keyword))}
              pagination={{
                defaultPageSize: 20,
                showSizeChanger: true,
                pageSizeOptions: [20, 50, 100],
              }}
              rowSelection={{
                selectedRowKeys: ids,
                preserveSelectedRowKeys: true,
                onChange: (keys) => setIDs(keys.map(Number)),
                getCheckboxProps: (g) => ({
                  disabled: saving || unselectable(g.Id),
                }),
              }}
              columns={[
                { title: '桌游', dataIndex: 'Name' },
                {
                  title: '未分配',
                  width: 90,
                  render: (_, g) => available(g.Id),
                },
                ...(mode === 'purchase'
                  ? [
                      {
                        title: '售价（元）',
                        width: 160,
                        render: (_: unknown, g: API.BoardGame) => (
                          <InputNumber
                            aria-label={`${g.Name}售价`}
                            disabled={saving || !ids.includes(g.Id)}
                            min={0.01}
                            max={1000000}
                            precision={2}
                            value={salePrices[g.Id]}
                            onChange={(v) =>
                              setSalePrices({ ...salePrices, [g.Id]: v })
                            }
                          />
                        ),
                      },
                    ]
                  : [
                      {
                        title: '租赁库',
                        width: 100,
                        render: (_: unknown, g: API.BoardGame) =>
                          stocks.some(
                            (s) => s.BoardGameID === g.Id && s.Kind === 'rental'
                          )
                            ? '已有，去编辑'
                            : '未上架',
                      },
                    ]),
              ]}
            />
            <span>
              已选 {ids.length}{' '}
              款。已分配完的桌游不能重复分配；服务总开关在“服务规则与开关”中设置。
            </span>
          </>
        ) : (
          <Table<Stock>
            size="small"
            rowKey="ID"
            dataSource={selected}
            pagination={false}
            columns={[
              { title: '桌游', render: (_, s) => gameName(s.BoardGameID) },
              {
                title: '用途／品相',
                render: (_, s) => (s.Kind === 'rental' ? '租赁' : s.Condition),
              },
              { title: '当前库存总量', dataIndex: 'Quantity' },
              {
                title: '已占用',
                render: (_, s) => s.Reserved + s.Out + s.Held,
              },
            ]}
          />
        )}
        <Input.TextArea
          disabled={saving}
          placeholder="备注（选填）"
          maxLength={500}
          rows={2}
          value={remark}
          onChange={(e) => setRemark(e.target.value)}
        />
      </Space>
    </Drawer>
  );
}
