/**
 * COS 数据万象图片处理参数封装。
 *
 * 通过给 COS 图片 URL 拼上 `imageMogr2` 参数，让 CDN 直接吐出指定尺寸/格式的图，
 * 避免前端把数 MB 的原图拉过来再缩小（实测原图常达 4K / 400KB+）。
 *
 * 用法：cosThumb(url, 'sm')
 */
export type CosThumbSize = 'xs' | 'sm' | 'md' | 'lg';

const SIZE_PRESETS: Record<CosThumbSize, string> = {
  xs: 'thumbnail/100x/format/webp/quality/80', // 头像、表格 64×64 缩略图
  sm: 'thumbnail/200x/format/webp/quality/80', // 列表卡片、Upload 100×100 回显
  md: 'thumbnail/600x/format/webp/quality/80', // 详情中等图
  lg: 'thumbnail/1080x/format/webp/quality/85', // 大图预览
};

const COS_HOST_PATTERNS = [/\.myqcloud\.com\//i];

const isCosUrl = (url: string) => COS_HOST_PATTERNS.some((re) => re.test(url));

export function cosThumb(
  url: string | undefined | null,
  size: CosThumbSize = 'sm',
): string {
  if (!url) return '';
  // 非 https COS 链接直接返回（如历史 cloud:// 协议、Base64、外链等）
  if (!isCosUrl(url)) return url;
  // 已经带 imageMogr2 参数则不重复拼接，避免叠加导致行为不可预期
  if (url.includes('imageMogr2') || url.includes('imageView2')) return url;

  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}imageMogr2/${SIZE_PRESETS[size]}`;
}
