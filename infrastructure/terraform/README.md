# Magellon — Production AWS Infrastructure

Terraform-based, multi-region deployment of the Magellon microservices stack.
GPU-intensive workloads (MotionCor) run on a dedicated spot instance; all other
services run on a separate CPU instance. Only the frontend is public-facing.

---

## Architecture

```
                           ┌──────────────────────────────────────┐
                           │           Route 53 (Global)          │
                           │  Failover routing with health checks  │
                           │  Primary → us-east-1                  │
                           │  Secondary → us-west-2  (auto-switch) │
                           └────────────┬─────────────────────────┘
                                        │ DNS
                        ┌───────────────┴──────────────────┐
                        │                                  │
              ┌─────────▼──────────┐            ┌─────────▼──────────┐
              │    us-east-1       │            │    us-west-2        │
              │    PRIMARY         │            │    SECONDARY        │
              └─────────┬──────────┘            └─────────┬──────────┘
                        │                                  │
         ┌──────────────▼──────────────────────────────────▼──────────┐
         │                  (same layout in both regions)              │
         │                                                             │
         │   ┌─────────────────────────────────────────────────────┐  │
         │   │  VPC  10.0.0.0/16                                   │  │
         │   │                                                       │  │
         │   │  ┌──────────────────────┐  ┌──────────────────────┐ │  │
         │   │  │  Public Subnet A      │  │  Public Subnet B     │ │  │
         │   │  │  10.0.1.0/24         │  │  10.0.2.0/24         │ │  │
         │   │  │  ┌──────────────┐    │  │  ┌──────────────┐   │ │  │
         │   │  │  │  ALB         │    │  │  │  NAT GW B    │   │ │  │
         │   │  │  │  + WAF v2    │    │  │  └──────────────┘   │ │  │
         │   │  │  │  + ACM TLS   │    │  └──────────────────────┘ │  │
         │   │  │  │  NAT GW A    │    │                            │  │
         │   │  │  └──────┬───────┘    │                            │  │
         │   │  └─────────┼────────────┘                            │  │
         │   │            │ port 8080 only                           │  │
         │   │  ┌─────────▼────────────────────────────────────┐   │  │
         │   │  │  Private Subnet A  10.0.10.0/24               │   │  │
         │   │  │                                                │   │  │
         │   │  │  ┌─────────────────────────────────────────┐ │   │  │
         │   │  │  │  Main EC2  (t3.xlarge, private IP only) │ │   │  │
         │   │  │  │                                          │ │   │  │
         │   │  │  │  mysql         dragonfly (cache)         │ │   │  │
         │   │  │  │  rabbitmq      nats (JetStream)          │ │   │  │
         │   │  │  │  backend API   web (React/Nginx)         │ │   │  │
         │   │  │  │  ctf_plugin    prometheus + grafana       │ │   │  │
         │   │  │  └──────────────────┬──────────────────────┘ │   │  │
         │   │  └─────────────────────┼──────────────────────── ┘   │  │
         │   │                        │ ports 5672 / 4222 / 6379     │  │
         │   │                        │ (GPU SG → Main SG only)      │  │
         │   │  ┌─────────────────────┼──────────────────────────┐   │  │
         │   │  │  Private Subnet B   │  10.0.11.0/24             │   │  │
         │   │  │                     ▼                            │   │  │
         │   │  │  ┌──────────────────────────────────────────┐  │   │  │
         │   │  │  │  GPU EC2 Spot  (g4dn.xlarge, private IP) │  │   │  │
         │   │  │  │  NVIDIA T4 GPU                           │  │   │  │
         │   │  │  │  magellon_motioncor_plugin only           │  │   │  │
         │   │  │  └──────────────────────────────────────────┘  │   │  │
         │   │  └─────────────────────────────────────────────── ┘   │  │
         │   │                                                         │  │
         │   │  ┌──────────────────────────────────────────────────┐  │  │
         │   │  │  EFS  (elastic throughput, encrypted, backups on) │  │  │
         │   │  │  /magellon   /gpfs   /jobs                        │  │  │
         │   │  │  mounted by BOTH instances                        │  │  │
         │   │  └──────────────────────────────────────────────────┘  │  │
         │   └─────────────────────────────────────────────────────────┘  │
         └─────────────────────────────────────────────────────────────────┘
```

### Traffic Flow

