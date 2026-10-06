import Banners from '@/pages/Banners';
import { PageContainer } from '@ant-design/pro-components';
import { Tabs } from 'antd';
import Promotions from './Promotions';
export default function DisplayManagement() {
  return (
    <PageContainer title="展示管理">
      <Tabs
        destroyInactiveTabPane
        items={[
          {
            key: 'banners',
            label: '首页 Banner',
            children: <Banners embedded />,
          },
          {
            key: 'splash',
            label: '开屏展示',
            children: <Promotions kind="splash" />,
          },
          {
            key: 'popup',
            label: '首页弹窗',
            children: <Promotions kind="popup" />,
          },
        ]}
      />
    </PageContainer>
  );
}
