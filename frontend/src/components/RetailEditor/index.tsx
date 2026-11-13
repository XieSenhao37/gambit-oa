import { Button, Form, message, Modal, Space } from 'antd';
import type { FormInstance } from 'antd';
import { useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { newRequestKey } from '@/services/requestKey';

export function useMutationKey() {
  const ref = useRef({ data: '', key: '' });
  return (data: unknown) => {
    const serialized = JSON.stringify(data);
    if (ref.current.data !== serialized || !ref.current.key)
      ref.current = { data: serialized, key: newRequestKey() };
    return ref.current.key;
  };
}
export default function RetailEditor({
  title,
  form,
  initialValues,
  onSave,
  onClose,
  children,
  width = 720,
}: {
  title: string;
  form: FormInstance;
  initialValues: object;
  onSave: (v: any) => Promise<void>;
  onClose: () => void;
  children: ReactNode;
  width?: number;
}) {
  const [busy, setBusy] = useState(false);
  const close = () => {
    if (busy) return;
    if (form.isFieldsTouched())
      Modal.confirm({
        title: '放弃尚未保存的修改？',
        okText: '放弃修改',
        cancelText: '继续编辑',
        onOk: onClose,
      });
    else onClose();
  };
  return (
    <Modal
      open
      title={title}
      width={width}
      className="oa-operation-modal"
      maskClosable={false}
      onCancel={close}
      footer={
        <Space>
          <Button disabled={busy} onClick={close}>
            取消
          </Button>
          <Button type="primary" loading={busy} onClick={() => form.submit()}>
            保存
          </Button>
        </Space>
      }
    >
      <Form
        form={form}
        initialValues={initialValues}
        layout="vertical"
        disabled={busy}
        onFinish={async (v) => {
          setBusy(true);
          try {
            await onSave(v);
            message.success('已保存');
            onClose();
          } catch (e) {
            message.error(e instanceof Error ? e.message : '保存失败，请重试');
          } finally {
            setBusy(false);
          }
        }}
      >
        {children}
      </Form>
    </Modal>
  );
}
