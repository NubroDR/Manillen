---
description: "Use when changing Docker, Compose, container startup, NAS hosting, GitHub Actions, or publishing/deployment workflows."
name: "Deployment and Publishing"
applyTo:
  - "Dockerfile"
  - "docker-compose.yml"
  - "docker-entrypoint.sh"
  - ".github/workflows/**"
---

# Deployment guidance

- The Docker image runs the writable `app.py` on port 8000; Compose publishes it on NAS port 8080 and mounts persistent data at `/app/data`.
- Preserve the entrypoint's seed-only behavior: copy only missing initial files into the data mount; never replace existing persistent files.
- Keep deployment configuration consistent with the README, including host data paths, ports, required environment variables, and workflow names.
- Keep secrets in runtime environment or GitHub Actions secrets. Never add credentials to the image, repository, workflow output, or user-facing messages.
- Preserve least-privilege workflow permissions and avoid changing workflow triggers or deployment targets without updating the README.
- After changing deployment or publishing behavior, validate the relevant YAML/configuration and update `README.md` in the same change.
