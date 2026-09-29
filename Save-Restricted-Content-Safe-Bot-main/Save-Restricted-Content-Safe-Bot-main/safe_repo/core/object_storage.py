import os
from pathlib import Path
from urllib.parse import quote


_CLIENT = None
_CLIENT_CONFIG = None


def _configuration():
    values = {
        "endpoint_url": os.environ.get("OBJECT_STORAGE_ENDPOINT", "").strip(),
        "bucket": os.environ.get("OBJECT_STORAGE_BUCKET", "").strip(),
        "access_key": os.environ.get("OBJECT_STORAGE_ACCESS_KEY_ID", "").strip(),
        "secret_key": os.environ.get("OBJECT_STORAGE_SECRET_ACCESS_KEY", "").strip(),
        "region": os.environ.get("OBJECT_STORAGE_REGION", "auto").strip() or "auto",
        "prefix": os.environ.get("OBJECT_STORAGE_PREFIX", "safe-repo").strip("/"),
    }
    required = ("endpoint_url", "bucket", "access_key", "secret_key")
    if not any(values[key] for key in required):
        return None
    missing = [key for key in required if not values[key]]
    if missing:
        names = {
            "endpoint_url": "OBJECT_STORAGE_ENDPOINT",
            "bucket": "OBJECT_STORAGE_BUCKET",
            "access_key": "OBJECT_STORAGE_ACCESS_KEY_ID",
            "secret_key": "OBJECT_STORAGE_SECRET_ACCESS_KEY",
        }
        raise RuntimeError("Object storage is partially configured; set " + ", ".join(names[key] for key in missing))
    return values


def is_configured():
    return _configuration() is not None


def object_key(*parts):
    config = _configuration()
    if config is None:
        return None
    safe_parts = [quote(str(part).strip("/"), safe="-_.~") for part in parts if str(part).strip("/")]
    key = "/".join(safe_parts)
    return f"{config['prefix']}/{key}" if config["prefix"] else key


def _get_client():
    global _CLIENT, _CLIENT_CONFIG
    config = _configuration()
    if config is None:
        return None, None
    client_config = tuple(config[key] for key in ("endpoint_url", "access_key", "secret_key", "region"))
    if _CLIENT is None or client_config != _CLIENT_CONFIG:
        import boto3

        _CLIENT = boto3.client(
            "s3",
            endpoint_url=config["endpoint_url"],
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
            region_name=config["region"],
        )
        _CLIENT_CONFIG = client_config
    return _CLIENT, config


def _is_missing_object(error):
    if isinstance(error, (FileNotFoundError, KeyError)):
        return True
    response = getattr(error, "response", {}) or {}
    error_code = str(response.get("Error", {}).get("Code", ""))
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return error_code in {"404", "NoSuchKey", "NotFound"} or status == 404


def get_bytes(key):
    client, config = _get_client()
    if client is None:
        return None
    try:
        response = client.get_object(Bucket=config["bucket"], Key=key)
        return response["Body"].read()
    except Exception as error:
        if _is_missing_object(error):
            return None
        raise


def put_bytes(key, data, content_type="application/octet-stream"):
    client, config = _get_client()
    if client is None:
        return False
    client.put_object(
        Bucket=config["bucket"],
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return True


def download_file(key, destination):
    client, config = _get_client()
    if client is None:
        return False
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        client.download_file(config["bucket"], key, str(path))
        return True
    except Exception as error:
        if _is_missing_object(error):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return False
        raise


def upload_file(key, source_path, content_type=None):
    client, config = _get_client()
    if client is None:
        return False
    extra_args = {"ContentType": content_type} if content_type else None
    client.upload_file(str(source_path), config["bucket"], key, ExtraArgs=extra_args or {})
    return True
