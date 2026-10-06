import { PageContainer } from '@ant-design/pro-components';
import { history, useLocation } from '@umijs/max';
import { Tabs } from 'antd';
import { CateringWorkbench } from '../Catering';
import PlayWorkbench from './PlayWorkbench';

type WorkbenchTab = 'catering' | 'play';

const getActiveTab = (search: string): WorkbenchTab => {
  const tab = new URLSearchParams(search).get('tab');
  return tab === 'play' ? 'play' : 'catering';
};

const WorkbenchPage: React.FC = () => {
  const location = useLocation();
  const activeTab = getActiveTab(location.search);

  const handleTabChange = (tab: string) => {
    history.replace(`/workbench?tab=${tab}`);
  };

  return (
    <PageContainer title="工作台">
      <Tabs
        activeKey={activeTab}
        onChange={handleTabChange}
        items={[
          { key: 'catering', label: '餐饮订单' },
          { key: 'play', label: '游玩订单' },
        ]}
      />
      {activeTab === 'catering' ? <CateringWorkbench /> : <PlayWorkbench />}
    </PageContainer>
  );
};

export default WorkbenchPage;
