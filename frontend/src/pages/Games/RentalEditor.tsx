import { Table } from '@/components/AdaptiveTable';
import {
  Inventory,
  newRequestKey,
  saveGameInventories,
} from '@/services/gameServices';
import {
  Alert,
  AutoComplete,
  Button,
  Col,
  Collapse,
  Drawer,
  Form,
  Row as GridRow,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  message,
} from 'antd';
import { useRef, useState } from 'react';
import './rentalEditor.less';
type Row = Inventory & { Name: string };
export default function RentalEditor({
  rows,
  onClose,
  onSaved,
}: {
  rows: Row[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [items, setItems] = useState(rows);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [field, setField] = useState('Quantity'),
    [value, setValue] = useState<number | null>(null);
  const retry = useRef<{ signature: string; keys: string[] }>();
  const update = (id: number, patch: Partial<Row>) => {
    if (busy) return;
    setItems((old) =>
      old.map((r) => (r.BoardGameID === id ? { ...r, ...patch } : r)),
    );
  };
  const dirty = JSON.stringify(items) !== JSON.stringify(rows);
  const close = () => {
    if (busy) return;
    if (!dirty) {
      onClose();
      return;
    }
    Modal.confirm({
      title: '放弃未保存的修改？',
      content: '关闭后，本次库存和租售调整不会保存。',
      okText: '放弃修改',
      cancelText: '继续编辑',
      onOk: onClose,
    });
  };
  async function save() {
    if (busy) return;
    setError('');
    const invalid = items.find(
      (r) =>
        !Number.isInteger(r.Total) ||
        !Number.isInteger(r.Quantity) ||
        r.Quantity < r.Reserved + r.Out + r.Held ||
        r.Quantity > r.Total,
    );
    if (invalid) {
      setError(
        `${invalid.Name}：对外数量应不少于已占用数量，且不能超过总数量。`,
      );
      return;
    }
    if (items.some((r) => r.MultipleOffers)) {
      setError('存在多个旧品相／报价，请先核对，不能自动合并。');
      return;
    }
    const signature = JSON.stringify(items);
    if (retry.current?.signature !== signature)
      retry.current = { signature, keys: items.map(() => newRequestKey()) };
    setBusy(true);
    try {
      await saveGameInventories(
        items.map((r, i) => ({ ...r, RequestKey: retry.current!.keys[i] })),
      );
      message.success('库存与租售配置已保存');
      onSaved();
      onClose();
    } catch (e: any) {
      setError(
        e?.info?.errorMessage || e?.message || '保存未确认，请刷新核实后重试',
      );
    } finally {
      setBusy(false);
    }
  }
  const currency = (
    r: Row,
    key: 'RentalPrice' | 'Deposit' | 'PurchasePrice',
  ) => (
    <InputNumber
      aria-label={`${r.Name}${
        { RentalPrice: '日租金', Deposit: '押金', PurchasePrice: '售价' }[key]
      }`}
      disabled={busy}
      min={0}
      precision={2}
      value={r[key] / 100}
      onChange={(v) =>
        update(r.BoardGameID, { [key]: Math.round((v || 0) * 100) })
      }
      addonBefore="¥"
      style={{ width: 130 }}
    />
  );
  const occupancy = (r: Row) => (
    <span className="oa-inventory-occupancy">
      待付款 / 交付 {r.Reserved} · 已借出 {r.Out} · 待处理 {r.Held}
    </span>
  );
  const extraFields = (r: Row) => (
    <div className="oa-inventory-extras">
      <Form.Item label="出售品相">
        <AutoComplete
          disabled={busy || !r.PurchaseEnabled}
          aria-label={`${r.Name}出售品相`}
          value={r.Condition || undefined}
          placeholder="选择或输入品相"
          options={['全新未拆', '几乎全新', '轻微使用痕迹', '明显使用痕迹'].map(
            (value) => ({ label: value, value }),
          )}
          onChange={(value) => update(r.BoardGameID, { Condition: value })}
        />
      </Form.Item>
      <Form.Item label="配件与品相说明（选填）">
        <Input.TextArea
          disabled={busy}
          value={r.Description}
          autoSize={{ minRows: 2, maxRows: 4 }}
          maxLength={3000}
          onChange={(event) =>
            update(r.BoardGameID, { Description: event.target.value })
          }
        />
      </Form.Item>
      <div className="oa-inventory-option">
        <span>允许租后购买</span>
        <Switch
          aria-label={`${r.Name}允许租后购买`}
          disabled={busy || !r.RentalEnabled || !r.PurchaseEnabled}
          checked={r.BuyoutEnabled}
          onChange={(checked) =>
            update(r.BoardGameID, { BuyoutEnabled: checked })
          }
        />
      </div>
      {r.BuyoutEnabled && (
        <p className="oa-secondary">
          租金与押金抵购款，多退少补。当前售价和品相须适用于出租的实物。
        </p>
      )}
    </div>
  );
  return (
    <Drawer
      open
      rootClassName="oa-inventory-editor"
      title={
        items.length === 1
          ? `${items[0].Name} · 库存与租售`
          : `批量编辑 · ${items.length} 款桌游`
      }
      width={items.length === 1 ? 640 : 1180}
      onClose={close}
      maskClosable={!busy}
      closable={!busy}
      footer={
        <div className="oa-inventory-footer">
          <span className="oa-secondary">
            {dirty ? '有未保存的修改' : '未修改'}
          </span>
          <Space>
            <Button disabled={busy} onClick={close}>
              取消
            </Button>
            <Button type="primary" loading={busy} onClick={save}>
              保存修改
            </Button>
          </Space>
        </div>
      }
    >
      {error && (
        <Alert
          type="error"
          showIcon
          message={error}
          style={{ marginBottom: 20 }}
        />
      )}
      {items.some((r) => r.Legacy) && (
        <Alert
          type="info"
          message="保存后使用共享租售数量，历史订单保留。"
          style={{ marginBottom: 20 }}
        />
      )}
      {items.length > 1 ? (
        <>
          <div className="oa-inventory-batch-toolbar">
            <span>批量填入</span>
            <Select
              disabled={busy}
              aria-label="批量修改字段"
              value={field}
              onChange={setField}
              options={[
                { value: 'Quantity', label: '对外租售数量' },
                { value: 'RentalPrice', label: '日租金（元）' },
                { value: 'Deposit', label: '押金（元）' },
              ]}
            />
            <InputNumber
              disabled={busy}
              min={0}
              aria-label="批量填写数值"
              value={value}
              precision={field === 'Quantity' ? 0 : 2}
              onChange={setValue}
            />
            <Button
              disabled={busy || value === null}
              onClick={() =>
                setItems((old) =>
                  old.map((r) => ({
                    ...r,
                    [field]:
                      field === 'Quantity'
                        ? Math.floor(value!)
                        : Math.round(value! * 100),
                  })),
                )
              }
            >
              应用到所选
            </Button>
          </div>
          <div className="oa-inventory-batch-toolbar">
            <span>批量开关</span>
            {[
              ['开启出租', true, 'RentalEnabled'],
              ['关闭出租', false, 'RentalEnabled'],
              ['开启出售', true, 'PurchaseEnabled'],
              ['关闭出售', false, 'PurchaseEnabled'],
            ].map(([label, enabled, key]) => (
              <Button
                disabled={busy}
                key={String(label)}
                onClick={() =>
                  setItems((old) =>
                    old.map((r) => ({
                      ...r,
                      [String(key)]: enabled,
                      ...(!enabled ? { BuyoutEnabled: false } : {}),
                    })),
                  )
                }
              >
                {label}
              </Button>
            ))}
          </div>
          <Table<Row>
            pagination={false}
            rowKey="BoardGameID"
            dataSource={items}
            expandable={{
              expandedRowRender: (r) => extraFields(r),
              rowExpandable: () => true,
            }}
            columns={[
              {
                title: '桌游',
                width: 230,
                render: (_, r) => (
                  <>
                    <strong>{r.Name}</strong>
                    <div>{occupancy(r)}</div>
                  </>
                ),
              },
              {
                title: '总数量',
                width: 120,
                render: (_, r) => (
                  <InputNumber
                    disabled={busy}
                    aria-label={`${r.Name}总数量`}
                    min={r.Quantity}
                    max={100000}
                    precision={0}
                    value={r.Total}
                    onChange={(v) => update(r.BoardGameID, { Total: v || 0 })}
                  />
                ),
              },
              {
                title: '对外数量',
                width: 140,
                render: (_, r) => (
                  <>
                    <InputNumber
                      disabled={busy}
                      aria-label={`${r.Name}对外租售数量`}
                      min={r.Reserved + r.Out + r.Held}
                      max={r.Total}
                      precision={0}
                      value={r.Quantity}
                      onChange={(v) =>
                        update(r.BoardGameID, { Quantity: v || 0 })
                      }
                    />
                    <div className="oa-secondary">
                      留店 {Math.max(0, r.Total - r.Quantity)} 盒
                    </div>
                  </>
                ),
              },
              {
                title: '出租 / 日租金',
                width: 200,
                render: (_, r) => (
                  <Space direction="vertical">
                    <Switch
                      aria-label={`${r.Name}允许出租`}
                      disabled={busy}
                      checked={r.RentalEnabled}
                      onChange={(enabled) =>
                        update(r.BoardGameID, {
                          RentalEnabled: enabled,
                          ...(!enabled ? { BuyoutEnabled: false } : {}),
                        })
                      }
                    />
                    {r.RentalEnabled && currency(r, 'RentalPrice')}
                  </Space>
                ),
              },
              {
                title: '出售 / 售价',
                width: 200,
                render: (_, r) => (
                  <Space direction="vertical">
                    <Switch
                      aria-label={`${r.Name}允许出售`}
                      disabled={busy}
                      checked={r.PurchaseEnabled}
                      onChange={(enabled) =>
                        update(r.BoardGameID, {
                          PurchaseEnabled: enabled,
                          ...(!enabled ? { BuyoutEnabled: false } : {}),
                        })
                      }
                    />
                    {r.PurchaseEnabled && currency(r, 'PurchasePrice')}
                  </Space>
                ),
              },
              {
                title: '押金',
                width: 160,
                render: (_, r) => currency(r, 'Deposit'),
              },
            ]}
          />
          <p className="oa-secondary" style={{ marginTop: 16 }}>
            展开桌游可编辑品相、配件说明与租后购买。全部修改一起保存。
          </p>
        </>
      ) : (
        items.map((r) => (
          <Form layout="vertical" key={r.BoardGameID}>
            <section className="oa-inventory-section">
              <h3>数量分配</h3>
              <GridRow gutter={24}>
                <Col span={12}>
                  <Form.Item label="总数量">
                    <InputNumber
                      disabled={busy}
                      aria-label="总数量"
                      min={r.Quantity}
                      max={100000}
                      precision={0}
                      value={r.Total}
                      onChange={(v) => update(r.BoardGameID, { Total: v || 0 })}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="对外租售数量">
                    <InputNumber
                      disabled={busy}
                      aria-label="对外租售数量"
                      min={r.Reserved + r.Out + r.Held}
                      max={r.Total}
                      precision={0}
                      value={r.Quantity}
                      onChange={(v) =>
                        update(r.BoardGameID, { Quantity: v || 0 })
                      }
                    />
                  </Form.Item>
                </Col>
              </GridRow>
              <div className="oa-inventory-balance">
                <strong>留店使用 {Math.max(0, r.Total - r.Quantity)} 盒</strong>
                <span>
                  当前可接单{' '}
                  {Math.max(0, r.Quantity - r.Reserved - r.Out - r.Held)} 盒
                </span>
              </div>
              <Collapse
                ghost
                size="small"
                items={[
                  {
                    key: 'occupancy',
                    label: `已占用 ${r.Reserved + r.Out + r.Held} 盒`,
                    children: occupancy(r),
                  },
                ]}
              />
            </section>
            <section className="oa-inventory-section">
              <div className="oa-inventory-option">
                <h3>出租</h3>
                <Switch
                  aria-label="允许出租"
                  disabled={busy}
                  checked={r.RentalEnabled}
                  onChange={(enabled) =>
                    update(r.BoardGameID, {
                      RentalEnabled: enabled,
                      ...(!enabled ? { BuyoutEnabled: false } : {}),
                    })
                  }
                />
              </div>
              {r.RentalEnabled && (
                <GridRow gutter={24}>
                  <Col span={12}>
                    <Form.Item label="日租金">
                      {currency(r, 'RentalPrice')}
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="押金">{currency(r, 'Deposit')}</Form.Item>
                  </Col>
                </GridRow>
              )}
            </section>
            <section className="oa-inventory-section">
              <div className="oa-inventory-option">
                <h3>出售</h3>
                <Switch
                  aria-label="允许出售"
                  disabled={busy}
                  checked={r.PurchaseEnabled}
                  onChange={(enabled) =>
                    update(r.BoardGameID, {
                      PurchaseEnabled: enabled,
                      ...(!enabled ? { BuyoutEnabled: false } : {}),
                    })
                  }
                />
              </div>
              {r.PurchaseEnabled && (
                <Form.Item label="售价">
                  {currency(r, 'PurchasePrice')}
                </Form.Item>
              )}
              {r.PurchaseEnabled && extraFields(r)}
            </section>
          </Form>
        ))
      )}
    </Drawer>
  );
}
