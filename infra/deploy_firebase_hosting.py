"""Publish an existing static build through the Firebase Hosting REST API."""

import argparse
import gzip
import hashlib
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import requests

BASE = "https://firebasehosting.googleapis.com/v1beta1"


def access_token():
    return subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()


def request(method, url, token, **kwargs):
    response = requests.request(
        method,
        url,
        headers={"Authorization": "Bearer " + token, **kwargs.pop("headers", {})},
        timeout=45,
        **kwargs,
    )
    response.raise_for_status()
    return response.json() if response.content else {}


def publish(project, directory, site=None):
    token = access_token()
    site = site or project
    headers = {"x-goog-user-project": project}
    config = {
        "rewrites": [{"glob": "**", "path": "/index.html"}],
        "headers": [
            {"glob": "/assets/**", "headers": {"Cache-Control": "public,max-age=31536000,immutable"}},
            {"glob": "/index.html", "headers": {"Cache-Control": "no-store"}},
        ],
    }
    version = request(
        "POST", f"{BASE}/sites/{site}/versions", token,
        headers=headers, json={"config": config},
    )["name"]
    compressed = {}
    for path in directory.rglob("*"):
        if path.is_file():
            content = gzip.compress(path.read_bytes(), mtime=0)
            digest = hashlib.sha256(content).hexdigest()
            compressed[digest] = content
    files = {
        "/" + path.relative_to(directory).as_posix():
            hashlib.sha256(gzip.compress(path.read_bytes(), mtime=0)).hexdigest()
        for path in directory.rglob("*") if path.is_file()
    }
    if not files or len(files) > 1000:
        raise RuntimeError("Hosting build must contain between 1 and 1000 files")
    pending = request(
        "POST", f"{BASE}/{version}:populateFiles", token,
        headers=headers, json={"files": files},
    )
    upload_url = pending["uploadUrl"]
    if urlsplit(upload_url).scheme != "https" or urlsplit(upload_url).hostname != "upload-firebasehosting.googleapis.com":
        raise RuntimeError("Unexpected Firebase upload origin")

    def upload(digest):
        response = requests.post(
            upload_url + "/" + digest,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/octet-stream"},
            data=compressed[digest],
            timeout=90,
        )
        response.raise_for_status()

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(upload, pending.get("uploadRequiredHashes", [])))
    finalized = request(
        "PATCH", f"{BASE}/{version}", token,
        headers=headers, params={"update_mask": "status"}, json={"status": "FINALIZED"},
    )
    if finalized.get("status") != "FINALIZED":
        raise RuntimeError("Hosting version was not finalized")
    release = request(
        "POST", f"{BASE}/sites/{site}/releases", token,
        headers=headers, params={"versionName": version},
    )
    print("released", release["name"], "files", len(files), "url", f"https://{site}.web.app")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--site", help="Hosting site ID; defaults to the project ID")
    parser.add_argument("--directory", type=Path, default=Path("frontend/dist"))
    arguments = parser.parse_args()
    publish(arguments.project, arguments.directory, arguments.site)
