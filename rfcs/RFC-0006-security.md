<!-- markdownlint-disable -->
# RFC-0006 - Segurança

- **Status:** Accepted
- **Autor:** Tiago Ribeiro Navarro de Andrade
- **Criado em:** 2026-07-19
- **Última atualização:** 2026-07-19
- **Versão:** 1.0

---

## Threat Model

None formally modeled. This is stated honestly rather than papered over: the bundle is a local-development demo, and its security posture reflects that — not an omission to be quietly fixed, but a deliberate non-goal (see `rfcs/RFC-0000-project-charter.md`). Anyone deploying this pattern beyond local Docker Compose needs to threat-model their own deployment; this RFC does not attempt to do that for them.

## OAuth

Not used anywhere in the stack.

## JWT

Not used anywhere in the stack.

## RBAC

None. No service in the stack enforces role-based access.

## Gestão de Segredos

All credentials are hardcoded defaults in `infra/compose/docker-compose.yml` / environment variables, with `.env` / `.env.example` as the override mechanism (which ships the same weak defaults):

- MinIO: `minioadmin` / `minioadmin`
- PostgreSQL: `kappa` / `kappa`
- Doris: `root` with an **empty password**
- Cube.js: `CUBEJS_API_SECRET: dev-secret-change-me`

None of these are safe for anything beyond local development.

## Criptografia

No TLS anywhere in the stack — not between services, not for the Kafka broker, not for the Doris/PostgreSQL/Cube.js/Nessie/Flink REST surfaces. All traffic is plaintext on the Docker bridge network.

## Auditoria

No audit logging exists. Docker Compose service logs (`docker compose logs`) are the only trace of activity, and are not structured for audit purposes.

## LGPD

The simulator generates fully synthetic data (Faker-based); no real personal data ever enters the system, so LGPD/GDPR compliance is out of scope by construction rather than by control. This would need to be revisited entirely if this pattern were adapted to handle real user data — none of the security posture above would be acceptable at that point.
