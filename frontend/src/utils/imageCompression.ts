type CompressionOptions = {
  maxWidth: number;
  maxHeight: number;
  quality: number;
  format: 'image/png' | 'image/jpeg' | 'preserve-transparency';
};

export async function compressRasterImage(
  file: File,
  options: CompressionOptions,
): Promise<File> {
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
      options.maxWidth / image.naturalWidth,
      options.maxHeight / image.naturalHeight,
    );
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const context = canvas.getContext('2d');
    if (!context) return file;

    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    let type = options.format;
    if (type === 'preserve-transparency') {
      const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
      const hasTransparency = data.some(
        (channel, index) => index % 4 === 3 && channel < 255,
      );
      type = hasTransparency ? 'image/png' : 'image/jpeg';
    }
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, type, options.quality);
    });
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

async function isStaticPng(file: File): Promise<boolean> {
  // APNG places its animation control chunk before the first image data chunk.
  // Preserve the original if this prefix is insufficient to tell.
  const bytes = new DataView(await file.slice(0, 64 * 1024).arrayBuffer());
  for (let offset = 8; offset + 8 <= bytes.byteLength; ) {
    const chunk = bytes.getUint32(offset + 4);
    if (chunk === 0x6163544c) return false; // acTL
    if (chunk === 0x49444154) return true; // IDAT
    offset += 12 + bytes.getUint32(offset);
  }
  return false;
}

export async function compressPromotionImage(file: File): Promise<File> {
  if (file.size <= 512 * 1024) return file;
  const jpeg = /\.jpe?g$/i.test(file.name);
  try {
    if (!jpeg && (!/\.png$/i.test(file.name) || !(await isStaticPng(file)))) {
      return file;
    }
    return await compressRasterImage(file, {
      maxWidth: 1440,
      maxHeight: 3840,
      quality: 0.9,
      format: jpeg ? 'image/jpeg' : 'preserve-transparency',
    });
  } catch {
    return file;
  }
}
