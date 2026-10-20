import { Table } from '@/components/AdaptiveTable';
import { queryUsers } from '@/services/users';
import {
  Alert,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Space,
  Typography,
  message,
} from 'antd';
import { useEffect, useRef, useState } from 'react';

export default function UserPicker({
  open,
  value,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  value: API.UserInfo[];
  onCancel: () => void;
  onConfirm: (users: API.UserInfo[]) => void;
}) {
  const [form] = Form.useForm();
  const [selected, setSelected] = useState<Map<number, API.UserInfo>>(
    new Map(),
  );
  const [rows, setRows] = useState<API.UserInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<API.QueryUsersParams>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [reload, setReload] = useState(0);
  const sequence = useRef(0);
  useEffect(() => {
    if (open) {
      setSelected(new Map(value.map((user) => [user.Id, user])));
      form.resetFields();
      setFilters({});
      setPage(1);
    }
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const current = ++sequence.current;
    setLoading(true);
    setError(undefined);
    queryUsers({ ...filters, Current: page, PageSize: 10 })
      .then((response) => {
        if (current !== sequence.current) return;
        if (response.Code !== 0 || !response.Data)
          throw new Error(response.Message || '用户加载失败');
        setRows(response.Data.Items);
        setTotal(response.Data.Total);
      })
      .catch((err) => {
        if (current !== sequence.current) return;
        setRows([]);
        setTotal(0);
        const data = err?.response?.data;
        setError(
          data?.ErrorId
            ? `用户加载失败，错误编号：${data.ErrorId}`
            : data?.Message ||
                (err?.response || err?.request ? undefined : err.message) ||
                '用户加载失败，请重试',
        );
      })
      .finally(() => {
        if (current === sequence.current) setLoading(false);
      });
    return () => {
      sequence.current++;
    };
  }, [open, filters, page, reload]);

  const change = (users: API.UserInfo[], checked: boolean) => {
    setSelected((previous) => {
      const next = new Map(previous);
      users.forEach((user) => {
        if (checked && next.size < 100) next.set(user.Id, user);
        if (!checked) next.delete(user.Id);
      });
      return next;
    });
  };
  return (
    <Modal
      title="选择开通用户"
      open={open}
      width={900}
      okText={`确认选择（${selected.size}）`}
      okButtonProps={{ disabled: !selected.size }}
      onCancel={onCancel}
      onOk={() => onConfirm(Array.from(selected.values()))}
      maskClosable={false}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Form
          form={form}
          layout="inline"
          onFinish={(values) => {
            setPage(1);
            setFilters({
              Id: values.Id || undefined,
              NickName: values.NickName?.trim() || undefined,
              PhoneNumber: values.PhoneNumber?.trim() || undefined,
            });
          }}
          style={{ rowGap: 12 }}
        >
          <Form.Item name="Id" label="用户ID">
            <InputNumber
              min={1}
              precision={0}
              placeholder="精确查询"
              style={{ width: 125 }}
            />
          </Form.Item>
          <Form.Item name="NickName" label="昵称">
            <Input placeholder="搜索昵称" allowClear style={{ width: 150 }} />
          </Form.Item>
          <Form.Item name="PhoneNumber" label="手机号">
            <Input placeholder="完整手机号" allowClear style={{ width: 155 }} />
          </Form.Item>
          <Space>
            <Button htmlType="submit" type="primary">
              查询
            </Button>
            <Button
              onClick={() => {
                form.resetFields();
                setFilters({});
                setPage(1);
              }}
            >
              重置
            </Button>
          </Space>
        </Form>
        <Space>
          <Typography.Text>
            已选 {selected.size} 位用户，可跨页选择，最多 100 位
          </Typography.Text>
          <Button
            type="link"
            disabled={!selected.size}
            onClick={() => setSelected(new Map())}
          >
            清空已选
          </Button>
        </Space>
        {error && (
          <Alert
            showIcon
            type="error"
            message={error}
            action={
              <Button onClick={() => setReload((v) => v + 1)}>重试</Button>
            }
          />
        )}
        <Table<API.UserInfo>
          rowKey="Id"
          loading={loading}
          dataSource={rows}
          rowSelection={{
            selectedRowKeys: Array.from(selected.keys()),
            preserveSelectedRowKeys: true,
            getCheckboxProps: (row) => ({
              disabled:
                !row.OpenId || (selected.size >= 100 && !selected.has(row.Id)),
            }),
            onSelect: (row, checked) => change([row], checked),
            onSelectMultiple: (checked, _, changedRows) =>
              change(changedRows, checked),
            onSelectAll: (checked, _, changedRows) => {
              if (
                checked &&
                changedRows.filter((row) => !selected.has(row.Id)).length +
                  selected.size >
                  100
              )
                message.info('最多选择 100 位用户');
              change(changedRows, checked);
            },
          }}
          columns={[
            { title: '用户ID', dataIndex: 'Id', width: 90 },
            {
              title: '昵称',
              dataIndex: 'NickName',
              width: 190,
              render: (value) => value || '未设置昵称',
            },
            {
              title: '手机号',
              dataIndex: 'PhoneNumber',
              width: 150,
              render: (value) => value || '未绑定',
            },
            {
              title: '月卡到期',
              dataIndex: 'MonthCardExpire',
              width: 180,
              render: (value) => value || '尚未开通',
            },
          ]}
          pagination={{
            current: page,
            pageSize: 10,
            total,
            showSizeChanger: false,
            showTotal: (count) => `共 ${count} 位用户`,
            onChange: setPage,
          }}
        />
      </Space>
    </Modal>
  );
}
