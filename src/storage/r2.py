import mimetypes
from contextlib import closing
import boto3
from botocore.config import Config


class R2Storage:
    def __init__(self, settings):
        """使用配置中的 S3 凭据连接私有 R2 桶。"""
        if not all((settings.r2_endpoint, settings.r2_bucket,
                    settings.r2_access_key_id, settings.r2_secret_access_key)):
            raise ValueError('请先填写 R2 endpoint、桶名和两项 S3 密钥')
        if not settings.r2_endpoint.startswith('https://'):
            raise ValueError('R2 endpoint 必须使用 https')
        self.bucket = settings.r2_bucket
        self.expiry = settings.r2_url_expiry_seconds
        self.client = boto3.client('s3', endpoint_url=settings.r2_endpoint,
                                  aws_access_key_id=settings.r2_access_key_id,
                                  aws_secret_access_key=settings.r2_secret_access_key,
                                  region_name='auto', config=Config(signature_version='s3v4',
                                      connect_timeout=settings.request_timeout,
                                      read_timeout=settings.request_timeout,
                                      retries={'max_attempts': 3, 'mode': 'standard'},
                                      request_checksum_calculation='when_required',
                                      response_checksum_validation='when_required'))

    def put(self, key, content):
        """上传单条新增内容；失败时由调用方保留数据库原状态。"""
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content,
                               ContentType=mimetypes.guess_type(key)[0] or 'application/octet-stream')

    def read_text(self, key):
        """读取云端文字并关闭响应流。"""
        with closing(self.client.get_object(Bucket=self.bucket, Key=key)['Body']) as body:
            return body.read().decode('utf-8')

    def url(self, key):
        """每次发送生成新的临时下载地址，无需开放公共访问。"""
        return self.client.generate_presigned_url('get_object',
            Params={'Bucket': self.bucket, 'Key': key}, ExpiresIn=self.expiry)

    def delete(self, key):
        """删除一个对象；R2 删除不存在的对象也视为成功。"""
        self.client.delete_object(Bucket=self.bucket, Key=key)
