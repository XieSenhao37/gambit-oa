// 桌游照片在浏览器压缩，保留透明 PNG；GIF 保留动画，不转为静态图。
export async function compressGameImage(file: File): Promise<File> {
  if (file.type === 'image/gif' || /\.gif$/i.test(file.name)) return file;
  const url = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () =>
        reject(new Error('图片无法读取，请重新选择 jpg/png/webp/gif 图片'));
      img.src = url;
    });
    const scale = Math.min(
      1,
      1600 / Math.max(image.naturalWidth, image.naturalHeight),
    );
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const context = canvas.getContext('2d');
    if (!context) return file;
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const type = /\.(png|webp)$/i.test(file.name) ? 'image/png' : 'image/jpeg';
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, type, 0.82);
    });
    // 压缩反而变大时保留原文件。
    if (!blob || blob.size >= file.size) return file;
    return new File(
      [blob],
      file.name.replace(/\.[^.]+$/, type === 'image/png' ? '.png' : '.jpg'),
      { type },
    );
  } finally {
    URL.revokeObjectURL(url);
  }
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
