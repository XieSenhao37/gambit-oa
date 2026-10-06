import { settlementProof } from '@/services/settlement';
import { Button, Image, Modal, message } from 'antd';
import { useEffect, useState } from 'react';

export function ReceiptProof({
  id,
  kind = 'expenses',
}: {
  id: number;
  kind?: 'expenses';
}) {
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );
  return (
    <>
      <Button
        type="link"
        loading={busy}
        onClick={async () => {
          setBusy(true);
          try {
            setUrl(URL.createObjectURL(await settlementProof(id, kind)));
          } catch {
            message.error('凭证图片读取失败，请重试');
          } finally {
            setBusy(false);
          }
        }}
      >
        查看图片
      </Button>
      <Modal
        title="付款凭证图片"
        open={!!url}
        onCancel={() => setUrl('')}
        footer={null}
        destroyOnClose
      >
        {url && (
          <Image src={url} alt="转账图片凭证" style={{ maxWidth: '100%' }} />
        )}
      </Modal>
    </>
  );
}
