# Oracle Cloud Always Free VM Provisioning — Mahika runbook

**Purpose:** Stand up the Always Free Postgres host that Mahika talks to.
**Time:** ~25 minutes (mostly waiting for Oracle to provision).
**Cost:** ₹0/month forever (Oracle Always Free tier).
**Output:** A reachable Postgres 16 instance with the Mahika schema applied.

> ⚠️ **One-time only.** Sir does this once. Once the VM is up and you've
> got the public IP in your `.env`, every other phase is automated code
> that talks to Postgres remotely.

---

## §1 — Pre-flight checklist

Tick before starting:

- [ ] Oracle Cloud account created (sign up at https://signup.cloud.oracle.com/ with a credit card; nothing is ever charged on Always Free, but they need the card for identity verification)
- [ ] You can log in to https://cloud.oracle.com and reach the dashboard
- [ ] You've decided on a region. **Recommended: Mumbai (`ap-mumbai-1`)** — lowest latency to your Indian machines + India data-residency for SAFE-T evidence.
- [ ] You have ~25 min of uninterrupted time (VM provisioning + Postgres install)

---

## §2 — Create the VM

1. Sign in to Oracle Cloud Console: https://cloud.oracle.com
2. Top-left **☰ menu** → **Compute** → **Instances**
3. Make sure the region selector (top-right) shows **Mumbai (`ap-mumbai-1`)** or your chosen region.
4. Click **Create instance**.
5. Fill these fields exactly:

   | Field | Value |
   |---|---|
   | Name | `mahika-pg` |
   | Compartment | (leave default) |
   | Image | Click **Edit** under "Image and shape". Select **Canonical Ubuntu 22.04**. |
   | Shape | Click **Change shape**. Select **Ampere → VM.Standard.A1.Flex**. Set **OCPUs: 2** and **Memory (GB): 12**. (We're entitled to up to 4 OCPU + 24 GB free total across all VMs — we'll save the rest for future growth.) |
   | Networking | "Create new virtual cloud network" — accept defaults. **Public IPv4 address: Assign a public IPv4 address.** |
   | SSH keys | **Generate SSH key pair for me** — download BOTH the private and public key. Save the private key (`ssh-key-*.key`) to `C:/Users/DELL/.ssh/oracle-mahika.key`. Set permissions: `icacls "C:\Users\DELL\.ssh\oracle-mahika.key" /inheritance:r /grant:r "DELL:F"` |

6. Click **Create**. Wait ~3-5 min for the VM to provision.
7. Once it's running, copy the **Public IP Address** from the instance details page. We'll call this `$VM_IP` from here on.

---

## §3 — Open Postgres port (5432) in Oracle's firewall

By default the VM is locked down. Open just the port we need.

1. From the instance page → **Primary VNIC → Subnet** → **Security Lists** → click the default security list.
2. **Add Ingress Rule**:
   - Source CIDR: `0.0.0.0/0` (open to internet — fine because Postgres password auth is strong)
   - IP Protocol: `TCP`
   - Destination Port Range: `5432`
   - Description: `Mahika postgres (Sir)`
3. Save.

---

## §4 — SSH into the VM + install Postgres 16

From a Windows PowerShell on the runner machine:

```powershell
ssh -i C:\Users\DELL\.ssh\oracle-mahika.key ubuntu@$VM_IP
```

You're now on the VM. Run this block (paste as one chunk):

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Add the official Postgres apt repo (gives us PG 16, the LTS we want)
sudo apt install -y curl ca-certificates
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
  --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc
sudo sh -c 'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
  https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
  > /etc/apt/sources.list.d/pgdg.list'
sudo apt update
sudo apt install -y postgresql-16 postgresql-contrib-16

# Allow remote connections
sudo sed -i "s/^#listen_addresses = 'localhost'/listen_addresses = '*'/" \
  /etc/postgresql/16/main/postgresql.conf
echo "host    all             all             0.0.0.0/0               scram-sha-256" \
  | sudo tee -a /etc/postgresql/16/main/pg_hba.conf

# Open port at the OS firewall level too (Oracle has iptables enabled)
sudo iptables -I INPUT -p tcp --dport 5432 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || sudo iptables-save | sudo tee /etc/iptables/rules.v4

# Restart Postgres to pick up the config changes
sudo systemctl restart postgresql
sudo systemctl enable postgresql
```

---

## §5 — Create the Mahika database + user

Still on the VM (still ssh'd in):

```bash
# Set a strong password for the new mahika user.
# Use a password manager — you'll paste this into the runner's .env file next.
MAHIKA_DB_PW=$(openssl rand -base64 24 | tr -d '/+= ' | head -c 24)
echo "Mahika DB password (save this): $MAHIKA_DB_PW"

# Create user + database
sudo -u postgres psql <<EOF
CREATE USER mahika WITH PASSWORD '$MAHIKA_DB_PW';
CREATE DATABASE mahika OWNER mahika;
\c mahika
GRANT ALL PRIVILEGES ON DATABASE mahika TO mahika;
GRANT ALL PRIVILEGES ON SCHEMA public TO mahika;
EOF

# Verify
sudo -u postgres psql -c "\du" | grep mahika
sudo -u postgres psql -c "\l" | grep mahika
```

**Copy the printed password.** You'll paste it into `MAHIKA_DB_PASSWORD` in your runner's `.env` next.

Log out of the VM (`exit`).

---

## §6 — Update the runner's `.env`

Back on the runner machine (where the agent lives):

```powershell
cd "C:\Projects\Amazon Systems Design\agent"
cp .env.example .env
notepad .env
```

Fill in:

```
MAHIKA_DB_HOST=<the VM_IP from §2>
MAHIKA_DB_PORT=5432
MAHIKA_DB_NAME=mahika
MAHIKA_DB_USER=mahika
MAHIKA_DB_PASSWORD=<the password from §5>
```

Save + close.

---

## §7 — Apply the schema migrations

```powershell
cd "C:\Projects\Amazon Systems Design\agent"
python -m pip install -e .
python -m mahika.db.migrate
```

Expected output:
```
Mahika DB: 1 migration(s) pending:
  - 001_init_schema.sql
Mahika DB: applying 001_init_schema.sql...
Mahika DB: all migrations applied.
```

---

## §8 — Smoke test

```powershell
python -c "from mahika.db.connection import db_engine; \
  from sqlalchemy import text; \
  print(db_engine.connect().execute(text('SELECT version()')).scalar())"
```

You should see `PostgreSQL 16.x ...`. **That's success.** Mahika is now talking to her cloud DB.

---

## §9 — Verify heartbeat works

```powershell
python -c "from mahika.runner.heartbeat import claim_active, am_i_active; \
  print('claimed:', claim_active(notes='setup smoke-test')); \
  print('am_i_active:', am_i_active())"
```

Expected:
```
claimed: True
am_i_active: True
```

---

## §10 — What's next

Once you're at this point:

- ✅ Oracle VM is up and reachable
- ✅ Postgres has the Mahika schema
- ✅ The agent on your runner can read/write it
- ✅ Heartbeat works → you're the active runner

You're done with the Oracle side of Phase 1. The next external blocker
is **SP-API registration** — see `sp_api_registration_checklist.md`.

After that's clear, Phase 4 (Mahika Core) can be built end-to-end.

---

## §11 — Troubleshooting

**"Connection timed out" when migrating from Windows**
- The Oracle Security List rule (§3) probably wasn't saved correctly.
  Recheck under VNIC → Subnet → Security Lists.
- Alternative: the VM's iptables config didn't persist after reboot. Re-ssh
  and rerun `sudo iptables -I INPUT -p tcp --dport 5432 -j ACCEPT`.

**"FATAL: password authentication failed"**
- The `.env` password has a special character that got mangled by the shell.
  Regenerate via §5 — use only alphanumerics. (The default openssl one
  filters them out already.)

**"VM was reclaimed by Oracle"**
- Oracle reclaims Always Free VMs that are idle for 7+ days. Workaround:
  set up a tiny systemd timer that pings Postgres every hour to keep
  activity logged. Add `crontab -e` line:
  ```
  0 * * * * sudo -u postgres psql -c "SELECT 1" > /dev/null
  ```
