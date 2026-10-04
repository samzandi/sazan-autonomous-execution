# Security Policy

## Supported branch

Security fixes target the default branch during pre-1.0 development.

## Reporting a vulnerability

Do not publish credentials, exploit details, private repository data, or sensitive logs in a public issue. Use GitHub's private vulnerability reporting when available. If private reporting is unavailable, open a minimal public issue that states only that a private security contact is needed.

## Security boundaries

This project is designed around least privilege, fail-closed checks, explicit authorization, and evidence before completion. Contributions must not silently expand write permissions, expose secrets, persist private inventories by default, or bypass release gates.

## Scope

A green CI run does not by itself establish production security. Production use requires environment-specific threat modeling, credential isolation, audit logging, incident response, and rollback validation.
