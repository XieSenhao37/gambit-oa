import { ProTable } from '@/components/AdaptiveTable';
import {
  createGameLibraryItem,
  deleteGameLibraryItem,
  queryGameLibrary,
  updateGameLibraryItem,
  uploadGameImage,
} from '@/services/games';
import { cosThumb } from '@/utils/cosImage';
import { compressGameImage, runGameImageUpload } from '@/utils/gameImage';
import { PlusOutlined, UploadOutlined } from '@ant-design/icons';
import {
  PageContainer,
  type ActionType,
  type ProColumns,
} from '@ant-design/pro-components';
import {
  Button,
  Drawer,
  Form,
  Image,
  Input,
  InputNumber,
  message,
  Popconfirm,
  Select,
  Space,
  Tag,
  Typography,
  Upload,
  type UploadFile,
} from 'antd';
import { useRef, useState } from 'react';

const { Paragraph } = Typography;

const toNumberList = (items?: (string | number)[]) =>
  (items || [])
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item))
    .sort((a, b) => a - b);

const toStringList = (items?: string[]) =>
  (items || []).map((item) => String(item).trim()).filter(Boolean);

const defaultValues = {
  GstoneScore: 0,
  GstoneRank: 0,
  SupportedPlayers: [1, 2, 3, 4],
  RecommendedPlayers: [2, 3, 4],
  Complexity: 5,
  PlayTime: 30,
  SetupTime: '',
  LanguageLevel: '',
  PictureList: [],
  Designer: [],
  Publisher: [],
  PublishLanguage: [],
  PublishYear: 0,
  Categories: [],
  Modes: [],
  Mechanisms: [],
  Themes: [],
  TableRequirement: '',
  Portability: '',
  SuitableAge: '',
};

