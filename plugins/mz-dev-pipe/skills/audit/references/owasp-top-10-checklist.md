# OWASP Top 10 (2021) — Audit Checklist

Source: https://owasp.org/Top10/ (2021 edition — the most recent finalized OWASP Top 10). Each section: one-line definition, grep-able detection patterns, concrete examples, remediation pointer.

Use via grep — locate the category, apply its detection patterns to the scope. Do not load the whole file.

## A01:2021 — Broken Access Control

**Definition**: Users can act outside their intended permissions — horizontal (see other users' data) or vertical (escalate to admin).

**Detection patterns**:

- Grep for route handlers lacking an auth middleware: `(router\.(get|post|put|delete)|@(app|router)\.(route|get|post))` cross-referenced with missing `auth_required` / `@login_required` / `authenticate` decorators.
- Grep for object IDs used directly from request without ownership check: `request.params.id`, `req.body.userId`, `params\["id"\]` followed by `.find_by_id` / `.get(` without a `user_id = current_user` filter.
- Grep for role checks done on the client: `if (user.role === "admin")` in frontend code that controls UI but not server enforcement.
- Grep for `Authorization: Bearer` parsing that doesn't validate signature: `jwt.decode(` without `verify=True` / `jwt.verify(`.
- Grep for CORS wildcards on authenticated endpoints: `Access-Control-Allow-Origin: *` alongside `Access-Control-Allow-Credentials: true`.

**Concrete examples**:

- `GET /api/users/{id}/orders` returns any user's orders when the caller supplies any id — missing `WHERE user_id = :current_user`.
- Admin panel gated by `if (role === "admin")` in React; the underlying API has no server-side check.
- Forced browsing: `/admin/config` returns 200 for unauthenticated callers because the middleware was only mounted on `/admin/users`.

**Remediation pointer**: deny-by-default ACL, per-object ownership checks in the data layer, never trust client-side role state. Record denials in audit log.

## A02:2021 — Cryptographic Failures

**Definition**: Sensitive data exposed through missing/weak/misconfigured crypto — in transit, at rest, or in memory.

**Detection patterns**:

- Grep for weak algorithms: `MD5`, `SHA1`, `DES`, `RC4`, `Blowfish`, `md5\(`, `hashlib\.sha1`, `CryptoJS\.MD5`, `createHash\(["']md5["']\)`.
- Grep for hardcoded keys/IVs: `AES_KEY\s*=\s*["'][A-Za-z0-9+/=]{16,}`, `iv\s*=\s*b?["'][^"']+["']`, `password\s*=\s*["'][^"']+["']` in non-test paths.
- Grep for non-HTTPS endpoints in config: `http://` in production config files, `verify=False` on `requests.get`, `rejectUnauthorized: false` on Node TLS.
- Grep for password hashes without salt/work factor: `hashlib\.sha256\(password`, `crypto\.createHash\(["']sha256["']\)\.update\(password`, or bcrypt with work factor \<10.
- Grep for secrets in logs: `logger\.(debug|info).*password`, `console\.log.*token`, `print.*api_key`.

**Concrete examples**:

- `User.password = hashlib.md5(plain).hexdigest()` — MD5 for password storage, no salt, no work factor.
- TLS disabled for internal service-to-service calls because "we're inside the VPC" — MITM inside the VPC is still a vulnerability class.
- AES-CBC with a fixed IV reused across messages — enables IV-reuse plaintext recovery.

**Remediation pointer**: bcrypt/argon2/scrypt for passwords with cost ≥12, AES-GCM with random IV per message, TLS 1.2+ enforced everywhere, secrets from vault not config files.

## A03:2021 — Injection

**Definition**: Untrusted data is interpreted as code/commands — SQL, NoSQL, OS command, LDAP, XPath, ORM, expression languages, template engines.

**Detection patterns**:

- Grep for string concatenation into SQL: `["']SELECT.*["']\s*\+`, `f["']SELECT.*\{`, `execute\([^,]+\+`, `\.raw\(.*\$\{`.
- Grep for `exec`/`system`/`shell`: `os\.system\(`, `subprocess\..*shell=True`, `child_process\.exec\(`, `Runtime\.exec\(` with any variable input.
- Grep for `eval`: `\beval\(`, `Function\(`, `setTimeout\([^,]*["']`, `document\.write\(`.
- Grep for template-engine misuse: `render\(.*\+\s*user`, `Template\(.*\+`, Jinja `{% raw %}` around user input.
- Grep for unsanitized LDAP/XPath: `ldap_search\(.*\+`, `xpath\(.*\+`, `evaluate\(.*\+`.
- Grep for HTTP header injection: `redirect\(` / `Location:` headers built from request data.

**Concrete examples**:

- `cursor.execute(f"SELECT * FROM users WHERE name = '{name}'")` — classic SQL injection, not parameterized.
- `os.system(f"convert {user_file} output.png")` — shell metacharacter injection via filename.
- Express `res.send('<h1>' + req.query.name + '</h1>')` — reflected XSS.

**Remediation pointer**: parameterized queries always, shell execution with `args` array not `shell=True`, contextual output encoding (HTML/JS/URL), allow-list validation at boundaries.

## A04:2021 — Insecure Design

**Definition**: Missing or ineffective control *by design* — not a bug, but a missing threat model. Can't be patched after the fact.

**Detection patterns**:

- Grep for missing rate limits on auth endpoints: `login`, `reset-password`, `signup` routes without `rate_limit` / `throttle` middleware.
- Grep for password reset flows with predictable tokens: `Math\.random\(`, `random\.randint\(`, timestamp-based tokens in `reset_token =`.
- Grep for business logic that trusts client-computed totals: `amount = req.body.total`, `price = request.json\["price"\]`.
- Grep for TOCTOU races: `if (file.exists()) { ... file.read() }` without lock; `if (balance >= amount) { balance -= amount }` without transaction.
- Grep for missing CAPTCHA/MFA on sensitive actions: password reset, money transfer, account deletion.

**Concrete examples**:

- Password reset flow emits a link containing a 6-digit code with no rate limit — brute-forceable in minutes.
- Shopping cart uses client-supplied `price` field; attacker edits request to pay $0.
- Money transfer endpoint reads-balance then writes-new-balance without row lock — double-spend via concurrent requests.

**Remediation pointer**: threat model before implementation, use secure design patterns (Defense-in-Depth, Fail Secure, Least Privilege), reference an ASVS checklist during spec review, cost/frequency limits on expensive actions.

## A05:2021 — Security Misconfiguration

**Definition**: Servers/frameworks/libraries deployed with insecure defaults, exposed admin interfaces, verbose errors, or outdated components.

**Detection patterns**:

- Grep for stack traces leaked to users: `DEBUG\s*=\s*True` in Django/Flask settings, `app\.use\(errorhandler\(` without production branch, `NODE_ENV` not pinned.
- Grep for default credentials: `admin/admin`, `root/root`, `postgres/postgres` in config, compose files, init scripts.
- Grep for exposed management endpoints: `/actuator`, `/metrics`, `/debug`, `/phpmyadmin`, `/.git/`, `/.env` with no auth.
- Grep for permissive security headers: missing `Content-Security-Policy`, `X-Frame-Options`, `Strict-Transport-Security`, `X-Content-Type-Options`.
- Grep for wildcard firewall/ingress: `0.0.0.0/0` in CloudFormation / Terraform / k8s NetworkPolicy, `allowAll: true`.

**Concrete examples**:

- Production API runs with `DEBUG=True`; 500s expose full Python tracebacks including paths and env vars.
- Kubernetes Ingress exposes `/prometheus` with no auth — attacker scrapes metrics and identifies internal hostnames.
- S3 bucket policy `Principal: "*"` with `Action: s3:GetObject` — intended for a few files, applies to all.

**Remediation pointer**: infrastructure-as-code with secure defaults, periodic config audits (CIS Benchmarks, ScoutSuite, Prowler), strict CSP and HSTS, disabled debug in prod, locked-down admin interfaces.

## A06:2021 — Vulnerable and Outdated Components

**Definition**: Dependencies (direct and transitive) with known CVEs not patched, EOL runtimes, unmaintained libraries.

**Detection patterns**:

- Grep manifest files for old pinned versions: `package.json`, `package-lock.json`, `requirements.txt`, `Pipfile.lock`, `Cargo.lock`, `go.sum`, `pom.xml`, `Gemfile.lock`.
- Run SCA tools: `npm audit`, `pip-audit`, `cargo audit`, `govulncheck`, `bundler-audit`, `trivy fs .`, `grype dir:.`.
- Grep for EOL runtimes: Python 2.x, Node ≤16, Java 8, PHP 7.x, Ruby 2.x in CI configs and Dockerfiles.
- Grep `Dockerfile` for unpinned base images: `FROM node:latest`, `FROM python`, `FROM ubuntu`.
- Grep for archived/unmaintained repos — check the project README and last commit date before adding any new dep.

**Concrete examples**:

- `log4j 2.14` pinned in `pom.xml` — CVE-2021-44228 (Log4Shell) RCE.
- `requests==2.6.0` pinned for 8 years — multiple CVEs including certificate validation bypass.
- `FROM node:14` Dockerfile — Node 14 EOL April 2023; no security patches applied.

**Remediation pointer**: SBOM generation, automated SCA in CI (fail build on critical CVEs), Dependabot/Renovate for PRs, pin base images by digest, remove unused deps (they still count).

## A07:2021 — Identification and Authentication Failures

**Definition**: Weaknesses in identity proofing, session management, credential recovery — covers broken login flows and session hijacking.

**Detection patterns**:

- Grep for sessions that never expire: `expires: null`, `maxAge: Infinity`, `session_lifetime = 0`.
- Grep for session IDs passed in URLs: `?sessionid=`, `?jwt=`.
- Grep for missing lockout / rate limit on login: `def login(` with no rate_limit decorator, no failed-attempt counter.
- Grep for weak password policy: `min_length < 8`, no complexity check, no breach-list check (haveibeenpwned API).
- Grep for JWTs without algorithm pinning: `jwt.decode(token, key)` missing `algorithms=["RS256"]` (allows `alg: none` attack).
- Grep for custom password hashing: `sha256(password + salt)` — should use bcrypt/argon2.

**Concrete examples**:

- Login endpoint accepts unlimited attempts → credential stuffing wipes out the account base.
- JWT verified without `algorithms=` argument → attacker sends `{"alg":"none"}` and bypasses signature check.
- Session cookie lacks `Secure`, `HttpOnly`, `SameSite=Lax` → XSS theft, MITM, CSRF.

**Remediation pointer**: MFA for privileged accounts, rate limiting + lockout on login, bcrypt/argon2 with pepper, session cookie flags, JWT algorithm pinning, OAuth2/OIDC over custom auth.

## A08:2021 — Software and Data Integrity Failures

**Definition**: Code and data consumed without integrity checks — unsigned updates, untrusted CI plugins, insecure deserialization.

**Detection patterns**:

- Grep for unsafe deserialization: `pickle\.loads\(`, `yaml\.load\(` without `Loader=SafeLoader`, `ObjectInputStream\.readObject\(`, `Marshal\.load\(` with user input, `unserialize\(` in PHP.
- Grep for package downloads without signature/hash: `curl .* | sh`, `wget .* | bash`, `npm install` without `--ignore-scripts` in CI, missing `integrity=` in `package-lock.json`.
- Grep for CI step that executes arbitrary user branches: `uses: <action>@master` / `@main` instead of pinned SHA in GitHub Actions.
- Grep for auto-update channels without signing: `update.downloadUrl`, `fetch('https://...').then(r => r.text()).then(eval)`.
- Grep for disabled TLS verification during download: `curl -k`, `wget --no-check-certificate`, `NODE_TLS_REJECT_UNAUTHORIZED=0`.

**Concrete examples**:

- CI step `uses: actions/checkout@main` — upstream repo hijacked, CI runs attacker's code on next build.
- Python worker deserializes task payloads via `pickle.loads` — malicious payload executes arbitrary code on the worker.
- Auto-updater downloads installer over HTTP without signature — attacker on hostile network swaps binaries.

**Remediation pointer**: sign artifacts (Sigstore, cosign), pin CI actions to commit SHA, safe deserializers only (JSON, `yaml.safe_load`), verify hashes before execution, SLSA framework for supply chain.

## A09:2021 — Security Logging and Monitoring Failures

**Definition**: Insufficient logging, monitoring, or alerting allows breaches to go undetected.

**Detection patterns**:

- Grep for silent exception swallowing: `except:\s*pass`, `catch\s*\([^)]*\)\s*\{\s*\}`, `.catch\(\(\)\s*=>\s*\{\}\)`.
- Grep for auth events without audit log: `login`, `logout`, `password_reset`, `role_change` handlers that don't call an audit logger.
- Grep for missing structured logging: raw `print` / `console.log` in server code (breaks SIEM ingestion).
- Grep for PII in logs: `logger.info.*user.email`, `logger.debug.*credit_card` — shouldn't log, but also shouldn't fail silently.
- Grep for absent log-level guards on hot paths: `logger.debug(expensive_call())` without `isEnabledFor(DEBUG)` check.

**Concrete examples**:

- Failed logins logged to `stderr` without user/IP, never aggregated — a credential-stuffing attack runs for a week undetected.
- Admin panel changes have no audit trail — investigating who disabled a safety check takes days of git archaeology.
- Application logs only app-level events; reverse proxy logs rotate after 24h — incident 3 days old has no request data.

**Remediation pointer**: structured logs (JSON) to central SIEM, retain ≥90 days, alert on: auth failures per IP, privilege escalations, unusual request patterns. Test detection with red-team exercises.

## A10:2021 — Server-Side Request Forgery (SSRF)

**Definition**: Server fetches a URL supplied by the user — attacker points it at internal services or cloud metadata endpoints.

**Detection patterns**:

- Grep for HTTP clients fed with user-supplied URLs: `requests\.get\(request`, `fetch\(req\.body\.url`, `httpClient\.get\(user_input`, `urllib\.urlopen\(`.
- Grep for image/PDF preview features: `load_image_from_url`, `render_pdf_from_url`, `webhook_url` fields.
- Grep for cloud metadata exposure: `169\.254\.169\.254`, `metadata\.google\.internal`, `169\.254\.170\.2` in allow-lists or proxies.
- Grep for missing URL scheme allow-lists: `requests\.get\(url` where `url` is unchecked — attacker can pass `file://`, `gopher://`, `ftp://`.
- Grep for redirect-follow without allow-list: HTTP client with `allow_redirects=True` and no hostname check after redirect.

**Concrete examples**:

- Avatar uploader accepts a URL, server fetches it — attacker supplies `http://169.254.169.254/latest/meta-data/iam/security-credentials/` and exfiltrates AWS credentials.
- Webhook feature POSTs to any user-supplied URL — used as an internal port scanner via response timing.
- PDF-from-URL feature follows `file:///etc/passwd` redirects — reads arbitrary local files.

**Remediation pointer**: allow-list destination hostnames, deny RFC1918 + link-local + loopback, resolve DNS once and pin the IP to prevent TOCTOU, use a dedicated network segment for outbound fetchers (no metadata service access), strip redirect chains.
