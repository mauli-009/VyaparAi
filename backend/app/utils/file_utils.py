import uuid
import os
import boto3
import tempfile
from botocore.config import Config
from botocore.exceptions import NoCredentialsError, ClientError
from dotenv import load_dotenv

load_dotenv()

UPLOAD_FOLDER = "uploads"
S3_BUCKET = os.getenv("AWS_S3_BUCKET_NAME")
ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL")


def _get_s3_client():
    """Lazy init — always reads from env so vars are guaranteed loaded."""
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name="auto",
        config=Config(signature_version="s3v4")
    )


def generate_file_id():
    return str(uuid.uuid4())


def save_uploaded_file_locally(file, file_id):
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    file_path = os.path.join(UPLOAD_FOLDER, f"{file_id}.csv")
    contents = file.file.read()
    with open(file_path, "wb") as buffer:
        buffer.write(contents)
    file.file.seek(0)
    return file_path


def upload_to_s3(local_file_path, file_id):
    s3_key = f"datasets/{file_id}.csv"
    try:
        client = _get_s3_client()
        client.upload_file(
            local_file_path,
            os.getenv("AWS_S3_BUCKET_NAME"),
            s3_key,
            ExtraArgs={"ContentType": "text/csv"}
        )
        return f"s3://{os.getenv('AWS_S3_BUCKET_NAME')}/{s3_key}"
    except NoCredentialsError:
        raise Exception("R2 credentials missing. Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        raise Exception(f"R2 upload failed [{error_code}]: {error_msg}")
    except Exception as e:
        raise Exception(f"Unexpected upload error: {str(e)}")


def download_from_s3(s3_path: str) -> str:
    """
    Downloads a file from R2 to a temp local file.
    Returns the local temp file path. Caller must delete it after use.
    s3_path format: s3://bucket-name/datasets/file_id.csv
    """
    path_without_prefix = s3_path.replace("s3://", "")
    bucket, s3_key = path_without_prefix.split("/", 1)

    client = _get_s3_client()

    # Close immediately after creation — fixes Windows file locking issue
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    tmp.close()

    try:
        client.download_file(bucket, s3_key, tmp.name)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        raise Exception(f"R2 download failed [{error_code}]: {s3_key}")

    return tmp.name