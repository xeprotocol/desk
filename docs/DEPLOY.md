# Deploying the XE desk

One codebase, two deployments: staging at `desk.test.network` (both hosts set to it), production at `bounty.xe.network` + `support.xe.network`. Both read the testnet node until genesis. Everything below runs on the VPS under Docker Compose; nothing runs on a laptop.

## 0. Prerequisites on the VPS

- Ubuntu 22.04/24.04, 2 vCPU, 4 GB, 40 GB disk.
- Docker Engine 24+ with the compose plugin: `curl -fsSL https://get.docker.com | sh`.
- DNS `A`/`AAAA` for both hosts pointing at the VPS.
- Caddy for TLS: `apt install caddy`, then `/etc/caddy/Caddyfile`:

  ```
  bounty.xe.network, support.xe.network {
      reverse_proxy 127.0.0.1:8010
      encode gzip
      header Strict-Transport-Security "max-age=31536000"
  }
  ```

  `systemctl reload caddy`. Caddy provisions both certificates and forwards the `Host` header, which is how the app knows which front door it is answering.

## 1. Get the code

```sh
sudo mkdir -p /opt/desk && sudo chown $USER /opt/desk
git clone <repo> /opt/desk
cd /opt/desk
cp .env.example .env
mkdir -p secrets
```

Edit `.env`:

- `POSTGRES_PASSWORD`: long random, ASCII letters and digits only (it is spliced into a URL and a `.env` line; `%`, `@`, `/`, `:`, `$`, `#` and non-ASCII all have meanings there).
- `PUBLIC_BASE_URL`, `DESK_BOUNTY_HOST`, `DESK_SUPPORT_HOST`, `WEBAUTHN_RP_ID`: production values as in the example; for staging set both hosts to `desk.test.network` and the RP id to `test.network`.
- `DESK_SIGNER_PASSPHRASE`: long random (12+ chars); it encrypts the keyfile that holds the log key and the vault key.
- `GITHUB_TOKEN`: a fine-grained token with Issues read/write and Pull requests read on `xeprotocol/xe`, `xeprotocol/dao`, `xeprotocol/sdk`, and Issues read on the private `xeprotocol/core`. `GITHUB_BOT_LOGIN`: the account it belongs to.
- `GITHUB_WEBHOOK_SECRET`: long random; the same string goes in the GitHub webhook.
- `INTERNAL_TRACKER_URL`: already `https://github.com/xeprotocol/core/issues/{ref}`; change only if the tracker moves (and change `internal.repo` in `config/desk.yaml` with it).
- `SMTP_*`: optional; without it, invite links are printed instead of emailed.

## 2. Build and test

```sh
cd /opt/desk
export GIT_COMMIT=$(git rev-parse --short HEAD)
docker compose build
```

Pure tests (no database, no network): wire-format checks, signed requests, the authorisation matrix, the status machine, the vault, TOTP against the RFC vector, config vocabularies, the triage parser against the real doc, templates and copy lint.

```sh
docker compose run --rm --no-deps -v $PWD/tests:/app/tests app \
  sh -c "pip install -q pytest pytest-asyncio && pytest -q tests/test_xe_wire.py tests/test_desk_core.py tests/test_triage.py tests/test_templates.py"
```

Database tests (a scratch database the tests wipe):

```sh
docker compose up -d --wait db            # --wait: returns once Postgres is healthy, not merely started
docker compose exec db psql -U desk -d desk -c "CREATE DATABASE desk_test"
docker compose run --rm -v $PWD/tests:/app/tests \
  -e DESK_TEST_DATABASE_URL=postgresql+asyncpg://desk:$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2)@db:5432/desk_test \
  app sh -c "pip install -q pytest pytest-asyncio && pytest -q tests/test_db.py"
```

`test_triage_import_of_the_real_doc` imports the whole triage into the scratch database and checks the counts; if it fails, do not import into the real one.

Lint, if you want it: `docker compose run --rm --no-deps app sh -c "pip install -q ruff && ruff check desk tests"`.

## 3. Keys, migrate, first user

The services mount `secrets/` read-only, so the one write it ever gets is done with plain `docker run` against the built image, not through compose:

```sh
docker run --rm -v $PWD/secrets:/app/secrets --env-file .env desk-app desk keys init
ls -l secrets/signer.json                  # -rw------- root
```

Back up `secrets/signer.json` and the passphrase separately. Losing the vault key loses every private report; losing the log key means future entries are unsigned (the chain still verifies by hash).

