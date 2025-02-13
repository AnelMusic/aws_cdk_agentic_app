# **AWS CDK Stack: Multi-Service Application with ALB & Fargate for Deployment of Framework-agnostic AI Agent Apps**
![ArchAWS](https://github.com/user-attachments/assets/1aa575f2-2ffd-4fe6-a8d8-f6bc4b880991)

## **Introduction**
This documentation provides an in-depth explanation of the AWS Cloud Development Kit (CDK) stack for deploying two services (frontend & backend) on **AWS Fargate**, using a **single Application Load Balancer (ALB)** with **path-based routing**. This setup ensures a cost-effective, scalable, and secure architecture for containerized applications.

# **Setup Guide for Deploying the AWS CDK Infrastructure**

## **Prerequisites**
Before setting up and deploying the AWS CDK infrastructure, ensure that you have the following installed and configured on your system:

### **1. Required Tools**
- **AWS CDK (Node.js Required)** – Install Node.js and AWS CDK:
  ```sh
  # Install Node.js (if not already installed)
  sudo apt install nodejs npm   # Ubuntu/Debian
  brew install node             # macOS
  choco install nodejs          # Windows
  
  # Install AWS CDK globally
  npm install -g aws-cdk
  ```
- **Docker** (for building container images for AWS Fargate)
  ```sh
  # Install Docker (ensure the Docker daemon is running)
  ```
- **Python 3 & Virtual Environment**
  ```sh
  # Ensure Python is installed (3.8+ recommended)
  python3 --version
  
  # Install virtualenv if not installed
  pip install virtualenv
  ```

### **2. Configure AWS CLI and AWS Secret**
Ensure you are authenticated with AWS and have the necessary permissions:
```sh
aws configure
```
- Create a secret in the aws secret manager and call it agent-app. It must hold your HF_TOKEN and YOUR OPENAI_API_KEY 
- You should have access to an AWS account with IAM permissions for CDK deployment, ECS, ALB, and networking setup.
---

## **Setting Up the CDK Project**
Since AWS CDK projects require a specific structure, you **cannot simply clone this repository and run `cdk deploy`**. Instead, follow these steps:

### **1. Initialize a New CDK Project**
Navigate to your working directory and initialize a new CDK project:
```sh
mkdir my-cdk-project
cd my-cdk-project
cdk init app --language python
```
This creates the necessary CDK project structure.

### **2. Set Up a Python Virtual Environment**
```sh
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

### **3. Install Required Dependencies**
```sh
pip install -r requirements.txt
```
Ensure that the dependencies match those in the `requirements.txt` of the repository.

### **4. Copy the Repository Files to the CDK Project**
Since CDK requires an initialized project, **you must manually copy the files from this repository into your initialized CDK project**.
---

## **Bootstrapping Your AWS Environment**
AWS CDK requires your AWS account to be bootstrapped before deploying any infrastructure.

```sh
cdk bootstrap aws://your_account_id/your_region
```
This sets up necessary resources.

---

## **Deploying the CDK Stack**
Once you have copied the required files and bootstrapped your AWS environment, deploy the stack:

```sh
cdk deploy
```
This will:
- Create/update the VPC, subnets, and networking components.
- Deploy the Application Load Balancer (ALB).
- Set up the ECS Fargate services (frontend and backend).
- Apply security configurations.

---

## **Verifying the Deployment**
After the deployment completes, check the AWS console to confirm:
- The **ALB** is running and accessible.
- ECS **Fargate tasks** are successfully launched.
- The API endpoint (FastAPI) is responding correctly.

You can also check the deployed stack by running:
```sh
aws cloudformation list-stacks --query "StackSummaries[?StackStatus!='DELETE_COMPLETE'].StackName" --output text
```
and get the respective DNS via:
```sh
aws cloudformation describe-stacks --stack-name CombinedFrontendBackendStack --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' --output text
```
---

## **Cleaning Up Resources**
To avoid unnecessary AWS costs, delete the stack when no longer needed:
```sh
cdk destroy
```
This removes all AWS resources created by the stack.

---



## **Infrastructure Overview**

### **Network Infrastructure**
- **VPC Configuration**
  - 2 Availability Zones for high availability.
  - 1 NAT Gateway (can be increased to 1 per AZ for production).
  - Public subnets for ALB.
  - Private subnets for Fargate services.

### **Application Load Balancer (ALB) Setup**

- **Security Group Configuration**
  ```python
  alb_security_group = ec2.SecurityGroup(
      self, "ALBSecurityGroup",
      vpc=vpc,
      allow_all_outbound=True
  )
  alb_security_group.add_ingress_rule(
      ec2.Peer.any_ipv4(),
      ec2.Port.tcp(80),
      "Allow HTTP traffic"
  )
  ```
  - **Allows inbound HTTP traffic (port 80) from any IP**.
  - Allows all outbound traffic.
  - **Note:** In production, consider adding HTTPS (port 443) and restricting IP ranges.

- **ALB Configuration**
  ```python
  alb = elbv2.ApplicationLoadBalancer(
      self, "SharedALB",
      vpc=vpc,
      internet_facing=True,
      security_group=alb_security_group
  )
  ```
  - Internet-facing for public access.
  - Placed in public subnets.
  - Uses a single security group.

### **Routing Configuration**
- **Default Route (Frontend)**
  - All traffic by default routes to the frontend service.
  - Uses Streamlit's port 8501.
  ```python
  default_action=elbv2.ListenerAction.forward([frontend_target_group])
  ```

- **API Route (Backend)**
  - All `/api/*` paths route to the backend service.
  - Uses FastAPI's port 8000.
  ```python
  conditions=[elbv2.ListenerCondition.path_patterns(["/api/*"])]
  ```

---

## **ECS Fargate Services**

### **Backend Service (FastAPI)**
- **Task Definition**
  - CPU: 512 units.
  - Memory: 1024 MB.
  - Container Port: 8000.
  - **Environment Variables:**
    - `HF_TOKEN` (from Secrets Manager).
    - `OPENAI_API_KEY` (from Secrets Manager).

- **Health Check**
  - Path: `/health`.
  - Success Codes: `200`.

### **Frontend Service (Streamlit)**
- **Task Definition**
  - CPU: 256 units.
  - Memory: 512 MB.
  - Container Port: 8501.
  - **Environment Variables:**
    - `API_ENDPOINT`: Points to ALB DNS with `/api` prefix.

- **Health Check**
  - Path: `/_stcore/health`.
  - Success Codes: `200`.

---

## **ECS Fargate Configuration**
- Both services run on **Fargate (serverless)**.
- Services placed in **private subnets**.
- **No public IP addresses assigned** (`assign_public_ip=False`).
- Uses **AWS Log Driver** with 1-week retention.

---

## **Why the Default Fargate Pattern Could Not Be Used**
### **Issue with `ApplicationLoadBalancedFargateService`**
The standard CDK `ApplicationLoadBalancedFargateService` construct **was not used** because:
1. **We need custom routing logic for both services**.
2. **We're sharing a single ALB between services**.
3. **We need fine-grained control over security groups and routing rules**.

### **How We Solved This**
- **Manually created an ALB** and added path-based routing rules.  
- **Manually defined target groups for both services.**  
- **Attached Fargate services to their respective target groups during creation.**  

---

## **Networking Flow**
1. **Inbound: Internet → Internet Gateway IGW → ALB (Public Subnet) → Fargate Services (Private Subnet)**.
2. **Outbound: Fargate → NAT Gateway → Internet (for pulling images/updates).**

## **Port Configuration**
- **Exposed Ports**
  - **ALB: Port 80 (HTTP) (allows inbound traffic from any IP)**.
  - **Backend: Port 8000 (internal only)**.
  - **Frontend: Port 8501 (internal only)**.

- **Port Mapping**
  - External HTTP traffic (`80`) → ALB.
  - ALB → Backend (`8000`) for `/api/*` paths.
  - ALB → Frontend (`8501`) for all other paths.

---

## **Resource Scaling**
- Both services start with `desired_count=1`.
- **No auto-scaling configured in this setup**.
- Can be added using ECS **Service Auto Scaling**.

---

## **Security Considerations**
1. **Fargate tasks run in private subnets**.
2. **Only the ALB is internet-facing**.
3. **Services communicate through the ALB, not directly**.
4. **Secrets managed through AWS Secrets Manager**.

---


## **API Documentation**

### **Overview**
The backend service exposes a **FastAPI-based REST API** that provides an AI-driven medical appointment scheduling agent.

### **Endpoints**
#### **1. Query API** (POST `/api/query`)
- **Description:** Processes a user query and returns AI-generated results for medical appointment scheduling.
- **Request Body:**
  ```json
  {
      "user_input": "Find all orthopedic specialists available on Mondays."
  }
  ```
- **Response:**
  ```json
  {
      "answer": "Dr. Smith is available on Mondays from 8 AM - 12 PM."
  }
  ```
- **Error Handling:**
  - `500 Internal Server Error` if query processing fails.

#### **2. Health Check API** (GET `/api/health`)
- **Description:** Returns the API health status.
- **Response:**
  ```json
  {
      "status": "healthy",
      "version": "v1"
  }
  ```

#### **3. Root Endpoint** (GET `/api`)
- **Description:** Provides metadata about the API.
- **Response:**
  ```json
  {
      "message": "Welcome to the Medical Appointment Agent API",
      "version": "v1",
      "documentation": "/api/docs",
      "health_check": "/api/health",
      "usage": "Send a POST request to /api/query with a JSON body containing a 'user_input' field."
  }
  ```

### **API Dependencies & Features**
- **CORS Middleware:** Allows cross-origin requests.
- **Dependency Injection:** Uses `Depends()` for structured API dependencies.
- **Pydantic Models:** Ensures input validation and response standardization.
- **Environment Variables:** Uses `.env` files for configuration management during local development. Otherwise secret from AWS secret manager is utilized.

---


## **Potential Improvement for Production**
1. **Add HTTPS support** with an ACM certificate.
2. **Implement auto-scaling rules**. (Currently ECS Fargate services (frontend and backend) run with a fixed number of tasks (desired_count=1) to keep cost minimal. This means that the number of running containers will remain constant unless manually changed.)
4. **Enhance security with AWS WAF**.
5. **Configure CloudWatch alarms for monitoring**.
6. **Integrate with Route 53 for custom domain management**.


