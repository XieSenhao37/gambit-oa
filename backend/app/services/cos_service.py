"""腾讯云 COS 文件上传服务"""
from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from flask import current_app
from qcloud_cos import CosConfig, CosS3Client


def _get_client() -> CosS3Client:
    config = CosConfig(
        Region=current_app.config['COS_REGION'],
        SecretId=current_app.config['COS_SECRET_ID'],
        SecretKey=current_app.config['COS_SECRET_KEY'],
    )
    return CosS3Client(config)


def upload_file_to_cos(
    file_bytes: bytes,
    original_filename: str,
    folder: str = 'dish-images',
) -> str:
    """上传文件到 COS，返回公开访问 URL。"""
    ext = PurePosixPath(original_filename).suffix or '.jpg'
    key = f'{folder}/{uuid.uuid4().hex}{ext}'

    client = _get_client()
    bucket = current_app.config['COS_BUCKET']
    region = current_app.config['COS_REGION']
    client.put_object(
        Bucket=bucket,
        Body=file_bytes,
        Key=key,
        ContentType=_guess_content_type(ext),
    )

    return f'https://{bucket}.cos.{region}.myqcloud.com/{key}'


def _guess_content_type(ext: str) -> str:
    mapping = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
    }
    return mapping.get(ext.lower(), 'application/octet-stream')


def upload_private_receipt(content: bytes, ext: str) -> str:
    key=f'settlement-receipts/{uuid.uuid4().hex}{ext}'
    _get_client().put_object(Bucket=current_app.config['COS_BUCKET'],Key=key,Body=content,
        ContentType=_guess_content_type(ext),ACL='private')
    return key


def read_private_receipt(key: str):
    if not key.startswith('settlement-receipts/') or '..' in key:
        raise ValueError('凭证图片路径无效')
    response=_get_client().get_object(Bucket=current_app.config['COS_BUCKET'],Key=key)
    return response['Body'].get_raw_stream().read(),_guess_content_type(PurePosixPath(key).suffix)
