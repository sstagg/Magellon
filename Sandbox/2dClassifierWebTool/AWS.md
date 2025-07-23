# ✅ AWS Architecture Documentation  
---

## 🔧 Objective
To deploy a frontend and backend application in a **private AWS environment** with persistent storage using **Amazon EFS**, behind an **Application Load Balancer (ALB)** with path-based routing.

---

## 🧱 Components Used

- **EC2 instances** (inside private subnets)
- **Elastic File System (EFS)** for shared storage
- **Application Load Balancer (ALB)** for routing
- **Target Groups** for backend and frontend services
- **Security Groups** and **IAM Roles**
- **VPC with Private and Public Subnets**
- **NAT Gateway & Internet Gateway** (for updates & downloads)
- **Auto Scaling Group**
- **SSL Setup** 

---

## 🛠️ Steps Performed

### 1. VPC & Subnet Setup
- Created a custom VPC with public and private subnets.
- Attached route tables, NAT Gateway (for private subnet access), and Internet Gateway (for public access).

### 2. EFS Configuration
- Created an **EFS file system** for shared storage (used by backend services).
- Mounted EFS on EC2 instances using the correct mount targets and security group rules.
- Verified write-read operations from application containers.

### 3. Docker & ECS (if used)
- Dockerized both frontend and backend and pushed to Elastic Container Registry(ECR)
- Ensured EFS volume was mounted into containers (via Docker or ECS task definition with `mountPoints`).

### 4. Application Load Balancer (ALB)
- Configured path-based routing:
  - `/api/*` → Backend target group
  - `/images/*` → Backend (for static files)
  - `/*` → Frontend target group
- Health checks implemented on `/health` endpoints for backend and frontend.

### 5. Security Groups
- Defined least-privilege rules:
  - ALB SG allows HTTPS (443) from the internet.
  - Backend and frontend EC2s only accept traffic from ALB SG.
  - EFS accepts NFS (2049) only from backend EC2s.

### 6. HTTPS Setup
- If domain was configured:
  - Requested certificate via **ACM**
  - Attached SSL certificate to ALB Listener
  - Forwarded HTTPS traffic properly


---

## ✅ Outcome
- **Private AWS environment** successfully deployed
- **EFS-integrated backend** operational
- **Path-based routing** functional via ALB
setup

---

