# Deploying Spacio to spacio.cc (Phase 5)

One t3.micro/t2.micro EC2 instance (Docker Compose: api + mongo) behind
nginx on the host (TLS via Let's Encrypt), listing photos in S3. See
`docs/DOCUMENTATION.md` §5 for the design rationale (EC2 over a managed
option, chosen for the infra learning value).

## 0. Prerequisites (you do this part)

1. Create an AWS account at aws.amazon.com if you haven't.
2. Create an IAM user for CLI use (root credentials should never touch a
   terminal): AWS Console → IAM → Users → Create user → attach
   `AdministratorAccess` for now (fine for a single personal project; a
   scoped policy is a nice follow-up but not worth blocking on) → Security
   credentials tab → Create access key → "Command Line Interface (CLI)".
3. On your machine, run `aws configure` yourself (install via
   `brew install awscli` first) and paste the access key / secret / a
   default region (e.g. `us-east-1`) when prompted. **Do not paste these
   into the chat** — running it yourself keeps them out of the
   conversation and out of Claude's context entirely; the credentials just
   land in `~/.aws/credentials`, which any `aws`/boto3 call on this machine
   (including ones run for you) will pick up automatically.
4. Generate an SSH key pair for the instance if you don't already have one
   you want to reuse: `aws ec2 create-key-pair --key-name spacio-deploy
   --query 'KeyMaterial' --output text > ~/.ssh/spacio-deploy.pem && chmod
   400 ~/.ssh/spacio-deploy.pem`.

Once `aws sts get-caller-identity` succeeds locally, the rest of this
document is `aws` CLI commands that can be run directly (by you, or by
Claude in this session against your configured credentials) — each is a
real, billable AWS action, so review before running.

## 1. S3 bucket for listing photos

```bash
BUCKET=spacio-listings-<pick-something-unique>   # bucket names are global
REGION=us-east-1

aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"

# Public read on objects only (no listing, no write) — the app writes via
# an IAM role (next section), the browser only ever GETs image URLs.
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false
cat > /tmp/spacio-bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadListingPhotos",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::$BUCKET/listings/*"
  }]
}
EOF
aws s3api put-bucket-policy --bucket "$BUCKET" --policy file:///tmp/spacio-bucket-policy.json
```

## 2. IAM role for the EC2 instance (no static keys on the box)

The instance gets write access to the bucket via an attached IAM role
instead of `AWS_ACCESS_KEY_ID`/`SECRET` env vars — nothing to leak if the
box is compromised, and one less secret to manage in `.env.production`.

```bash
cat > /tmp/spacio-trust-policy.json <<'EOF'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}
EOF
aws iam create-role --role-name spacio-ec2-role --assume-role-policy-document file:///tmp/spacio-trust-policy.json

cat > /tmp/spacio-s3-write-policy.json <<EOF
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:PutObject","s3:GetObject"],"Resource":"arn:aws:s3:::$BUCKET/listings/*"}]}
EOF
aws iam put-role-policy --role-name spacio-ec2-role --policy-name spacio-s3-write \
  --policy-document file:///tmp/spacio-s3-write-policy.json
aws iam create-instance-profile --instance-profile-name spacio-ec2-profile
aws iam add-role-to-instance-profile --instance-profile-name spacio-ec2-profile --role-name spacio-ec2-role
```

boto3 (and thus `app/services/image_storage.py`) picks up role credentials
automatically via the instance metadata service — no code change and no
`.env.production` entry beyond `S3_BUCKET`/`AWS_REGION` needed.

## 3. Security group + EC2 instance

```bash
VPC_ID=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)
SG_ID=$(aws ec2 create-security-group --group-name spacio-sg --description "Spacio web+ssh" \
  --vpc-id "$VPC_ID" --query 'GroupId' --output text)

aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 \
  --cidr "$(curl -s ifconfig.me)/32"    # SSH from your current IP only
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 443 --cidr 0.0.0.0/0

# Ubuntu 24.04 LTS amd64 AMI for the configured region, via SSM's public parameter
AMI_ID=$(aws ssm get-parameters --names \
  /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
  --query 'Parameters[0].Value' --output text)

INSTANCE_ID=$(aws ec2 run-instances --image-id "$AMI_ID" --instance-type t3.micro \
  --key-name spacio-deploy --security-group-ids "$SG_ID" \
  --iam-instance-profile Name=spacio-ec2-profile \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":16}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=spacio}]' \
  --query 'Instances[0].InstanceId' --output text)

aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"

ALLOC_ID=$(aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text)
aws ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOC_ID"
aws ec2 describe-addresses --allocation-ids "$ALLOC_ID" --query 'Addresses[0].PublicIp' --output text
```

Note the printed Elastic IP — it's needed for the DNS step and doesn't
change even if the instance restarts (unlike the default public IP).

## 4. Point spacio.cc at the Elastic IP

In the Spaceship dashboard (where you bought the domain): DNS settings for
`spacio.cc` → add two `A` records: host `@` → the Elastic IP, host `www` →
the same Elastic IP. This is registrar-specific and has no CLI equivalent
here, so it's a manual step. DNS propagation can take a few minutes to a
few hours.

## 5. Provision the instance

```bash
ssh -i ~/.ssh/spacio-deploy.pem ubuntu@<elastic-ip>
```

Then, on the instance (`/opt` is root-owned, so it has to be chowned to the
`ubuntu` user *before* cloning into it — cloning first and chowning via the
setup script afterward, as an earlier draft of this doc had it, fails with
"Permission denied"):

```bash
sudo mkdir -p /opt/spacio && sudo chown ubuntu:ubuntu /opt/spacio
git clone https://github.com/iliyanalibhai/spacio.git /opt/spacio
sudo bash /opt/spacio/deploy/setup-ec2.sh
# log out/in (or `newgrp docker`) so the docker group membership applies
```

Create `/opt/spacio/api/.env.production` (copy `api/.env.example`, fill in
real values — `JWT_SECRET` freshly generated, `COOKIE_SECURE=true`,
`CORS_ORIGINS=https://spacio.cc`, `FRONTEND_URL=https://spacio.cc`,
real Stripe keys, `S3_BUCKET`/`AWS_REGION` from steps 1-2). This file is
gitignored and lives only on the server — never commit it.

## 6. Build the frontend locally and ship the static files up

Building on a 1GB t3.micro is avoidable — do it on your own machine and
copy the result, which also means the instance never needs Node.js
installed:

```bash
# on your machine, from the repo root
cd web && VITE_API_URL=https://spacio.cc npm run build
scp -i ~/.ssh/spacio-deploy.pem -r dist/* ubuntu@<elastic-ip>:/var/www/spacio/
```

Since nginx (step 7) proxies the API's route prefixes and falls through to
these static files for everything else, `VITE_API_URL=https://spacio.cc`
(same origin, no path suffix) is correct — see
`deploy/nginx/spacio.conf`'s comment on why same-origin avoids any
cross-site cookie complications.

## 7. nginx + TLS

On the instance:

```bash
sudo cp /opt/spacio/deploy/nginx/spacio.conf /etc/nginx/sites-available/spacio.conf
sudo ln -sf /etc/nginx/sites-available/spacio.conf /etc/nginx/sites-enabled/spacio.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d spacio.cc -d www.spacio.cc   # rewrites the ssl_certificate lines in place
```

Certbot installs a systemd timer for renewal automatically — nothing
further to schedule.

## 8. Start the app

```bash
cd /opt/spacio
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec api python seed.py   # optional demo data
```

## 9. Verify

Visit `https://spacio.cc` — full golden path (register → verify → create
listing → search → book → pay → review) should work exactly like the
local `docker compose up` stack, just over real TLS with real image
uploads landing in S3. Check `docker compose -f docker-compose.prod.yml
logs -f api` for startup errors.

## Redeploying after a code change

```bash
# on the instance
cd /opt/spacio && git pull
docker compose -f docker-compose.prod.yml up -d --build

# on your machine, only if the frontend changed
cd web && VITE_API_URL=https://spacio.cc npm run build
scp -i ~/.ssh/spacio-deploy.pem -r dist/* ubuntu@<elastic-ip>:/var/www/spacio/
```
