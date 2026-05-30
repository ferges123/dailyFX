# Security Policy

If you discover a security issue, please do not open a public issue with exploit details.

## Reporting

Send a private report to the repository maintainer or use your platform's private vulnerability reporting flow if available.

Include:

- A short description of the issue
- Steps to reproduce
- Affected versions
- Any relevant logs or proof-of-concept details

## Scope

This project stores secrets in `.env` and persists runtime data under `data/`. Never commit real credentials, API keys, or database backups to the repository.
