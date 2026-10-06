import { ProTable } from '@/components/AdaptiveTable';
import {
  addGameInventory,
  deleteGameInventory,
  getGameLibraryItem,
  queryGameLibrary,
  queryGames,
  updateGameInventory,
} from '@/services/games';
import { PlusOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { PageContainer } from '@ant-design/pro-components';
import {
  Button,
  Descriptions,
  Drawer,
  Form,
  Image,
  InputNumber,
  message,
  Popconfirm,
  Select,
  Space,
  Tag,
  Typography,
} from 'antd';
import { useRef, useState } from 'react';

const { Paragraph } = Typography;

const GameList: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [form] = Form.useForm();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<API.BoardGame | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [libraryOptions, setLibraryOptions] = useState<API.BoardGame[]>([]);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState<API.BoardGame | null>(null);

  const loadLibraryOptions = async () => {
    const response = await queryGameLibrary({ PageNum: 1, PageSize: 1000 });
    if (response.Code === 0) {
      setLibraryOptions(response.Data?.Items || []);
    }
  };

  const openCreate = async () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ Count: 1 });
    setDrawerOpen(true);
    await loadLibraryOptions();
  };

  const openEdit = (record: API.BoardGame) => {
    setEditing(record);
    form.resetFields();
    form.setFieldsValue({ Count: record.Count });
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditing(null);
    form.resetFields();
  };

  const handleDelete = async (id: number) => {
    try {
      const response = await deleteGameInventory(id);
      if (response.Code === 0) {
        message.success('已从当前门店库存移除');
        actionRef.current?.reload();
      } else {
        message.error(response.Message || response.Msg || '移除失败');
      }
    } catch (error: any) {
      message.error(error?.Msg || '移除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const count = Number(values.Count || 0);
      const response = editing
        ? await updateGameInventory(editing.Id, { Count: count })
        : await addGameInventory({
            BoardGameId: Number(values.BoardGameId),
            Count: count,
          });
      if (response.Code === 0) {
        message.success(editing ? '库存数量已更新' : '已添加到当前门店库存');
        closeDrawer();
        actionRef.current?.reload();
      } else {
        message.error(response.Message || response.Msg || '保存失败');
      }
    } catch (error: any) {
      if (!error?.errorFields) {
        message.error(error?.message || '保存失败');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openDetail = async (record: API.BoardGame) => {
    setDetailOpen(true);
    setDetailLoading(true);
    setDetail(null);
    try {
      const response = await getGameLibraryItem(record.Id);
      if (response.Code === 0 && response.Data) {
        setDetail(response.Data);
      } else {
        message.error(response.Message || response.Msg || '加载详情失败');
      }
    } finally {
      setDetailLoading(false);
    }
  };

  const columns: ProColumns<API.BoardGame>[] = [
    {
      title: 'ID',
      dataIndex: 'Id',
      width: 80,
      search: false,
    },
    {
      title: '封面',
      dataIndex: 'CoverUrl',
      width: 120,
      search: false,
      render: (_, record) => (
        <Image
          src={record.CoverUrl}
          alt={record.Name}
          width={80}
          height={80}
          style={{ objectFit: 'cover' }}
          fallback="data:image/png;base64,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"
        />
      ),
    },
    {
      title: '名称',
      dataIndex: 'Name',
      width: 220,
    },
    {
      title: '数量',
      dataIndex: 'Count',
      width: 80,
      search: false,
    },
    {
      title: '操作',
      width: 220,
      key: 'action',
      fixed: 'right',
      search: false,
      render: (_, record) => (
        <Space>
          <Button type="link" onClick={() => openDetail(record)}>
            详情
          </Button>
          <Button type="link" onClick={() => openEdit(record)}>
            改数量
          </Button>
          <Popconfirm
            title="确定从当前门店库存移除？"
            onConfirm={() => handleDelete(record.Id)}
            okText="移除"
            cancelText="取消"
          >
            <Button type="link" danger>
              移除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      <ProTable<API.BoardGame>
        headerTitle="门店桌游库存"
        actionRef={actionRef}
        rowKey="Id"
        scroll={{ x: 760 }}
        search={{
          labelWidth: 120,
          defaultCollapsed: false,
        }}
        toolBarRender={() => [
          <Button
            key="create"
            type="primary"
            icon={<PlusOutlined />}
            onClick={openCreate}
          >
            从信息库添加
          </Button>,
        ]}
        request={async (params) => {
          const response = await queryGames({
            PageNum: params.current,
            PageSize: params.pageSize,
            Keyword: params.Name,
          });

          if (response.Code === 0) {
            return {
              data: response.Data?.Items || [],
              total: response.Data?.Total || 0,
              success: true,
            };
          }
          return {
            data: [],
            total: 0,
            success: false,
          };
        }}
        columns={columns}
        pagination={{
          showQuickJumper: true,
          showSizeChanger: true,
          defaultPageSize: 10,
          pageSizeOptions: ['10', '20', '50', '100'],
        }}
      />

      <Drawer
        title={editing ? `修改库存数量 #${editing.Id}` : '从桌游信息库添加'}
        width={420}
        open={drawerOpen}
        onClose={closeDrawer}
        destroyOnClose
        extra={
          <Space>
            <Button onClick={closeDrawer}>取消</Button>
            <Button type="primary" loading={submitting} onClick={handleSubmit}>
              保存
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          {!editing && (
            <Form.Item
              label="选择桌游"
              name="BoardGameId"
              rules={[{ required: true, message: '请选择桌游' }]}
            >
              <Select
                showSearch
                placeholder="从全局桌游信息库选择"
                optionFilterProp="label"
                options={libraryOptions.map((game) => ({
                  label: `${game.Id} - ${game.Name}`,
                  value: game.Id,
                }))}
              />
            </Form.Item>
          )}
          <Form.Item
            label="当前门店数量"
            name="Count"
            rules={[{ required: true, message: '请输入数量' }]}
          >
            <InputNumber min={0} precision={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Drawer>

      <Drawer
        title={detail ? `桌游详情 #${detail.Id}` : '桌游详情'}
        width={720}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        loading={detailLoading}
      >
        {detail && (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Image src={detail.CoverUrl} alt={detail.Name} width={160} />
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="名称" span={2}>
                {detail.Name}
              </Descriptions.Item>
              <Descriptions.Item label="评分">
                {detail.GstoneScore ?? '-'}
              </Descriptions.Item>
              <Descriptions.Item label="排名">
                {detail.GstoneRank ?? '-'}
              </Descriptions.Item>
              <Descriptions.Item label="人数" span={2}>
                {detail.SupportedPlayers?.map((num) => (
                  <Tag key={num}>{num}人</Tag>
                ))}
              </Descriptions.Item>
              <Descriptions.Item label="难度">
                {detail.Complexity}/10
              </Descriptions.Item>
              <Descriptions.Item label="时长">
                {detail.PlayTime}分钟
              </Descriptions.Item>
              <Descriptions.Item label="类别" span={2}>
                {detail.Categories?.map((category) => (
                  <Tag key={category}>{category}</Tag>
                ))}
              </Descriptions.Item>
              <Descriptions.Item label="机制" span={2}>
                {detail.Mechanisms?.map((item) => (
                  <Tag key={item}>{item}</Tag>
                ))}
              </Descriptions.Item>
              <Descriptions.Item label="简介" span={2}>
                <Paragraph style={{ marginBottom: 0 }}>
                  {detail.Description}
                </Paragraph>
              </Descriptions.Item>
            </Descriptions>
          </Space>
        )}
      </Drawer>
    </PageContainer>
  );
};

export default GameList;
