from storages.backends.s3boto3 import S3Boto3Storage


class S3MediaStorage(S3Boto3Storage):
    """
    서버의 Alias를 S3 Bucket Root로 지정
    """
    location = 'litchi/media'
