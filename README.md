# **AWS CDK Stack: Multi-Service Application with ALB & Fargate for Deployment of Framework-agnostic AI Agent Apps**
![ArchAWS](https://github.com/user-attachments/assets/1aa575f2-2ffd-4fe6-a8d8-f6bc4b880991)

## **Introduction**
This documentation provides an in-depth explanation of the AWS Cloud Development Kit (CDK) stack for deploying two services (frontend & backend) on **AWS Fargate**, using a **single Application Load Balancer (ALB)** with **path-based routing**. This setup ensures a cost-effective, scalable, and secure architecture for containerized applications.

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