```sh
docker compose up -d                       # db, migrate (one-shot), app, worker
docker compose logs migrate                # "Running upgrade -> 0001"
docker compose exec app desk users add cto@xe.network --name "CTO" --roles reviewer,tier,treasurer,admin
```

Open the printed invite link in a browser within seven days; it signs you in once. On `/team/account`, add a passkey, and set up a TOTP code as the fallback. Then `/team/users` to add the rest of the team (each gets an invite link), granting `tier` only to the CTO and named delegates.

## 4. Import

Order matters: GitHub first (so tickets exist with their threads and reporters), then the triage (which sets the facts and status on them), then the internal tracker (which confirms or adds internal refs and moves status from the tracker's state), then labels.

```sh
docker compose exec app desk import-github            # every repo in config/desk.yaml; minutes, rate-limit aware
docker compose exec app desk import-triage --dry-run  # prints the 90 rows as parsed; read it
docker compose exec app desk import-triage            # applies them; re-runnable
docker compose exec app desk import-internal          # reads xeprotocol/core; `xe#8` in a title links it to xe issue 8
docker compose exec app desk github-labels            # creates the desk's status labels on each repo
```

For the three email reports, put their bodies in a JSON file and pass `--emails /app/secrets/emails.json` (`{"E1": "...", "E2": "...", "E3": "..."}`); the bodies are sealed on write. Add payout addresses on the ticket pages when the reporters send them.

Then the worker's first `push` run (within a minute) puts the status labels on the issues and closes the ones the desk has closed. Check `/team/outbox`: it lists every ticket that was fixed but whose reporter has not been told. Work through it with the `patched` template.

## 5. Webhook

In each repo, Settings → Webhooks → Add: payload URL `https://bounty.xe.network/v1/github/webhook`, content type `application/json`, secret as in `.env`, events: Issues, Issue comments, Pull requests. On `xeprotocol/core` the same webhook with Issues only: when the CTO closes an internal ticket, the public ticket it names goes to `patched` and into the outbox within seconds. The poll every two minutes covers anything the webhook misses.

## 6. Agent tokens

```sh
docker compose exec app desk tokens issue cto@xe.network claude-fable-5.1 --label nightly --scopes read:public,write:notes,write:proposals,write:patch-refs --days 90
```

Or on `/team/tokens`. The token is shown once. An agent then reads `https://bounty.xe.network/llms.txt` and calls `/v1` with `Authorization: Bearer desk_…`.

## 7. Day to day

```sh
docker compose exec app desk health          # node, log head, keys, hosts, config hashes
docker compose exec app desk verify-log      # replays the chain; non-zero exit on a break
docker compose exec app desk export-triage --out /app/blobs/triage-$(date +%F).md
docker compose exec app desk copy-lint       # fails on a kill-list phrase in public copy or templates
docker compose logs -f worker                # github poll, outbox, push, health, anchors
```

Upgrade: `git pull && export GIT_COMMIT=$(git rev-parse --short HEAD) && docker compose build && docker compose up -d`. The `migrate` service runs before `app` and `worker` start.

## 8. If a page is blank

Caddy answers an empty 502 when nothing is listening on 8010, and an empty 200 if it has no site block for the host; both look like a white page. In order:

```sh
docker compose ps                                   # app and worker "Up", migrate "Exited (0)"
docker compose logs --tail=50 app                   # the last lines say "Uvicorn running on 0.0.0.0:8000"
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8010/v1/health   # 200 from the app itself
curl -sI -H 'Host: bounty.xe.network' http://127.0.0.1:8010/ | head -3    # 200 text/html
caddy validate --config /etc/caddy/Caddyfile && systemctl status caddy --no-pager | head -5
curl -sI https://bounty.xe.network/ | head -3       # through Caddy
```

If `docker compose ps` shows no `app`, it was never started: `docker compose up -d`. If `app` is restarting, the log says why; the usual causes are a wrong `POSTGRES_PASSWORD` (the URL is built from it) or `migrate` having failed. If the app answers on 8010 but the domain does not, the problem is Caddy or DNS, not the desk.

## 9. Backups

`pgdata` (Postgres) and `blobs` (attachments) are compose volumes; `secrets/` is a bind mount. A nightly `pg_dump` plus a copy of `secrets/signer.json` is the whole backup. Without the keyfile, the dump's private bodies are unreadable, which is the point.
