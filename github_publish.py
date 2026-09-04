"""Trigger the repository's GitHub Actions mirror workflow."""

import json
import os
import base64
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class GitHubPublishError(RuntimeError):
    """Safe, user-facing error raised when dispatching the workflow fails."""


SNAPSHOT_FILES = (
    "pairings.csv",
    "pairings_history.csv",
    "scores_history.csv",
    "reserve_assignments.csv",
)


def _github_config():
    token = os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")
    workflow = os.getenv("GITHUB_WORKFLOW")
    reference = os.getenv("GITHUB_REF", "main")

    if not token:
        raise GitHubPublishError(
            "GitHub-publicatie is niet geconfigureerd: GITHUB_TOKEN ontbreekt."
        )
    if not repository:
        raise GitHubPublishError(
            "GitHub-publicatie is niet geconfigureerd: GITHUB_REPOSITORY ontbreekt."
        )
    if not workflow:
        raise GitHubPublishError(
            "GitHub-publicatie is niet geconfigureerd: GITHUB_WORKFLOW ontbreekt."
        )
    if repository.count("/") != 1 or any(not part.strip() for part in repository.split("/")):
        raise GitHubPublishError("GITHUB_REPOSITORY moet het formaat owner/repository hebben.")

    return token, repository, workflow, reference


def _request_json(request):
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in (401, 403):
            detail = "controleer token en repositoryrechten"
        elif error.code == 404:
            detail = "controleer repository, branch en bestandspad"
        else:
            detail = "controleer de GitHub-configuratie"
        raise GitHubPublishError(
            f"GitHub-publicatie mislukt (HTTP {error.code}); {detail}."
        ) from None
    except URLError as error:
        reason = str(error.reason).splitlines()[0]
        raise GitHubPublishError(f"GitHub is niet bereikbaar: {reason}") from None
    except TimeoutError:
        raise GitHubPublishError("GitHub-publicatie time-out na 15 seconden.") from None


def _upload_snapshot_files(data_dir, token, repository, reference):
    """Upload current NAS snapshots to the repository before dispatching the export."""
    source_dir = Path(data_dir)
    api_root = f"https://api.github.com/repos/{repository}/contents"
    for filename in SNAPSHOT_FILES:
        source = source_dir / filename
        if not source.exists():
            continue

        path = f"data/{filename}"
        encoded_path = quote(path, safe="/")
        get_request = Request(
            f"{api_root}/{encoded_path}?ref={quote(reference)}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )
        _, existing = _request_json(get_request)
        payload = {
            "message": f"Update mirror data: {filename}",
            "content": base64.b64encode(source.read_bytes()).decode("ascii"),
            "branch": reference,
        }
        if existing.get("sha"):
            payload["sha"] = existing["sha"]
        put_request = Request(
            f"{api_root}/{encoded_path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        _request_json(put_request)


def trigger_mirror_workflow(data_dir=None):
    """Upload NAS snapshots and dispatch the configured mirror workflow."""
    token, repository, workflow, reference = _github_config()
    if data_dir is not None:
        _upload_snapshot_files(data_dir, token, repository, reference)

    url = f"https://api.github.com/repos/{repository}/actions/workflows/{workflow}/dispatches"
    request = Request(
        url,
        data=json.dumps({"ref": reference}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status != 204:
                raise GitHubPublishError(
                    f"GitHub gaf onverwachte HTTP-status {response.status}."
                )
    except HTTPError as error:
        if error.code in (401, 403):
            detail = "controleer token en workflowrechten"
        elif error.code == 404:
            detail = "controleer repository en workflownaam"
        else:
            detail = "controleer de GitHub-configuratie"
        raise GitHubPublishError(
            f"GitHub-publicatie mislukt (HTTP {error.code}); {detail}."
        ) from None
    except URLError as error:
        reason = str(error.reason).splitlines()[0]
        raise GitHubPublishError(f"GitHub is niet bereikbaar: {reason}") from None
    except TimeoutError:
        raise GitHubPublishError("GitHub-publicatie time-out na 15 seconden.") from None
