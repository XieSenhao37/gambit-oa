import { useEffect, useRef, useState } from 'react';
import { PageContainer } from '@ant-design/pro-components';
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  message,
  Select,
  Space,
  Switch,
  Tabs,
  Upload,
  Image,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { request } from '@umijs/max';
import { Table } from '@/components/AdaptiveTable';
import RetailEditor from '@/components/RetailEditor';
import { call, Category, Product } from '@/services/retail';

const required = [{ required: true, message: '请填写' }];

function ProductSortField() {
  return (
    <Form.Item
      name="Sort"
      label="展示顺序"
      extra="各门店共用此顺序。数字越小越靠前，默认 0，可填负数。同值时新品靠前。"
      rules={[
        { required: true, message: '请输入展示顺序' },
        {
          type: 'integer',
          min: Number.MIN_SAFE_INTEGER,
          max: Number.MAX_SAFE_INTEGER,
          message: '请输入有效的整数',
        },
      ]}
    >
      <InputNumber step={1} style={{ width: 160 }} />
    </Form.Item>
  );
}

function ProductSortEditor({
  product,
  close,
  saved,
}: {
  product: Product;
  close: () => void;
  saved: () => void;
}) {
  const [form] = Form.useForm();
  return (
    <RetailEditor
      title="调整商品展示顺序"
      width={440}
      form={form}
      initialValues={{ Sort: product.Sort ?? 0 }}
      onClose={close}
      onSave={async ({ Sort }) => {
        await call(`products/${product.ID}/sort`, 'PUT', {
          Sort,
          Version: product.Version,
        });
        saved();
      }}
    >
      <p>{product.Name}</p>
      <ProductSortField />
    </RetailEditor>
  );
}