```
User → Route 53 → ALB (public, HTTPS 443) → web container (port 8080, private)
                                           → backend API (internal, no ALB route)

GPU worker → RabbitMQ on Main (5672, private VPC only)
           → NATS on Main     (4222, private VPC only)
           → Dragonfly on Main (6379, private VPC only)
           → EFS              (shared filesystem, NFS)
```

### Security Layers

| Layer | What it does |
|---|---|
| WAF v2 | Blocks common exploits, known bad IPs, malformed inputs before they hit the ALB |
| ALB Security Group | Only ports 80 + 443 from internet |
| Main SG | Only port 8080 from ALB SG; only 5672/4222/6379 from GPU SG |
| GPU SG | No inbound. Outbound to main instance only |
| No public IPs | All EC2 instances are in private subnets |
| SSM Session Manager | Shell access without SSH keys or bastion hosts |
| Secrets Manager | Secrets fetched at boot over HTTPS, never in userdata or git |
| EFS encryption | Data at rest encrypted; TLS in transit |
| EBS encryption | Root volumes encrypted |
| VPC Flow Logs | All VPC traffic logged to CloudWatch for audit |

---

## Repository Layout

```
infrastructure/terraform/
├── modules/
│   ├── vpc/            VPC, subnets (public + private × 2 AZs), NAT GWs, flow logs
│   ├── iam/            EC2 instance role (SSM, ECR, Secrets Manager, CloudWatch)
│   ├── efs/            Shared EFS filesystem + access points + backup policy
│   ├── alb/            ALB, HTTPS listener, WAF v2, ACM cert, S3 access logs
│   ├── ec2_stack/      Security groups, main instance, GPU spot instance, Secrets Manager
│   └── monitoring/     CloudWatch alarms (CPU, status, 5xx, unhealthy hosts), dashboard
├── regions/
│   ├── us-east-1/      PRIMARY region — wires all modules, has tfvars.example
│   └── us-west-2/      SECONDARY (failover) region — identical layout, different CIDRs
├── global/             Route 53 zone, health checks, failover A records, S3/DynamoDB state
└── scripts/
    ├── user_data_main.sh   Bootstraps main CPU instance (Docker, EFS, secrets, systemd)
    └── user_data_gpu.sh    Bootstraps GPU instance (NVIDIA toolkit, Docker, EFS, settings)

Docker/
├── docker-compose.yml                   Original single-host compose (local dev)
└── AWS_docker_compose/
    ├── docker-compose.main.yml          CPU services only (runs on main EC2)
    └── docker-compose.gpu.yml           MotionCor plugin only (runs on GPU EC2)
```

---

## Prerequisites

### Tools (install on your workstation)

```bash
# Terraform >= 1.10 (required for S3 native state locking)
https://developer.hashicorp.com/terraform/install

# AWS CLI v2
https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

# AWS Session Manager plugin (for SSM shell access)
https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
```

### AWS IAM permissions

Your IAM user needs the following permissions. If you don't have AdministratorAccess,
attach this inline policy to your IAM user (IAM → Users → your user → Add permissions
→ Create inline policy → JSON):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:*", "iam:*", "logs:*", "cloudwatch:*",
        "elasticfilesystem:*", "secretsmanager:*",
        "elasticloadbalancing:*", "wafv2:*",
        "sns:*", "s3:*", "acm:*", "ssm:*"
      ],
      "Resource": "*"
    }
  ]
}
```

> **Note:** Route 53 permissions (`route53:*`) are only needed if you use a custom
> domain. Skip them until you're ready to add HTTPS.

```bash
# Configure credentials
aws configure

# Verify
aws sts get-caller-identity
```

### Domain name (optional to start)

You do **not** need a domain name to deploy. By default the app is reachable at
the ALB's built-in AWS DNS name over HTTP
(`http://magellon-prod-use1-alb-XXXXX.us-east-1.elb.amazonaws.com`).

When you're ready to add a real domain, set `domain_name` and `route53_zone_id`
in your tfvars and run `terraform apply` again. Terraform will provision the ACM
certificate, validate it via Route 53, and switch the listener to HTTPS with no
downtime.

---

## Step-by-Step Deployment

### Choose your starting path

```
┌─────────────────────────────────────────────────────────┐
│  No domain yet (quickest start)                         │
│  Skip Step 1 entirely.                                  │
│  Go straight to Step 2.                                 │
│  Access the app via the ALB DNS name printed at the end.│
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Have a domain / want HTTPS from day one                │
│  Follow all steps including Step 1.                     │
└─────────────────────────────────────────────────────────┘
```

