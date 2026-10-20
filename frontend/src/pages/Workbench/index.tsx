import { getCurrentStoreId, rememberPageStore } from '@/utils/pageStores';
import { SettingOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import { history, useLocation, useModel } from '@umijs/max';
import { Button, Tabs } from 'antd';
import { CateringWorkbench } from '../Catering';
import PlayWorkbench from './PlayWorkbench';
import TodayTodos from './TodayTodos';
import './operations.less';

type WorkbenchTab = 'catering' | 'play';

const getActiveTab = (search: string): WorkbenchTab => {
  const tab = new URLSearchParams(search).get('tab');
  return tab === 'play' ? 'play' : 'catering';
};

const WorkbenchPage: React.FC = () => {
  const location = useLocation();
  const activeTab = getActiveTab(location.search);
  const { initialState } = useModel('@@initialState');
  const canPrice = initialState?.auth?.Stores.some(
    (store) =>
      store.Id === getCurrentStoreId() && store.Pages.includes('play-pricing'),
  );

  const handleTabChange = (tab: string) => {
    history.replace(`/workbench?tab=${tab}`);
  };

  return (
    <PageContainer
      title="工作台"
      extra={
        canPrice && (
          <Button
            icon={<SettingOutlined />}
            onClick={() => {
              if (!initialState?.auth) return;
              rememberPageStore(
                initialState.auth.UserId,
                'play-pricing',
                getCurrentStoreId(),
              );
              history.push('/play-pricing');
            }}
          >
            到店游玩计费
          </Button>
        )
      }
    >
      <TodayTodos />
      <Tabs
        activeKey={activeTab}
        onChange={handleTabChange}
        items={[
          { key: 'catering', label: '餐饮制作' },
          { key: 'play', label: '游玩收银' },
        ]}
      />
      {activeTab === 'catering' ? <CateringWorkbench /> : <PlayWorkbench />}
    </PageContainer>
  );
};

export default WorkbenchPage;
