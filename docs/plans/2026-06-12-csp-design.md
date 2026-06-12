# Design Document: Content Security Policy (Task 12)

## 1. Overview
This document specifies the design for adding a Content Security Policy (CSP) header to the frontend Nginx configuration in DailyFX.

## 2. CSP Directives
We will add the following CSP header in `frontend/nginx.conf`:
```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' ws: wss:; frame-ancestors 'none'; object-src 'none'; base-uri 'self';" always;
```

### Explanations
* `default-src 'self'`: Only load assets from the origin domain by default.
* `script-src 'self' 'unsafe-inline' 'unsafe-eval'`: Required by React/Vite development server (HMR) and standard chunk loading.
* `style-src 'self' 'unsafe-inline'`: Required for React dynamically-injected inline styles.
* `img-src 'self' data: blob:`: Allows local assets, inline base64 images, and `blob:` object URLs from `SecureImage.tsx`.
* `connect-src 'self' ws: wss:`: Restricts API calls to 'self' and allows WebSockets (used in local development HMR).
* `frame-ancestors 'none'`: Prevents iframe clickjacking attacks.
* `object-src 'none'`: Disables dangerous objects/embeds.
* `base-uri 'self'`: Disallows external base URIs.

## 3. Verification and Testing
Verify Nginx configuration using `nginx -t` or check headers manually using `curl -I` when the application is running, or verify it parses correctly in local tests if Nginx configuration validator is available.
Since we don't run Nginx container locally during standard python unit tests, we will verify the syntax is clean.
