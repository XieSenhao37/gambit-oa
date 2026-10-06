import { settlementPost } from '@/services/settlement';
import { createRequestKey } from '@/utils/requestKey';
import {
  Alert,
  Button,
  Checkbox,
  Form,
  Input,
  Modal,
  Space,
  Steps,
  Typography,
  message,
} from 'antd';
import { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
const yuan = (amount: number) => `¥${(Math.abs(amount) / 100).toFixed(2)}`;
export default function ReportActions({
  month,
  overview,
  headquarters,
  allStores,
  ended,
  selectAllStores,
  actionContainer,
  refresh,
}: any) {
  const report = overview.Report;
  const blockedReason =
    overview.GenerationBlockedReason ||
    (!ended ? '自然月尚未结束，请在次月 1 日起生成报表。' : '');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false),
    [confirming, setConfirming] = useState(false);
  const [form] = Form.useForm();
  const generationKey = useRef<{ month: string; key: string }>();
  const pending = useRef(false);
  const run = async (action: () => Promise<unknown>) => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setActionError('');
    try {
      await action();
      refresh();
    } catch (error: any) {
      setActionError(
        error.response?.data?.Message ||
          error.message ||
          '操作失败，请重试；本次没有确认结算。',
      );
      throw error;
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  const generate = () =>
    run(async () => {
      if (generationKey.current?.month !== month)
        generationKey.current = { month, key: createRequestKey() };
      await settlementPost('prepare', {
        Month: month,
        RequestKey: generationKey.current!.key,
      });
      generationKey.current = undefined;
      message.success('报表已生成，尚未结算');
    });
  const stores = (overview.Totals || []).filter(
    (t: any) => t.StoreId && t.amount,
  );
  const actions = (
    <Space wrap>
      {headquarters && !allStores && (
        <Button type="primary" onClick={selectAllStores}>
          切换总部汇总，办理结算
        </Button>
      )}
      {headquarters && allStores && (
        <Space wrap>
          {!report && (
            <Button
              type="primary"
              loading={busy}
              disabled={!!blockedReason || overview.Status === 'locked'}
              onClick={() => {
                void generate().catch(() => {});
              }}
            >
              生成结算报表
            </Button>
          )}
          {report?.Status === 'draft' && (
            <>
              <Button
                disabled={busy}
                onClick={() =>
                  Modal.confirm({
                    title: `作废 ${report.Number}？`,
                    content:
                      '仅在尚未按此报表开始收付款时操作。旧版将永久标记作废，不能再确认；修改资料后需重新生成并重新发给各方核对。',
                    okText: '尚未收付款，作废报表',
                    onOk: () =>
                      run(async () => {
                        await settlementPost(`reports/${report.Id}/void`, {
                          Digest: report.Digest,
                          NoTransfersStarted: true,
                        });
                        generationKey.current = undefined;
                      }),
                  })
                }
              >
                作废报表并修改资料
              </Button>
              <Button
                type="primary"
                disabled={busy}
                onClick={() => {
                  form.resetFields();
                  setConfirming(true);
                }}
              >
                收付款完成，确认结算
              </Button>
            </>
          )}
        </Space>
      )}
    </Space>
  );
  return (
    <>
      {actionContainer && createPortal(actions, actionContainer)}
      <Space direction="vertical" style={{ width: '100%' }}>
        {!report && blockedReason && (
          <Alert type="info" showIcon message={blockedReason} />
        )}
        {actionError && (
          <Alert
            type="error"
            showIcon
            message="结算操作未完成"
            description={actionError}
          />
        )}

        <Steps
          size="small"
          current={report?.Status === 'confirmed' ? 4 : report ? 2 : 0}
          items={[
            { title: '补齐资料' },
            { title: '生成报表' },
            { title: '核对并收付款' },
            { title: '确认结算' },
          ]}
        />
        <Typography.Text>
          {report
            ? `${report.Number} · ${
                report.Status === 'confirmed' ? '已结算' : '待确认'
              } · 生成于 ${report.CreatedAt.replace('T', ' ')}`
            : '尚未生成报表。当前业务记录不代表最终结算金额。'}
        </Typography.Text>
        {report?.Status === 'draft' && (
          <Alert
            type="info"
            showIcon
            message="月卡、积分及手续费已计入本版报表，待确认入账"
            description="请导出此版本给各方核对。正数总部付门店，负数门店在本期转回总部；全部收付款完成后再确认。已开始转账请勿作废重算。"
          />
        )}
        {!!report?.Confirmation?.late_entry_ids?.length && (
          <Alert
            type="info"
            showIcon
            message={`报表生成后新增的 ${report.Confirmation.late_entry_ids.length} 笔储值/调整流水已保留到后续月份，不影响本次收付款。`}
          />
        )}
        {!!report?.Confirmation?.late_usage_ids?.length && (
          <Alert
            type="warning"
            showIcon
            message="发现报表生成后补录的历史核销，需总部核对补差"
            description={`核销编号：${report.Confirmation.late_usage_ids.join(
              '、',
            )}。本报表未重新计算，请在月卡分配池核对后补记结算调整。`}
          />
        )}
        <Modal
          title={`确认结算 · ${report?.Number || ''}`}
          open={confirming}
          destroyOnClose
          confirmLoading={busy}
          okText="确认结算并固定记录"
          onCancel={() => {
            if (!busy) setConfirming(false);
          }}
          onOk={async () => {
            const values = await form.validateFields();
            await run(async () => {
              await settlementPost('lock', {
                ReportId: report.Id,
                Digest: report.Digest,
                References: values.References || {},
                AllTransfersCompleted: values.Completed,
              });
              setConfirming(false);
              message.success('结算已确认，报表和已结算区间已固定');
            });
          }}
        >
          <Alert
            type="warning"
            showIcon
            message="请在实际收付款全部完成后操作"
            description="本操作按当前固定报表记账，不重新计算，也不会发起银行转账。确认后不能覆盖原单，更正需补记调整。"
          />
          <Form
            form={form}
            layout="vertical"
            preserve={false}
            style={{ marginTop: 20 }}
          >
            {stores.map((t: any) => (
              <Form.Item
                key={t.StoreId}
                name={['References', String(t.StoreId)]}
                label={`${t.StoreName} · ${
                  t.amount > 0 ? '总部付款' : '转回总部'
                } ${yuan(t.amount)}`}
                rules={[
                  {
                    required: true,
                    whitespace: true,
                    message: '请填写本店实际付款 / 收款凭证',
                  },
                ]}
              >
                <Input
                  maxLength={200}
                  placeholder="银行回单号或可核对的收付款记录"
                />
              </Form.Item>
            ))}
            {!stores.length && (
              <Typography.Paragraph>
                本期各店净额为零，无需转账；仍需核对并确认明细。
              </Typography.Paragraph>
            )}
            <Form.Item
              name="Completed"
              valuePropName="checked"
              rules={[
                {
                  validator: (_, value) =>
                    value === true
                      ? Promise.resolve()
                      : Promise.reject(
                          new Error('请确认各方核对和实际收付款均已完成'),
                        ),
                },
              ]}
            >
              <Checkbox>
                各方已认可此版本，应付门店款及门店应转回总部款均已完成。
              </Checkbox>
            </Form.Item>
          </Form>
        </Modal>
      </Space>
    </>
  );
}
