import { call, Lead, Policy, Share } from '@/services/gameServices';
import { getPageStores } from '@/utils/pageStores';
import { PageContainer } from '@ant-design/pro-components';
import { useModel } from '@umijs/max';
import {
  Avatar,
  Button,
  Empty,
  Image,
  Input,
  InputNumber,
  message,
  Modal,
  Pagination,
  Select,
  Skeleton,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import dayjs from 'dayjs';
import { useEffect, useRef, useState } from 'react';
import './index.less';

type Community = {
  Shares: Share[];
  Intents: Lead[];
  ShareTotal: number;
  IntentTotal: number;
};
type Settings = { Policy: Policy; Revision: number };
export default function GameCommunity() {
  const { initialState } = useModel('@@initialState');
  const stores = getPageStores(
    initialState?.auth?.Stores ?? [],
    'game-community',
  );
  const managedStores = stores.filter((s) => s.Pages.includes('game-services'));
  const accessKey = stores.map((s) => `${s.Id}:${s.Pages.join(',')}`).join('|');
  const [tab, setTab] = useState('intents');
  const [data, setData] = useState<Community>();
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [shareKeyword, setShareKeyword] = useState('');
  const [shareStatus, setShareStatus] = useState('all');
  const [intentPage, setIntentPage] = useState(1);
  const [sharePage, setSharePage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [acting, setActing] = useState<number>();
  const actingRef = useRef(false);
  const refresh = () => setRevision((v) => v + 1);
  useEffect(() => {
    let disposed = false;
    setLoading(true);
    setFailed(false);
    setData(undefined);
    call<Community>('community', 'GET', {
      Page: sharePage,
      IntentPage: intentPage,
      Keyword: keyword,
      ShareKeyword: shareKeyword,
      ShareStatus: shareStatus,
    })
      .then((next) => {
        if (!disposed) setData(next);
      })
      .catch(() => {
        if (!disposed) setFailed(true);
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
    };
  }, [
    sharePage,
    intentPage,
    keyword,
    shareKeyword,
    shareStatus,
    revision,
    accessKey,
  ]);

  const [settingsStore, setSettingsStore] = useState<number>();
  const [settings, setSettings] = useState<Settings>();
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsRevision, setSettingsRevision] = useState(0);
  const managedKey = managedStores.map((s) => s.Id).join(',');
  useEffect(() => {
    let disposed = false;
    setSettings(undefined);
    if (!settingsStore) return;
    if (!managedStores.some((s) => s.Id === settingsStore)) {
      setSettingsStore(undefined);
      return;
    }
    setSettingsLoading(true);
    call<Settings>('policy', 'GET', undefined, settingsStore)
      .then((next) => {
        if (!disposed) setSettings(next);
      })
      .catch(() => {
        if (!disposed) message.error('社区设置加载失败');
      })
      .finally(() => {
        if (!disposed) setSettingsLoading(false);
      });
    return () => {
      disposed = true;
    };
  }, [settingsStore, managedKey, settingsRevision]);
  async function saveSettings() {
    if (!settings || !settingsStore || savingSettings) return;
    setSavingSettings(true);
    try {
      await call('policy', 'PUT', settings, settingsStore);
      setSettingsStore(undefined);
      message.success('社区设置已保存');
    } finally {
      setSavingSettings(false);
    }
  }
  async function manageShare(s: Share, status: string, quality: boolean) {
    if (actingRef.current) return;
    actingRef.current = true;
    setActing(s.ID);
    try {
      await call(
        'review',
        'POST',
        { ID: s.ID, Version: s.Version, Status: status, Quality: quality },
        s.StoreID,
      );
      message.success(
        quality
          ? '已评为优质分享，奖励按门店规则处理'
          : status === 'rejected'
          ? '已隐藏分享'
          : '已恢复展示',
      );
      refresh();
    } catch {
      message.error('操作未完成，请刷新后核对');
    } finally {
      actingRef.current = false;
      setActing(undefined);
    }
  }
  const retry = (
    <div className="community-empty">
      <Empty description="加载失败，请重试" />
      <Button onClick={refresh}>重新加载</Button>
    </div>
  );
  return (
    <PageContainer
      title="桌游玩家与分享"
      extra={
        <Space>
          {managedStores.length > 0 && (
            <Button onClick={() => setSettingsStore(managedStores[0].Id)}>
              社区设置
            </Button>
          )}
          <Button loading={loading} onClick={refresh}>
            刷新
          </Button>
        </Space>
      }
    >
      <div className="community-page">
        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={[
            {
              key: 'intents',
              label: '想玩列表',
              children: (
                <div className="community-panel">
                  <div className="community-toolbar">
                    <Input.Search
                      placeholder="搜索桌游或玩家"
                      allowClear
                      onSearch={(v) => {
                        setKeyword(v);
                        setIntentPage(1);
                      }}
                    />
                    <span className="community-count">
                      {data ? `${data.IntentTotal} 条想玩记录` : ''}
                    </span>
                  </div>
                  {failed ? (
                    retry
                  ) : (
                    <Table<Lead>
                      rowKey="ID"
                      loading={loading}
                      dataSource={data?.Intents ?? []}
                      scroll={{ x: 760 }}
                      locale={{
                        emptyText: (
                          <Empty
                            image={Empty.PRESENTED_IMAGE_SIMPLE}
                            description="还没有玩家登记想玩"
                          />
                        ),
                      }}
                      pagination={{
                        current: intentPage,
                        total: data?.IntentTotal ?? 0,
                        pageSize: 30,
                        showSizeChanger: false,
                        onChange: setIntentPage,
                        hideOnSinglePage: true,
                      }}
                      columns={[
                        {
                          title: '想玩的桌游',
                          dataIndex: 'GameName',
                          render: (v, row) => v || `桌游 #${row.GameID}`,
                        },
                        {
                          title: '玩家',
                          render: (_, row) => (
                            <Space>
                              <Avatar size={32} src={row.Avatar}>
                                {(row.NickName || '玩').slice(0, 1)}
                              </Avatar>
                              {row.NickName || `玩家 #${row.UserID}`}
                            </Space>
                          ),
                        },
                        {
                          title: '想玩门店',
                          dataIndex: 'StoreName',
                          render: (v, row) => v || `门店 #${row.StoreID}`,
                        },
                        {
                          title: '联系方式',
                          dataIndex: 'Phone',
                          render: (v) =>
                            v ? (
                              <Typography.Text copyable>{v}</Typography.Text>
                            ) : (
                              <Typography.Text type="secondary">
                                未提供
                              </Typography.Text>
                            ),
                        },
                        {
                          title: '登记时间',
                          dataIndex: 'UpdatedAt',
                          width: 172,
                          render: (v) => dayjs(v).format('YYYY-MM-DD HH:mm'),
                        },
                      ]}
                    />
                  )}
                </div>
              ),
            },
            {
              key: 'shares',
              label: '玩家分享列表',
              children: (
                <div className="community-panel">
                  <div className="community-toolbar">
                    <Input.Search
                      placeholder="搜索桌游、玩家或分享内容"
                      allowClear
                      onSearch={(v) => {
                        setShareKeyword(v);
                        setSharePage(1);
                      }}
                    />
                    <Select
                      aria-label="分享状态"
                      value={shareStatus}
                      onChange={(v) => {
                        setShareStatus(v);
                        setSharePage(1);
                      }}
                      options={[
                        { value: 'all', label: '全部分享' },
                        { value: 'published', label: '已公开' },
                        { value: 'quality', label: '优质分享' },
                        { value: 'rejected', label: '已隐藏' },
                      ]}
                    />
                    <span className="community-count">
                      {data ? `${data.ShareTotal} 条分享` : ''}
                    </span>
                  </div>
                  {loading ? (
                    <div className="community-loading">
                      <Skeleton active avatar paragraph={{ rows: 3 }} />
                      <Skeleton active avatar paragraph={{ rows: 2 }} />
                    </div>
                  ) : failed ? (
                    retry
                  ) : !data?.Shares.length ? (
                    <div className="community-empty">
                      <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description={
                          shareKeyword || shareStatus !== 'all'
                            ? '没有符合条件的分享'
                            : '还没有玩家分享'
                        }
                      />
                    </div>
                  ) : (
                    <div className="community-shares">
                      {data.Shares.map((s) => (
                        <article className="community-share" key={s.ID}>
                          <Avatar
                            className="community-share-avatar"
                            size={40}
                            src={s.Author.Avatar}
                          >
                            {(s.Author.NickName || '玩').slice(0, 1)}
                          </Avatar>
                          <div className="community-share-main">
                            <div className="community-share-heading">
                              <strong>{s.Author.NickName || '玩家'}</strong>
                              {s.Quality && <Tag>优质分享</Tag>}
                              {s.Status === 'rejected' && <Tag>已隐藏</Tag>}
                            </div>
                            <div className="community-share-meta">
                              <span className="community-share-game">
                                {s.GameName || `桌游 #${s.BoardGameID}`}
                              </span>
                              <span>{s.StoreName || `门店 #${s.StoreID}`}</span>
                              <time>
                                {dayjs(s.CreatedAt).format('YYYY-MM-DD HH:mm')}
                              </time>
                            </div>
                            {s.Content && (
                              <Typography.Paragraph
                                className="community-share-content"
                                ellipsis={{
                                  rows: 4,
                                  expandable: true,
                                  symbol: '展开',
                                }}
                              >
                                {s.Content}
                              </Typography.Paragraph>
                            )}
                            {s.Images.length > 0 && (
                              <div className="community-share-images">
                                <Image.PreviewGroup>
                                  {s.Images.map((url, i) => (
                                    <Image
                                      key={`${url}-${i}`}
                                      src={url}
                                      width={88}
                                      height={88}
                                      alt={`分享照片 ${i + 1}`}
                                      style={{
                                        objectFit: 'cover',
                                        borderRadius: 8,
                                      }}
                                    />
                                  ))}
                                </Image.PreviewGroup>
                              </div>
                            )}
                          </div>
                          <div className="community-share-actions">
                            {s.RewardedAt ? (
                              <Typography.Text type="secondary">
                                已奖励 {s.RewardPoints} 积分
                              </Typography.Text>
                            ) : (
                              managedStores.some(
                                (store) => store.Id === s.StoreID,
                              ) && (
                                <>
                                  {s.Status !== 'rejected' && !s.Quality && (
                                    <Button
                                      disabled={acting !== undefined}
                                      onClick={() =>
                                        Modal.confirm({
                                          title: '评为优质分享',
                                          content: `按${
                                            s.StoreName || '所属门店'
                                          }当前积分规则发放奖励，每条仅发一次。`,
                                          onOk: () =>
                                            manageShare(s, 'published', true),
                                        })
                                      }
                                    >
                                      评为优质
                                    </Button>
                                  )}
                                  <Button
                                    type="text"
                                    loading={acting === s.ID}
                                    disabled={
                                      acting !== undefined && acting !== s.ID
                                    }
                                    onClick={() =>
                                      manageShare(
                                        s,
                                        s.Status === 'rejected'
                                          ? 'published'
                                          : 'rejected',
                                        false,
                                      )
                                    }
                                  >
                                    {s.Status === 'rejected'
                                      ? '恢复展示'
                                      : '隐藏'}
                                  </Button>
                                </>
                              )
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                  {data && data.ShareTotal > 30 && (
                    <div className="community-pagination">
                      <Pagination
                        current={sharePage}
                        total={data.ShareTotal}
                        pageSize={30}
                        showSizeChanger={false}
                        onChange={setSharePage}
                      />
                    </div>
                  )}
                </div>
              ),
            },
          ]}
        />
      </div>
      <Modal
        title="社区设置"
        open={!!settingsStore}
        onCancel={() => !savingSettings && setSettingsStore(undefined)}
        onOk={saveSettings}
        confirmLoading={savingSettings}
        okButtonProps={{ disabled: !settings || settingsLoading }}
      >
        <div className="community-settings">
          <label>配置门店</label>
          <Select
            aria-label="配置门店"
            disabled={savingSettings}
            value={settingsStore}
            options={managedStores.map((s) => ({ value: s.Id, label: s.Name }))}
            onChange={setSettingsStore}
          />
          {settingsLoading ? (
            <Skeleton active paragraph={{ rows: 3 }} />
          ) : settings ? (
            <>
              <label>优质分享奖励积分</label>
              <InputNumber
                min={0}
                max={10000}
                precision={0}
                value={settings.Policy.QualityRewardPoints}
                onChange={(v) =>
                  setSettings({
                    ...settings,
                    Policy: { ...settings.Policy, QualityRewardPoints: v || 0 },
                  })
                }
              />
              <Typography.Text type="secondary">
                设为 0 时只评优，不发积分
              </Typography.Text>
              <label>想玩联系说明</label>
              <Input.TextArea
                maxLength={300}
                value={settings.Policy.ContactNotice}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    Policy: {
                      ...settings.Policy,
                      ContactNotice: e.target.value,
                    },
                  })
                }
              />
            </>
          ) : (
            <Button onClick={() => setSettingsRevision((v) => v + 1)}>
              重新加载设置
            </Button>
          )}
        </div>
      </Modal>
    </PageContainer>
  );
}
