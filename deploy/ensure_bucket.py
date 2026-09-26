"""Create the local S3-compatible bucket before API and worker start."""

from __future__ import annotations

import os
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError


def main() -> None:
    bucket = os.environ["CAPSTONE_ARTIFACT_BUCKET"]
    endpoint = os.environ["CAPSTONE_S3_ENDPOINT"]
    client = boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1")
    for attempt in range(40):
        try:
            client.create_bucket(Bucket=bucket)
            return
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {
                "BucketAlreadyOwnedByYou", "BucketAlreadyExists",
            }:
                return
        except (BotoCoreError, EndpointConnectionError):
            pass
        time.sleep(0.5 if attempt < 20 else 1)
    raise RuntimeError("local artifact bucket is unavailable")


if __name__ == "__main__":
    main()
