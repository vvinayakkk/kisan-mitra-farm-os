import os
from functools import lru_cache
from pathlib import Path
from uuid import uuid4


def enabled():
    return bool(os.getenv("ASSISTANT_S3_BUCKET"))


@lru_cache(maxsize=1)
def _client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ["AWS_REGION"],
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3, "mode": "standard"}),
    )


def _key(path: Path, root: Path, namespace: str):
    relative = path.resolve().relative_to(root.resolve())
    if not relative.parts or any(part in (".", "..") for part in relative.parts):
        raise ValueError("Invalid object path")
    return namespace + "/" + relative.as_posix()


def uri(path: Path, root: Path, namespace: str):
    if not enabled():
        return path.resolve().as_uri()
    return "s3://" + os.environ["ASSISTANT_S3_BUCKET"] + "/" + _key(path, root, namespace)


def put(path: Path, root: Path, namespace: str):
    if enabled():
        _client().upload_file(
            str(path), os.environ["ASSISTANT_S3_BUCKET"], _key(path, root, namespace)
        )
    return uri(path, root, namespace)


def ensure(path: Path, root: Path, namespace: str):
    if path.is_file():
        return True
    if not enabled():
        return False
    from botocore.exceptions import ClientError

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        _client().download_file(
            os.environ["ASSISTANT_S3_BUCKET"], _key(path, root, namespace), str(temporary)
        )
        temporary.chmod(0o600)
        temporary.replace(path)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            return False
        raise
    finally:
        temporary.unlink(missing_ok=True)
    return True