const GameLibraryPage: React.FC = () => {
  const actionRef = useRef<ActionType>();
  const [form] = Form.useForm();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<API.BoardGame | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submitLock = useRef(false);
  const [coverFileList, setCoverFileList] = useState<UploadFile[]>([]);
  const [pictureFileList, setPictureFileList] = useState<UploadFile[]>([]);

  const openCreate = () => {
    setEditing(null);
    setCoverFileList([]);
    setPictureFileList([]);
    form.resetFields();
    form.setFieldsValue(defaultValues);
    setDrawerOpen(true);
  };

  const openEdit = (record: API.BoardGame) => {
    setEditing(record);
    setCoverFileList(
      record.CoverUrl
        ? [
            {
              uid: 'cover-existing',
              name: '封面图',
              status: 'done',
              url: record.CoverUrl,
              thumbUrl: cosThumb(record.CoverUrl, 'sm'),
            } as UploadFile,
          ]
        : [],
    );
    setPictureFileList(
      (record.PictureList || []).map(
        (url, index) =>
          ({
            uid: `picture-existing-${index}`,
            name: `详情图${index + 1}`,
            status: 'done',
            url,
            thumbUrl: cosThumb(url, 'sm'),
          } as UploadFile),
      ),
    );
    form.resetFields();
    form.setFieldsValue({
      ...defaultValues,
      ...record,
      SupportedPlayers: record.SupportedPlayers || [],
      RecommendedPlayers: record.RecommendedPlayers || [],
      Designer: record.Designer || [],
      Publisher: record.Publisher || [],
      PublishLanguage: record.PublishLanguage || [],
      Categories: record.Categories || [],
      Modes: record.Modes || [],
      Mechanisms: record.Mechanisms || [],
      Themes: record.Themes || [],
    });
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditing(null);
    setCoverFileList([]);
    setPictureFileList([]);
    form.resetFields();
  };

  const buildFormData = (values: any) => {
    const formData = new FormData();
    const appendValue = (
      key: string,
      value: string | number | string[] | number[],
    ) => {
      formData.append(
        key,
        Array.isArray(value) ? JSON.stringify(value) : String(value ?? ''),
      );
    };

    appendValue('Name', values.Name?.trim());
    appendValue('Description', values.Description?.trim());
    appendValue('GstoneScore', Number(values.GstoneScore || 0));
    appendValue('GstoneRank', Number(values.GstoneRank || 0));
    appendValue('SupportedPlayers', toNumberList(values.SupportedPlayers));
    appendValue('RecommendedPlayers', toNumberList(values.RecommendedPlayers));
    appendValue('Complexity', Number(values.Complexity || 1));
    appendValue('PlayTime', Number(values.PlayTime || 0));
    appendValue('SetupTime', values.SetupTime?.trim() || '');
    appendValue('LanguageLevel', values.LanguageLevel?.trim() || '');
    appendValue('Designer', toStringList(values.Designer));
    appendValue('Publisher', toStringList(values.Publisher));
    appendValue('PublishLanguage', toStringList(values.PublishLanguage));
    appendValue('PublishYear', Number(values.PublishYear || 0));
    appendValue('Categories', toStringList(values.Categories));
    appendValue('Modes', toStringList(values.Modes));
    appendValue('Mechanisms', toStringList(values.Mechanisms));
    appendValue('Themes', toStringList(values.Themes));
    appendValue('TableRequirement', values.TableRequirement?.trim() || '');
    appendValue('Portability', values.Portability?.trim() || '');
    appendValue('SuitableAge', values.SuitableAge?.trim() || '');

    const coverUrl = coverFileList.find(
      (file) => file.status === 'done' && file.url,
    )?.url;
    if (coverUrl) formData.append('CoverUrl', coverUrl);
    appendValue(
      'PictureList',
      pictureFileList.map((file) => file.url as string),
    );
    return formData;
  };

  const imagesReady = [...coverFileList, ...pictureFileList].every(
    (file) => file.status === 'done' && !!file.url,
  );
  const uploadImage = (options: any) => {
    const controller = new AbortController();
    runGameImageUpload(async () => {
      if (controller.signal.aborted) return;
      options.onProgress?.({ percent: 1 });
      const compressed = await compressGameImage(options.file as File);
      if (controller.signal.aborted) return;
      options.onProgress?.({ percent: 10 });
      const response = await uploadGameImage(
        compressed,
        controller.signal,
        (percent) => options.onProgress?.({ percent }),
      );
      if (controller.signal.aborted) return;
      if (response.Code !== 0 || !response.Data?.Url)
        throw new Error(response.Message || '图片上传失败');
      options.onSuccess?.(response);
    }).catch((error) => {
      if (!controller.signal.aborted) options.onError?.(error);
    });
    return { abort: () => controller.abort() };
  };
  const validateImage = (file: File) => {
    if (
      !/\.(jpe?g|png|webp|gif)$/i.test(file.name) ||
      file.size > 5 * 1024 * 1024
    ) {
      message.error('请选择 jpg/png/webp/gif 图片，单张不超过 5MB');
      return Upload.LIST_IGNORE;
    }
    return true;
  };
  const uploadedList = (files: UploadFile[]) =>
    files.map((file) => ({
      ...file,
      url: file.response?.Data?.Url || file.url,
    }));

  const handleSubmit = async () => {
    if (submitLock.current) return;
    if (!imagesReady) {
      message.warning('请等待图片上传完成；失败的图片请移除后重新上传');
      return;
    }
    submitLock.current = true;
    try {
      const values = await form.validateFields();
      const hasCover = coverFileList.some(
        (file) => file.status === 'done' && !!file.url,
      );
      if (!hasCover) {
        message.error('请上传封面图');
        return;
      }
      setSubmitting(true);
      const payload = buildFormData(values);
      const response = editing
        ? await updateGameLibraryItem(editing.Id, payload)
        : await createGameLibraryItem(payload);
      if (response.Code === 0) {
        message.success(editing ? '更新成功' : '创建成功');
        closeDrawer();
        actionRef.current?.reload();
      } else {
        message.error(response.Message || response.Msg || '保存失败');
      }
    } catch (error: any) {
      // 网络/HTTP 错误由统一处理器提示，避免叠加两个报错。
      if (!error?.errorFields && !error?.request && !error?.response) {
        message.error(error?.message || '保存失败');
      }
    } finally {
      submitLock.current = false;
      setSubmitting(false);
    }
  };

  const handleDelete = async (record: API.BoardGame) => {
    const response = await deleteGameLibraryItem(record.Id);
    if (response.Code === 0) {
      message.success('删除成功');
      actionRef.current?.reload();
    } else {
      message.error(response.Message || response.Msg || '删除失败');
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
      width: 100,
      search: false,
      render: (_, record) => (
        <Image
          src={record.CoverUrl}
          preview={{ src: cosThumb(record.CoverUrl, 'lg') }}
          alt={record.Name}
          width={72}
          height={72}
          style={{ objectFit: 'cover' }}
        />
      ),
    },
    {
      title: '名称',
      dataIndex: 'Name',
      width: 180,
    },
    {
      title: '评分',
      dataIndex: 'GstoneScore',
      width: 80,
      search: false,
    },
    {
      title: '排名',
      dataIndex: 'GstoneRank',
      width: 80,
      search: false,
    },
    {
      title: '人数',
      dataIndex: 'SupportedPlayers',
      width: 140,
      search: false,
      render: (_, record) => (
        <>
          {record.SupportedPlayers?.map((num) => (
            <Tag key={num}>{num}人</Tag>
          ))}
        </>
      ),
    },
    {
      title: '难度',
      dataIndex: 'Complexity',
      width: 80,
      search: false,
      render: (_, record) =>
        record.Complexity ? `${record.Complexity}/10` : '-',
    },
    {
      title: '时长',
      dataIndex: 'PlayTime',
      width: 90,
      search: false,
      render: (_, record) => (record.PlayTime ? `${record.PlayTime}分钟` : '-'),
    },
    {
      title: '类别',
      dataIndex: 'Categories',
      width: 180,
      search: false,
      render: (_, record) => (
        <>
          {record.Categories?.map((category) => (
            <Tag key={category}>{category}</Tag>
          ))}
        </>
      ),
    },
    {
      title: '简介',
      dataIndex: 'Description',
      width: 280,
      search: false,
      ellipsis: true,
      render: (_, record) => (
        <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 0 }}>
          {record.Description}
        </Paragraph>
      ),
    },
    {
      title: '操作',
      width: 150,
      key: 'action',
      fixed: 'right',
      search: false,
      render: (_, record) => (
        <Space>
          <Button type="link" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确认删除该全局桌游资料？"
            description="如果该桌游仍存在门店库存，后端会阻止删除。"
            onConfirm={() => handleDelete(record)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="link" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      <ProTable<API.BoardGame>
        headerTitle="桌游信息库"
        actionRef={actionRef}
        rowKey="Id"
        scroll={{ x: 1400 }}
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
            新增桌游
          </Button>,
        ]}
        request={async (params) => {
          const response = await queryGameLibrary({
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
          return { data: [], total: 0, success: false };
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
        title={editing ? `编辑桌游 #${editing.Id}` : '新增桌游'}
        width={720}
        open={drawerOpen}
        onClose={() => {
          if (!submitLock.current) closeDrawer();
        }}
        closable={!submitting}
        maskClosable={!submitting}
        destroyOnClose
        extra={
          <Space>
            <Button disabled={submitting} onClick={closeDrawer}>
              取消
            </Button>
            <Button
              type="primary"
              loading={submitting}
              disabled={!imagesReady}
              onClick={handleSubmit}
            >
              {submitting ? '保存中' : '保存'}
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical" disabled={submitting}>
          <Form.Item
            label="名称"
            name="Name"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input maxLength={255} placeholder="如：璀璨宝石" />
          </Form.Item>
          <Form.Item label="封面图" required>
            <Upload
              listType="picture-card"
              maxCount={1}
              fileList={coverFileList}
              beforeUpload={validateImage}
              customRequest={uploadImage}
              onChange={({ fileList: next }) =>
                setCoverFileList(uploadedList(next))
              }
              onRemove={() => {
                setCoverFileList([]);
                return true;
              }}
              accept="image/jpeg,image/png,image/webp,image/gif"
            >
              {coverFileList.length === 0 && (
                <div>
                  <UploadOutlined />
                  <div style={{ marginTop: 8 }}>上传封面</div>
                </div>
              )}
            </Upload>
            <div style={{ color: '#999', fontSize: 12 }}>
              单张最大 5MB，选择后自动压缩并上传；上传完成后即可保存
            </div>
          </Form.Item>
          <Form.Item
            label="简介"
            name="Description"
            rules={[{ required: true, message: '请输入简介' }]}
          >
            <Input.TextArea
              rows={4}
              placeholder="桌游简介，支持简单文本/HTML"
            />
          </Form.Item>

          <Space size="middle" style={{ width: '100%' }} align="start">
            <Form.Item label="评分" name="GstoneScore">
              <InputNumber min={0} max={10} precision={1} step={0.1} />
            </Form.Item>
            <Form.Item label="排名" name="GstoneRank">
              <InputNumber min={0} precision={0} />
            </Form.Item>
            <Form.Item label="难度（1-10）" name="Complexity">
              <InputNumber min={1} max={10} precision={0} />
            </Form.Item>
            <Form.Item label="时长（分钟）" name="PlayTime">
              <InputNumber min={0} precision={0} />
            </Form.Item>
            <Form.Item label="出版年份" name="PublishYear">
              <InputNumber min={0} precision={0} />
            </Form.Item>
          </Space>

          <Form.Item label="支持人数" name="SupportedPlayers">
            <Select
              mode="tags"
              tokenSeparators={[',', '，', ' ']}
              placeholder="输入数字后回车，如 2"
            />
          </Form.Item>
          <Form.Item label="推荐人数" name="RecommendedPlayers">
            <Select
              mode="tags"
              tokenSeparators={[',', '，', ' ']}
              placeholder="输入数字后回车，如 3"
            />
          </Form.Item>
          <Form.Item label="类别" name="Categories">
            <Select
              mode="tags"
              tokenSeparators={[',', '，']}
              placeholder="如：策略、家庭"
            />
          </Form.Item>
          <Form.Item label="模式" name="Modes">
            <Select
              mode="tags"
              tokenSeparators={[',', '，']}
              placeholder="如：合作、对抗"
            />
          </Form.Item>
          <Form.Item label="机制" name="Mechanisms">
            <Select
              mode="tags"
              tokenSeparators={[',', '，']}
              placeholder="如：牌库构筑、工人放置"
            />
          </Form.Item>
          <Form.Item label="主题" name="Themes">
            <Select
              mode="tags"
              tokenSeparators={[',', '，']}
              placeholder="如：奇幻、科幻"
            />
          </Form.Item>
          <Form.Item label="详情图片">
            <Upload
              listType="picture-card"
              multiple
              fileList={pictureFileList}
              beforeUpload={validateImage}
              customRequest={uploadImage}
              onChange={({ fileList: next }) =>
                setPictureFileList(uploadedList(next))
              }
              accept="image/jpeg,image/png,image/webp,image/gif"
            >
              <div>
                <UploadOutlined />
                <div style={{ marginTop: 8 }}>上传图片</div>
              </div>
            </Upload>
            <div style={{ color: '#999', fontSize: 12 }}>
              选择后自动上传，可同时填写其他资料；上传失败请移除后重新选择
            </div>
          </Form.Item>
          <Form.Item label="设计师" name="Designer">
            <Select
              mode="tags"
              tokenSeparators={[',', '，']}
              placeholder="输入后回车"
            />
          </Form.Item>
          <Form.Item label="出版商" name="Publisher">
            <Select
              mode="tags"
              tokenSeparators={[',', '，']}
              placeholder="输入后回车"
            />
          </Form.Item>
          <Form.Item label="出版语言" name="PublishLanguage">
            <Select
              mode="tags"
              tokenSeparators={[',', '，']}
              placeholder="如：中文、英文"
            />
          </Form.Item>

          <Space size="middle" style={{ width: '100%' }} align="start">
            <Form.Item label="设置时长" name="SetupTime">
              <Input maxLength={50} placeholder="如：5分钟" />
            </Form.Item>
            <Form.Item label="语言要求" name="LanguageLevel">
              <Input maxLength={50} placeholder="如：弱文字依赖" />
            </Form.Item>
            <Form.Item label="桌面要求" name="TableRequirement">
              <Input maxLength={50} placeholder="如：中桌" />
            </Form.Item>
          </Space>

          <Space size="middle" style={{ width: '100%' }} align="start">
            <Form.Item label="便携程度" name="Portability">
              <Input maxLength={50} placeholder="如：便携" />
            </Form.Item>
            <Form.Item label="适合年龄" name="SuitableAge">
              <Input maxLength={50} placeholder="如：8+" />
            </Form.Item>
          </Space>
        </Form>
      </Drawer>
    </PageContainer>
  );
};

export default GameLibraryPage;
