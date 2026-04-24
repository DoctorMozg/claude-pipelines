# Trust-Boundary Patterns

Used by Phase 1 (Scope Intelligence Gate) at T2+ tier to identify which changed files cross or mutate a trust boundary. A trust boundary is any point where data, control, or identity moves between two principals with different trust levels.

Phase 1 searches changed file content for these patterns to populate the `trust_boundary_delta` section of `scope.md`.

## Python / FastAPI

| Pattern                                                   | Boundary type                                      |
| --------------------------------------------------------- | -------------------------------------------------- |
| `@app.get`, `@app.post`, `@router.get`, `@router.post`    | Ingress — public route                             |
| `Depends(`                                                | Ingress — dependency injection (check if auth dep) |
| `OAuth2PasswordBearer`, `HTTPBearer`, `HTTPBasic`         | Auth — credential extraction                       |
| `SessionMiddleware`, `HTTPSRedirectMiddleware`            | Auth — session management                          |
| `Request.cookies`, `Request.headers.get("Authorization")` | Auth — credential consumption                      |

## Python / Django

| Pattern                                        | Boundary type                   |
| ---------------------------------------------- | ------------------------------- |
| `@login_required`, `@permission_required`      | Auth — access control decorator |
| `permission_classes`, `authentication_classes` | Auth — DRF auth guard           |
| `@csrf_exempt`                                 | Auth — CSRF protection removal  |
| `post_save`, `pre_delete` (signals)            | Data — side-effect boundary     |
| `ContentType`, `GenericForeignKey`             | Data — polymorphic relation     |

## TypeScript / Express

| Pattern                    | Boundary type                    |
| -------------------------- | -------------------------------- |
| `router.use(`, `app.use(`  | Ingress — middleware chain       |
| `passport.authenticate(`   | Auth — strategy invocation       |
| `jwt.verify(`, `jwt.sign(` | Auth — token validation/issuance |
| `req.user`, `req.session`  | Auth — identity propagation      |
| `cors(`, `helmet(`         | Ingress — policy boundary        |

## TypeScript / Next.js

| Pattern                                           | Boundary type                   |
| ------------------------------------------------- | ------------------------------- |
| `getServerSideProps`                              | Ingress — SSR data fetch        |
| `getStaticProps`                                  | Ingress — build-time data fetch |
| `middleware.ts` or `_middleware.ts`               | Auth — edge middleware          |
| `withIronSessionApiRoute`, `getSession(`          | Auth — session read             |
| `export default function handler` in `pages/api/` | Ingress — API route             |

## Go

| Pattern                           | Boundary type               |
| --------------------------------- | --------------------------- |
| `context.WithValue(`              | Auth — identity propagation |
| `r.Use(` (chi/gorilla)            | Ingress — middleware        |
| `grpc.UnaryInterceptor(`          | Ingress — gRPC interceptor  |
| `http.HandleFunc(`, `mux.Handle(` | Ingress — route handler     |

## Generic (any language)

Any file that imports or calls any of these symbols crosses a trust boundary:

- Auth: `jwt`, `bcrypt`, `argon2`, `pbkdf2`, `session`, `cookie`, `auth`, `oauth`, `saml`, `ldap`, `sso`, `oidc`
- Crypto: `crypto`, `encrypt`, `decrypt`, `hmac`, `hashlib`
- Secrets: `secretsmanager`, `vault`, `keyVault`, `ssm.GetParameter`
- Admin/IAM: `iam.`, `rbac.`, `acl.`, `RoleBinding`, `grant_permission`

## Database — ORM

| Pattern                                          | Boundary type                 |
| ------------------------------------------------ | ----------------------------- |
| `ForeignKey(User` or `ForeignKey('User'`         | Data — user-keyed relation    |
| `.filter(user=request.user)`                     | Data — per-user row filter    |
| `.filter(tenant_id=`, `.filter(organization_id=` | Data — multi-tenant isolation |
| Row-level security definitions in migrations     | Data — DB-enforced isolation  |

## Network Egress

Any outbound call crosses an egress boundary:

| Pattern                                                | Type                       |
| ------------------------------------------------------ | -------------------------- |
| `requests.get(`, `requests.post(`, `requests.request(` | HTTP egress (Python)       |
| `httpx.get(`, `aiohttp.ClientSession(`                 | HTTP egress (Python async) |
| `fetch(`, `axios.get(`, `axios.post(`                  | HTTP egress (JS/TS)        |
| `http.NewRequest(`, `http.Get(`                        | HTTP egress (Go)           |
| `grpc.Dial(`                                           | gRPC egress                |
| `subprocess.run(`, `os.system(`, `child_process.exec(` | Process egress             |
| `smtplib.SMTP(`, `nodemailer.createTransport(`         | Email egress               |