function ProductEditor({
  product,
  categories,
  close,
  saved,
}: {
  product: Partial<Product>;
  categories: Category[];
  close: () => void;
  saved: () => void;
}) {
  const [form] = Form.useForm();
  const [uploading, setUploading] = useState(false);
  const initial = {
    ...product,
    Enabled: product.Enabled ?? false,
    Sort: product.Sort ?? 0,
    Images: product.Images || [],
    Parameters: Object.entries(product.Parameters || {}).map(
      ([Name, Value]) => ({ Name, Value })
    ),
    SKUs: (product.Offers || []).map((s) => ({ ...s })).length
      ? product.Offers
      : [{ Name: '默认规格', Code: '', Enabled: true }],
  };
  return (
    <RetailEditor
      title={product.ID ? '编辑商品' : '新增商品'}
      form={form}
      initialValues={initial}
      onClose={close}
      onSave={async (v) => {
        if (uploading) throw Error('请等待图片上传完成');
        await call('products', 'PUT', {
          ...v,
          ID: product.ID || 0,
          Version: product.Version || 0,
          Parameters: Object.fromEntries(
            (v.Parameters || []).map((p: any) => [p.Name, p.Value])
          ),
          SKUs: v.SKUs.map((s: any) => ({
            ID: s.ID || 0,
            Name: s.Name,
            Code: s.Code || '',
            Image: s.Image || '',
            Specifications: s.Specifications || {},
            Enabled: s.Enabled,
          })),
        });
        saved();
      }}
    >
      <Form.Item name="Name" label="商品名称" rules={required}>
        <Input maxLength={120} />
      </Form.Item>
      <Space align="start">
        <Form.Item name="CategoryID" label="分类" rules={required}>
          <Select
            style={{ width: 260 }}
            options={categories.map((c) => ({
              value: c.ID,
              label: `${
                c.ParentID
                  ? categories.find((p) => p.ID === c.ParentID)?.Name + ' / '
                  : ''
              }${c.Name}`,
            }))}
          />
        </Form.Item>
        <Form.Item name="Enabled" label="商品可售" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Space>
      <ProductSortField />
      <Form.Item
        label="商品图片"
        extra="第一张为封面；最多12张。门店还需设置价格、库存及上架状态。"
      >
        <Form.List name="Images">
          {(fields, { add, remove, move }) => (
            <>
              <Space wrap>
                {fields.map((f, i) => (
                  <div key={f.key}>
                    <Image
                      src={form.getFieldValue(['Images', f.name])}
                      width={88}
                      height={88}
                      style={{ objectFit: 'cover' }}
                    />
                    <Space>
                      <Button
                        size="small"
                        disabled={i === 0}
                        onClick={() => move(i, i - 1)}
                      >
                        前移
                      </Button>
                      <Button
                        size="small"
                        aria-label="删除图片"
                        icon={<DeleteOutlined />}
                        onClick={() => remove(f.name)}
                      />
                    </Space>
                    <Form.Item name={f.name} hidden>
                      <Input />
                    </Form.Item>
                  </div>
                ))}
              </Space>
              <Upload
                showUploadList={false}
                accept="image/jpeg,image/png,image/webp"
                disabled={uploading || fields.length >= 12}
                customRequest={async (options) => {
                  setUploading(true);
                  try {
                    const data = new FormData();
                    data.append('file', options.file as File);
                    const res = await request<any>(
                      '/admin_api/retail/v1/images',
                      { method: 'POST', data }
                    );
                    if (res.Code !== 0) throw Error(res.Message || '上传失败');
                    add(res.Data.URL);
                    options.onSuccess?.(res);
                  } catch (e) {
                    message.error('图片上传失败，请重试');
                    options.onError?.(e as Error);
                  } finally {
                    setUploading(false);
                  }
                }}
              >
                <Button icon={<UploadOutlined />} loading={uploading}>
                  上传图片
                </Button>
              </Upload>
            </>
          )}
        </Form.List>
      </Form.Item>
      <Form.Item name="Description" label="商品详情">
        <Input.TextArea rows={5} maxLength={20000} showCount />
      </Form.Item>
      <Form.List name="Parameters">
        {(fields, { add, remove }) => (
          <Card
            size="small"
            title="商品参数（选填）"
            extra={
              <Button type="link" onClick={() => add({})}>
                添加参数
              </Button>
            }
          >
            {fields.map((f) => (
              <Space key={f.key} align="start">
                <Form.Item name={[f.name, 'Name']} rules={required}>
                  <Input placeholder="参数名，如材质" maxLength={60} />
                </Form.Item>
                <Form.Item name={[f.name, 'Value']} rules={required}>
                  <Input placeholder="参数值" maxLength={500} />
                </Form.Item>
                <Button
                  icon={<DeleteOutlined />}
                  onClick={() => remove(f.name)}
                />
              </Space>
            ))}
          </Card>
        )}
      </Form.List>
      <Form.List name="SKUs">
        {(fields, { add, remove }) => (
          <Card
            size="small"
            title="规格"
            style={{ marginTop: 16 }}
            extra={
              <Button
                type="link"
                onClick={() => add({ Name: '', Enabled: true })}
              >
                添加规格
              </Button>
            }
          >
            {fields.map((f) => (
              <Space key={f.key} align="start" wrap>
                <Form.Item name={[f.name, 'ID']} hidden>
                  <InputNumber />
                </Form.Item>
                <Form.Item
                  name={[f.name, 'Name']}
                  label="规格名称"
                  rules={required}
                >
                  <Input placeholder="如黑色 / 标准尺寸" maxLength={120} />
                </Form.Item>
                <Form.Item name={[f.name, 'Code']} label="货号（选填）">
                  <Input maxLength={64} />
                </Form.Item>
                <Form.Item
                  name={[f.name, 'Enabled']}
                  label="启用"
                  valuePropName="checked"
                >
                  <Switch />
                </Form.Item>
                <Button
                  disabled={fields.length === 1}
                  onClick={() => remove(f.name)}
                >
                  移除
                </Button>
              </Space>
            ))}
          </Card>
        )}
      </Form.List>
    </RetailEditor>
  );
}
function CategoryEditor({
  category,
  all,
  close,
  saved,
}: {
  category: Partial<Category>;
  all: Category[];
  close: () => void;
  saved: () => void;
}) {
  const [form] = Form.useForm();
  return (
    <RetailEditor
      title={category.ID ? '编辑分类' : '新增分类'}
      form={form}
      initialValues={{ ParentID: 0, Sort: 0, Enabled: true, ...category }}
      onClose={close}
      onSave={async (v) => {
        await call('categories', 'PUT', {
          ...v,
          ID: category.ID || 0,
          Version: category.Version || 0,
        });
        saved();
      }}
    >
      <Form.Item name="Name" label="分类名称" rules={required}>
        <Input maxLength={60} />
      </Form.Item>
      <Form.Item name="ParentID" label="上级分类">
        <Select
          options={[
            { value: 0, label: '一级分类' },
            ...all
              .filter((c) => !c.ParentID && c.ID !== category.ID)
              .map((c) => ({ value: c.ID, label: c.Name })),
          ]}
        />
      </Form.Item>
      <Form.Item name="Sort" label="排序">
        <InputNumber min={0} precision={0} />
      </Form.Item>
      <Form.Item name="Enabled" label="显示分类" valuePropName="checked">
        <Switch />
      </Form.Item>
    </RetailEditor>
  );
}
export default function RetailCatalog() {
  const [categories, setCategories] = useState<Category[]>([]),
    [products, setProducts] = useState<Product[]>([]),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(1),
    [keyword, setKeyword] = useState(''),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [revision, setRevision] = useState(0);
  const [product, setProduct] = useState<Partial<Product>>(),
    [category, setCategory] = useState<Partial<Category>>();
  const [productToSort, setProductToSort] = useState<Product>();
  const seq = useRef(0);
  const reload = () => setRevision((v) => v + 1);
  useEffect(() => {
    const token = ++seq.current;
    setBusy(true);
    setError('');
    Promise.all([
      call<{ Categories: Category[] }>('categories'),
      call<{ Products: Product[]; Total: number }>('products', 'GET', {
        Page: page,
        Keyword: keyword,
      }),
    ])
      .then(([c, p]) => {
        if (token !== seq.current) return;
        setCategories(c.Categories);
        setProducts(p.Products);
        setTotal(p.Total);
      })
      .catch((e) => {
        if (token === seq.current) setError(e.message);
      })
      .finally(() => {
        if (token === seq.current) setBusy(false);
      });
    return () => {
      seq.current++;
    };
  }, [page, keyword, revision]);
  return (
    <PageContainer
      title="商城商品与分类"
      extra={<Button onClick={reload}>刷新</Button>}
    >
      {error && (
        <Card>
          <p>{error}</p>
          <Button onClick={reload}>重试</Button>
        </Card>
      )}
      <Tabs
        items={[
          {
            key: 'products',
            label: '商品资料',
            children: (
              <Card>
                <Space style={{ marginBottom: 16 }}>
                  <Input.Search
                    placeholder="搜索商品"
                    allowClear
                    onSearch={(v) => {
                      setPage(1);
                      setKeyword(v);
                    }}
                  />
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => setProduct({})}
                  >
                    新增商品
                  </Button>
                </Space>
                <Table<Product>
                  rowKey="ID"
                  loading={busy}
                  dataSource={products}
                  pagination={{
                    current: page,
                    pageSize: 20,
                    total,
                    onChange: setPage,
                  }}
                  columns={[
                    {
                      title: '商品',
                      dataIndex: 'Name',
                      width: 280,
                      render: (_, p) => (
                        <Space>
                          {p.Images?.[0] && (
                            <Image src={p.Images[0]} width={48} height={48} />
                          )}
                          <span>{p.Name}</span>
                        </Space>
                      ),
                    },
                    {
                      title: '分类',
                      dataIndex: 'CategoryID',
                      width: 144,
                      render: (id) => categories.find((c) => c.ID === id)?.Name,
                    },
                    {
                      title: '状态',
                      dataIndex: 'Enabled',
                      width: 92,
                      render: (v) => (v ? '可售' : '已停用'),
                    },
                    {
                      title: '展示顺序',
                      dataIndex: 'Sort',
                      width: 104,
                      render: (sort) => sort ?? 0,
                    },
                    {
                      title: '操作',
                      width: 168,
                      render: (_, p) => (
                        <Space size={0}>
                          <Button type="link" onClick={() => setProductToSort(p)}>
                            调整顺序
                          </Button>
                          <Button type="link" onClick={() => setProduct(p)}>
                            编辑
                          </Button>
                        </Space>
                      ),
                    },
                  ]}
                />
              </Card>
            ),
          },
          {
            key: 'categories',
            label: '商品分类',
            children: (
              <Card
                extra={
                  <Button type="primary" onClick={() => setCategory({})}>
                    新增分类
                  </Button>
                }
              >
                <Table<Category>
                  rowKey="ID"
                  dataSource={categories}
                  pagination={false}
                  columns={[
                    { title: '分类', dataIndex: 'Name' },
                    {
                      title: '上级分类',
                      dataIndex: 'ParentID',
                      render: (id) =>
                        categories.find((c) => c.ID === id)?.Name || '一级分类',
                    },
                    { title: '排序', dataIndex: 'Sort' },
                    {
                      title: '显示',
                      dataIndex: 'Enabled',
                      render: (v) => (v ? '是' : '否'),
                    },
                    {
                      title: '操作',
                      render: (_, c) => (
                        <Button type="link" onClick={() => setCategory(c)}>
                          编辑
                        </Button>
                      ),
                    },
                  ]}
                />
              </Card>
            ),
          },
        ]}
      />
      {product && (
        <ProductEditor
          product={product}
          categories={categories}
          close={() => setProduct(undefined)}
          saved={reload}
        />
      )}
      {productToSort && (
        <ProductSortEditor
          product={productToSort}
          close={() => setProductToSort(undefined)}
          saved={reload}
        />
      )}
      {category && (
        <CategoryEditor
          category={category}
          all={categories}
          close={() => setCategory(undefined)}
          saved={reload}
        />
      )}
    </PageContainer>
  );
}
