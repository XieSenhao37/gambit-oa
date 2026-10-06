import { bannerPreviewUrl, uploadBanner } from '@/services/banner';
import { UploadOutlined } from '@ant-design/icons';
import { Button, Image, message, Space, Typography, Upload } from 'antd';
import { useRef, useState } from 'react';
export default function ImageField({
  value,
  onChange,
  wide,
  variant,
  disabled = false,
  onBusy,
}: {
  value?: string;
  onChange?: (value: string) => void;
  wide?: boolean;
  variant?: 'splash' | 'popup';
  disabled?: boolean;
  onBusy: (busy: boolean) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const busy = useRef(false);
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <div
        style={{
          height: 150,
          background: '#f5f6f8',
          borderRadius: 8,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
        }}
      >
        {value ? (
          <Image
            src={bannerPreviewUrl(value)}
            height={150}
            style={{ width: '100%', objectFit: 'contain' }}
          />
        ) : (
          <Typography.Text type="secondary">
            {variant === 'splash'
              ? '3:4 开屏海报'
              : variant === 'popup'
              ? '3:4 首页弹窗海报'
              : wide
              ? '首页轮播展示图'
              : '点击后显示的完整大图'}
          </Typography.Text>
        )}
      </div>
      <Upload
        accept="image/png,image/jpeg,image/webp,image/gif"
        showUploadList={false}
        disabled={uploading || disabled}
        beforeUpload={async (file) => {
          if (busy.current) return false;
          if (file.size > 10 * 1024 * 1024) {
            message.error('图片不能超过 10MB');
            return false;
          }
          busy.current = true;
          setUploading(true);
          onBusy(true);
          try {
            const res = await uploadBanner(file);
            onChange?.(res.Url);
          } catch {
            message.error('上传失败，请重试');
          } finally {
            busy.current = false;
            setUploading(false);
            onBusy(false);
          }
          return false;
        }}
      >
        <Button icon={<UploadOutlined />} loading={uploading}>
          {value ? '替换图片' : '上传图片'}
        </Button>
      </Upload>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {variant === 'splash'
          ? '建议 1080 × 1440（3:4），完整展示；底部品牌区自动生成'
          : variant === 'popup'
          ? '建议 1080 × 1440（3:4），与开屏共用素材，完整展示不裁剪'
          : wide
          ? '建议比例 21:9，完整显示'
          : '支持长图，可放大查看'}{' '}
        · 最大 10MB
      </Typography.Text>
    </Space>
  );
}
