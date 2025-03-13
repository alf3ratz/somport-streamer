s3:

```bash
docker run --rm -it -p 4566:4566 -p 4510-4559:4510-4559 localstack/localstack
aws configure set aws_access_key_id test
aws configure set aws_secret_access_key test
aws configure set region us-east-1
aws configure set endpoint_url http://localhost:4566
aws --endpoint-url=http://localhost:4566 s3 mb s3://my-local-bucket
aws --endpoint-url=http://localhost:4566 s3 ls
```