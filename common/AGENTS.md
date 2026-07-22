# AGENTS.md

This file applies to shared Java modules under `common`. It extends the repository-level `AGENTS.md`.

## Modules

- `common-core`: shared response envelopes, page results, exceptions, error codes, and utility types.
- `common-web`: global web concerns such as exception handling.
- `common-db`: MyBatis Plus and database base types/configuration.
- `common-security`: JWT utilities, interceptors, and `UserContext`.
- `common-storage`: Aliyun OSS/local fallback storage abstractions.

## Rules

- Changes here affect multiple services. Keep APIs stable and backward compatible where possible.
- Do not add business-domain behavior to common modules. Common code should stay generic.
- Prefer extending existing shared types over creating duplicate result, exception, auth, or storage helpers in a service.
- When changing `common-security`, inspect all authenticated services for interceptor/header assumptions.
- When changing `common-core` envelopes or error codes, inspect both Java callers and frontend response handling.
- When changing `common-db`, verify mapper/entity behavior in at least one affected service.

## Verification

Run a downstream module build when practical:

```powershell
mvn -pl common/common-core -am test
mvn -pl services/user-service -am test
```