### Step 1 — Bootstrap global resources (always required)

This creates the S3 bucket for Terraform state (with S3 native locking — no DynamoDB needed)
and optionally the Route 53 hosted zone if you have a domain.

```bash
cd infrastructure/terraform/global
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set domain_name = "yourdomain.com"

terraform init
terraform apply
```

**Copy the `name_servers` output** to your domain registrar's NS records.
DNS propagation takes up to 48 hours but usually under 30 minutes.

```bash
# Example output:
# name_servers = [
#   "ns-123.awsdns-45.com",
#   "ns-456.awsdns-67.net",
#   ...
# ]
```

Also note the `hosted_zone_id` — you need it for the region deploys.

---

### Step 2 — Deploy primary region (us-east-1)

```bash
cd infrastructure/terraform/regions/us-east-1
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
# ── No domain yet? Leave these two empty ─────────────────────────────────────
domain_name     = ""   # fill in later when you have a domain
route53_zone_id = ""   # fill in later (from Step 1 output)

# ── With a domain ─────────────────────────────────────────────────────────────
# domain_name     = "yourdomain.com"
# route53_zone_id = "Z0123456789..."

alert_email = "ops@yourdomain.com"

mysql_root_password = "..."   # generate with: openssl rand -base64 24
mysql_password      = "..."
rabbitmq_password   = "..."
dragonfly_password  = "..."
grafana_password    = "..."
```

```bash
terraform init
terraform plan    # review what will be created
terraform apply   # takes ~10 minutes (NAT GWs + spot instance fulfillment)
```

After apply, get your URL immediately:

```bash
terraform output app_url
# No domain:  http://magellon-prod-use1-alb-XXXXX.us-east-1.elb.amazonaws.com
# With domain: https://magellon.org

terraform output alb_dns_name   # raw ALB hostname (needed for Step 4)
terraform output alb_zone_id    # ALB zone ID     (needed for Step 4)
```

---

### Step 3 — Deploy secondary region (us-west-2)

```bash
cd infrastructure/terraform/regions/us-west-2
cp terraform.tfvars.example terraform.tfvars
# Use IDENTICAL secret values as us-east-1 (same passwords for consistent failover)
# Change key_pair_name to a key created in us-west-2 if you use SSH keys

terraform init
terraform apply
```

---

### Step 4 — Wire Route 53 failover

Go back to global and add the ALB DNS values from Steps 2 and 3:

```bash
cd infrastructure/terraform/global
```

Edit `terraform.tfvars`:

```hcl
primary_alb_dns       = "magellon-prod-use1-alb-XXXXX.us-east-1.elb.amazonaws.com"
primary_alb_zone_id   = "Z35SXDOTRQ7X7K"
secondary_alb_dns     = "magellon-prod-usw2-alb-XXXXX.us-west-2.elb.amazonaws.com"
secondary_alb_zone_id = "Z1H1FL5HABSF5"
```

```bash
terraform apply
```

Your app is now live at `https://yourdomain.com`.

---

### Step 5 — Verify the application is running

The EC2 instances clone the repository and build+start all containers automatically
on first boot via `user_data`. Boot takes **10–20 minutes** (image builds included).

Check boot progress via SSM:

```bash
# Get the main instance ID
cd infrastructure/terraform/regions/us-east-1
aws ssm start-session \
  --target $(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=magellon-prod-use1-main" \
    --query "Reservations[0].Instances[0].InstanceId" --output text) \
  --region us-east-1

# Inside the session — watch bootstrap log:
sudo tail -f /var/log/magellon-bootstrap.log

# Check service status once bootstrap completes:
sudo systemctl status magellon
sudo docker compose -f /opt/magellon-repo/Docker/AWS_docker_compose/docker-compose.main.yml ps
```

Once the `web` container is healthy on port 8080, the ALB health check passes
and the app becomes reachable at the URL from `terraform output app_url`.

On the **GPU instance** (verify MotionCor plugin):

```bash
aws ssm start-session \
  --target $(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=magellon-prod-use1-gpu-worker" \
    --query "Reservations[0].Instances[0].InstanceId" --output text) \
  --region us-east-1

# Inside the session:
sudo nvidia-smi                          # verify GPU is visible
sudo systemctl status magellon-gpu
sudo docker compose -f /opt/magellon-gpu/docker-compose.gpu.yml ps
```

---

## Day-2 Operations

### Upgrade from HTTP to HTTPS (when you get a real domain)

