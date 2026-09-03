"""Trigger the repository's GitHub Actions mirror workflow."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GitHubPublishError(RuntimeError):
    """Safe, user-facing error raised when dispatching the workflow fails."""


def trigger_mirror_workflow():
    """Dispatch the configured GitHub Actions workflow and return on HTTP 204."""
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
