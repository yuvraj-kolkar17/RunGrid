# RunGrid — Security Architecture & Threat Model

## Security Principles

RunGrid is built following defense-in-depth security principles to protect multi-tenant workload data, prevent unauthorized execution, and safeguard API credentials.

---

## 1. Authentication & JWT Management

- User access requires standard OAuth2 Password Bearer authentication.
- Passwords are hashed using `bcrypt` prior to storage.
- JWT tokens are signed using HMAC-SHA256 (`JWT_SECRET`) with configurable expiration windows (`ACCESS_TOKEN_EXPIRE_MINUTES`).

---

## 2. Multi-Tenant Isolation & Role-Based Access Control (RBAC)

All REST endpoints enforce row-level tenant filtering based on the user's `organization_id`.
Role permissions:

| Action / Endpoint | OWNER | ADMIN | MEMBER | VIEWER |
|---|:---:|:---:|:---:|:---:|
| View Dashboard & Metrics | ✓ | ✓ | ✓ | ✓ |
| View Jobs & Queues | ✓ | ✓ | ✓ | ✓ |
| Submit / Retry / Cancel Jobs | ✓ | ✓ | ✓ | ✗ |
| Create Batch Jobs & Dependencies | ✓ | ✓ | ✓ | ✗ |
| Create / Pause / Resume Queues | ✓ | ✓ | ✗ | ✗ |
| Create / Delete Cron Schedules | ✓ | ✓ | ✗ | ✗ |
| Manage Organization & Users | ✓ | ✗ | ✗ | ✗ |

---

## 3. Worker Protocol & Secret Isolation

- Workers do NOT possess database access credentials.
- All internal worker endpoints (`/api/v1/internal/*`) enforce authorization header validation via `X-Internal-Key`.
- Workers execute pre-registered Python task handlers from `TaskRegistry`. Raw dynamic code execution (`eval()` / `exec()`) is strictly prohibited.

---

## 4. API Rate Limiting

- Public REST APIs incorporate sliding-window rate limiting.
- Excessive requests beyond configured rate limits return HTTP 429 (`Too Many Requests`).

---

## 5. Credential Handling & Secret Protection

- `.env` files containing real production credentials are explicitly ignored via `.gitignore`.
- Structured JSON loggers sanitize sensitive payload keywords (`password`, `token`, `secret`, `access_token`, `authorization`).