No rebuild, no downtime. Three steps:

**1. Deploy global resources** (if you skipped Step 1 earlier):
```bash
cd infrastructure/terraform/global
cp terraform.tfvars.example terraform.tfvars
# set: domain_name = "yourdomain.com"
terraform init && terraform apply
# → copy the name_servers to your registrar, wait for DNS propagation
```

**2. Set your domain in each region's tfvars**:
```hcl
# regions/us-east-1/terraform.tfvars
domain_name     = "yourdomain.com"
route53_zone_id = "Z0123456789..."   # from global/ outputs
```

**3. Apply — Terraform handles the rest**:
```bash
cd infrastructure/terraform/regions/us-east-1
terraform apply
# Creates ACM cert, validates via Route 53, creates HTTPS listener,
# switches HTTP listener to redirect. Takes ~3 minutes for cert validation.

terraform output app_url
# → https://yourdomain.com
```
Repeat for `us-west-2`, then run `global/` apply again to wire Route 53 failover.

---

### Connect to any instance (no SSH key required)

```bash
# Main instance
aws ssm start-session --target <INSTANCE_ID> --region us-east-1

# GPU instance
aws ssm start-session --target <INSTANCE_ID> --region us-east-1

# Port-forward Grafana to your laptop (localhost:3000)
aws ssm start-session \
  --target <MAIN_INSTANCE_ID> \
  --region us-east-1 \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["3000"],"localPortNumber":["3000"]}'
# Then open http://localhost:3000
```

### View logs

```bash
# Container logs via CloudWatch (all services)
aws logs tail /magellon/prod/backend    --follow --region us-east-1
aws logs tail /magellon/prod/rabbitmq   --follow --region us-east-1
aws logs tail /magellon/prod/motioncor-plugin --follow --region us-east-1

# On-instance (when SSM session is open)
sudo docker compose \
  -f /opt/magellon-repo/Docker/AWS_docker_compose/docker-compose.main.yml \
  logs -f backend
```

### Update an application image

```bash
# Rebuild + push to ECR (example for backend)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com

docker build -t magellon-core-image CoreService/
docker tag magellon-core-image <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com/magellon/backend:latest
docker push <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com/magellon/backend:latest

# On the instance — pull and restart
sudo docker compose -f /opt/magellon/docker-compose.main.yml pull backend
sudo docker compose -f /opt/magellon/docker-compose.main.yml up -d backend
```

### Stop / start the GPU instance to save cost

The GPU spot instance should be stopped when no MotionCor jobs are running
(it costs ~$0.08–0.53/hr depending on spot price).

```bash
# Stop (preserves root EBS volume and EFS data)
aws ec2 stop-instances --instance-ids <GPU_INSTANCE_ID> --region us-east-1

# Start again when needed
aws ec2 start-instances --instance-ids <GPU_INSTANCE_ID> --region us-east-1
```

### Rotate a secret

```bash
# Update in Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id "/magellon/magellon-prod-use1/app-secrets" \
  --secret-string '{"RABBITMQ_DEFAULT_PASS":"new_password", ...}'

# Re-run the bootstrap to write a new .env, then restart the stack
# OR update the running container directly:
docker compose -f /opt/magellon/docker-compose.main.yml \
  exec rabbitmq rabbitmqctl change_password rabbit new_password
```

### Manual failover test

```bash
# Temporarily fail the primary health check by blocking port 443 on the primary ALB SG
# Route 53 will switch to secondary within ~90 seconds (3 checks × 30s interval)

# Check which endpoint Route 53 is resolving to:
dig +short yourdomain.com
```

### Terraform operations

```bash
# Always run plan before apply
terraform plan -out=tfplan
terraform apply tfplan

# Destroy a region (careful! this deletes everything)
terraform destroy

# Refresh state without applying changes
terraform refresh

# Import an existing resource
terraform import aws_instance.main i-0123456789abcdef0
```

---

## Monitoring

### CloudWatch Dashboard

```
AWS Console → CloudWatch → Dashboards → magellon-prod-use1-overview
```

Shows: Main CPU, GPU CPU, ALB request count, ALB 5xx errors, ALB p99 latency, EFS burst credits.

### Alarms

| Alarm | Threshold | Action |
|---|---|---|
| Main CPU high | >85% for 3 min | SNS email |
| GPU CPU high | >95% for 5 min | SNS email |
| Main status check | Any failure | Email + EC2 auto-recovery |
| ALB 5xx | >10 per minute | SNS email |
| ALB unhealthy hosts | Any | SNS email + ok |

