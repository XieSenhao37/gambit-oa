import { compressRasterImage } from './imageCompression';

// 桌游照片在浏览器压缩，保留透明 PNG；GIF 保留动画，不转为静态图。
export async function compressGameImage(file: File): Promise<File> {
  if (file.type === 'image/gif' || /\.gif$/i.test(file.name)) return file;
  return compressRasterImage(file, {
    maxWidth: 1600,
    maxHeight: 1600,
    quality: 0.82,
    format: /\.(png|webp)$/i.test(file.name) ? 'image/png' : 'image/jpeg',
  });
}

// 避免一次选择多张图片占满全部 OA worker，同时允许两张上传。
let active = 0;
const waiting: (() => void)[] = [];
export async function runGameImageUpload<T>(
  work: () => Promise<T>,
): Promise<T> {
  await new Promise<void>((resolve) => {
    const start = () => {
      active++;
      resolve();
    };
    if (active < 2) start();
    else waiting.push(start);
  });
  try {
    return await work();
  } finally {
    active--;
    waiting.shift()?.();
  }
}
