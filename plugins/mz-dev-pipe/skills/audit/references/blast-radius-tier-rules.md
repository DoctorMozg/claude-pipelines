# Blast-Radius Tier Rules

Used by Phase 1 (Scope Intelligence Gate) to classify each changed file into a blast-radius tier. The overall tier is the maximum tier across all changed files.

## Tier Definitions

### T0 — Documentation / Tests / Config (lowest risk)

Files in this tier have no runtime production impact. Audit can run in condensed/summary mode.

Patterns (any match → T0):

- `*.md`, `*.txt`, `*.rst`
- Paths matching `docs/`, `README*`
- Pure test files: `test_*`, `*_test*`, `*.spec.*`, `*.test.*`
- Lock files: `*.lock`, `package-lock.json`, `yarn.lock`, `Pipfile.lock`
- JSON/YAML config that is not a dependency manifest (e.g. `.prettierrc`, `pyproject.toml` non-deps sections)

### T1 — Application Code (standard risk)

Source files with no T2 or T3 signals. Standard 5-lens review applies.

Patterns (any source file not matching T2 or T3 signals → T1):

- Business logic, utilities, controllers, views not touching auth/crypto/PII/network
- Internal helper modules with no external dependencies or sensitive data

### T2 — Security-Relevant (elevated risk)

Files touching auth, cryptography, PII, external network, or deserialization. STRIDE-delta researcher activates.

Signals (any match in file content or path → T2):

- Auth: `auth`, `login`, `logout`, `session`, `token`, `jwt`, `oauth`, `saml`, `ldap`, `cookie`, `csrf`, `permission`, `middleware`
- Crypto: `bcrypt`, `hashlib`, `crypto`, `encrypt`, `decrypt`, `hash`, `hmac`, `pbkdf2`, `argon2`
- PII field names in models/schemas: `email`, `ssn`, `dob`, `date_of_birth`, `card_number`, `phone`, `address`, `national_id`
- Network egress: `requests.get`, `requests.post`, `fetch(`, `axios`, `http.Client`, `urllib`, `grpc.Dial`, `httpx`
- Subprocess / shell: `subprocess`, `os.system`, `exec(`, `eval(`, `child_process`, `shell=True`
- File-path consumers with user input: `open(`, `Path(`, `fs.readFile`, `os.path.join` combined with request params
- Deserialization: `pickle.loads`, `yaml.load(`, `JSON.parse` on untrusted data, `marshal.loads`, `eval(`
- Dependency manifest changes: `requirements.txt`, `Pipfile`, `package.json`, `go.mod`, `Cargo.toml`, `build.gradle`

### T3 — Regulated / Critical Infrastructure (highest risk)

Files touching multi-tenant isolation, secrets management, regulated data, IAM, or database migrations. All lenses run at maximum intensity; STRIDE-delta is mandatory regardless of T2 flag.

Signals (any match in file content or path → T3):

- Multi-tenant isolation: `tenant_id`, `row_level_security`, `rls`, `.filter(tenant`, `organization_id` as a security filter
- Secrets management: `AWS Secrets Manager`, `secretsmanager`, `vault.read`, `gcp.SecretManager`, `azure.KeyVault`
- Regulated data models: HIPAA PHI field names (`diagnosis`, `medication`, `patient_id`, `mrn`), PCI-DSS (`card_number`, `cvv`, `pan`), SOC2 audit log tables
- IAM / permission management: `iam.`, `RoleBinding`, `grant_permission`, `revoke_permission`, `acl.`, `rbac.`
- Database migration files: `migrations/`, `*_migration*`, `alembic/versions/`, `db/migrate/`

## Tier Computation

```
overall_tier = max(tier(f) for f in changed_files)
```

When a file matches multiple tiers, assign the highest. Write the per-file tier map and the overall tier to `scope.md`.
