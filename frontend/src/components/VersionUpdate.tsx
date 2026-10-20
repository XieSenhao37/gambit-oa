import {
  readPageVersion,
  startVersionMonitor,
} from '@/services/versionMonitor';
import { Button, Modal } from 'antd';
import { useEffect, useState, type ReactNode } from 'react';
import './versionUpdate.less';

export default function VersionUpdate({ children }: { children?: ReactNode }) {
  const [available, setAvailable] = useState('');
  const [postponed, setPostponed] = useState(false);
  const [modal, contextHolder] = Modal.useModal();
  useEffect(
    () =>
      startVersionMonitor(readPageVersion(), (version) => {
        setAvailable(version);
        setPostponed(false);
      }),
    [],
  );
  const refresh = () =>
    modal.confirm({
      title: '刷新到新版本？',
      content: '请确认正在编辑的内容已保存。刷新后，未保存的内容会丢失。',
      okText: '已保存，刷新',
      cancelText: '继续编辑',
      okButtonProps: { className: 'oa-update-primary' },
      onOk: () => window.location.reload(),
    });
  return (
    <>
      {children}
      {contextHolder}
      {available &&
        (postponed ? (
          <Button
            className="oa-update-reopen"
            onClick={() => setPostponed(false)}
          >
            发现新版本
          </Button>
        ) : (
          <section className="oa-update-notice" aria-label="版本更新提示">
            <div role="status" aria-live="polite">
              <strong>新版本已准备好</strong>
              <p>刷新后生效，请先保存正在编辑的内容。</p>
            </div>
            <div className="oa-update-actions">
              <Button type="text" onClick={() => setPostponed(true)}>
                稍后
              </Button>
              <Button
                type="primary"
                className="oa-update-primary"
                onClick={refresh}
              >
                立即刷新
              </Button>
            </div>
          </section>
        ))}
    </>
  );
}