### VPC Flow Logs

All VPC traffic (accepted + rejected) is logged to CloudWatch under:
`/aws/vpc/magellon-prod-use1/flow-logs` with 30-day retention.

---

## Cost Estimate (us-east-1, 24×7)

| Resource | Type | $/mo |
|---|---|---|
| Main instance | t3.xlarge on-demand | ~$130 |
| GPU instance | g4dn.xlarge spot | ~$55–80 (stop when idle → $0) |
| NAT Gateways (×2) | per-AZ | ~$65 |
| EFS storage | 50 GB generalPurpose | ~$15 |
| ALB | per-LCU | ~$20 |
| Secrets Manager | 5 secrets | ~$2.50 |
| CloudWatch | logs + alarms | ~$10 |
| **Total (both regions)** | | **~$600–700/mo** |

**Cost tips:**
- Stop the GPU instance when idle — biggest single saving
- Use Reserved Instances for the main instance if running >6 months (~40% discount)
- Enable EFS Intelligent Tiering (already configured) — cold data moves to IA at $0.025/GB
- Secondary region can use smaller instance types if it's cold standby only

---

## Troubleshooting

### MotionCor plugin can't reach RabbitMQ

The GPU instance connects to the main instance's private IP for RabbitMQ (5672).
Check:

```bash
# From GPU instance shell (SSM):
nc -zv <MAIN_PRIVATE_IP> 5672    # should say "Connection to X 5672 port succeeded"

# Check security group allows the traffic:
# GPU SG → Main SG on port 5672 must exist
aws ec2 describe-security-groups --group-ids <MAIN_SG_ID>

# Check the settings_prod.yml was written correctly:
cat /opt/magellon-gpu/settings_prod.yml

# Check the container is picking it up:
docker compose -f docker-compose.gpu.yml exec magellon_motioncor_plugin cat /app/settings_prod.yml
```

### EFS mount fails at boot

```bash
# Check EFS is reachable
showmount -e <EFS_ID>.efs.us-east-1.amazonaws.com

# Try manual mount
sudo mount -t efs -o tls,iam <EFS_ID>:/ /mnt/efs

# Check the EFS security group allows NFS (2049) from the instance's SG
```

### ALB shows unhealthy targets / 502 Bad Gateway

```bash
# 1. Check bootstrap completed (takes 10-20 min on first boot)
sudo tail -50 /var/log/magellon-bootstrap.log

# 2. Check containers are running
sudo docker compose \
  -f /opt/magellon-repo/Docker/AWS_docker_compose/docker-compose.main.yml ps

# 3. Check the web container is listening on 8080
curl -v http://localhost:8080/

# 4. View web container logs
sudo docker compose \
  -f /opt/magellon-repo/Docker/AWS_docker_compose/docker-compose.main.yml \
  logs web

# 5. Check the main security group allows port 8080 from the ALB SG
```

### Spot instance was interrupted

Spot interruptions with `instance_interruption_behavior = stop` leave the
instance in stopped state with the root volume intact. Start it again:

```bash
aws ec2 start-instances --instance-ids <GPU_INSTANCE_ID> --region us-east-1
```

Consider raising `gpu_spot_max_price` in `terraform.tfvars` if interruptions
are frequent (check EC2 Spot pricing history in the console).
The on-demand price for g4dn.xlarge is ~$0.526/hr; set your max to at least
`"0.30"` to reliably get a spot allocation in us-east-1.

### Terraform state drift

```bash
# Refresh state to match real AWS state
terraform refresh

# If a resource was deleted manually, remove it from state:
terraform state rm aws_instance.main

# Re-import it:
terraform import aws_instance.main i-0123456789abcdef0
```

---

## Adding the Secondary Region to the Same Database

Each region currently has an independent MySQL instance. For true active-active
multi-region you have two paths:

1. **Read replica** — promote us-west-2 MySQL to replicate from us-east-1.
   Writes still go to primary; reads are local. Failover requires manual promotion.

2. **Migrate to RDS** — swap the `mysql` container for an RDS instance with
   Multi-AZ + cross-region read replicas. This is the production-grade path
   but adds ~$150–300/mo.

For a science workload where failover is acceptable (users can wait minutes),
option 1 (MySQL replication between Docker containers over VPC peering) is
the pragmatic choice. VPC peering between us-east-1 and us-west-2 would need
to be added as a resource in `global/main.tf`.
