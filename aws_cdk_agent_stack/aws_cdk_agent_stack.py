import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_secretsmanager as secretsmanager,
    aws_logs
)
from constructs import Construct

class CombinedFrontendBackendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create base infrastructure
        vpc, cluster, secret = self._create_base_infrastructure()
        
        # Create ALB
        alb = self._create_alb(vpc)
        
        # Create services and target groups
        backend_target_group = self._create_backend_service(vpc, cluster, secret)
        frontend_target_group = self._create_frontend_service(vpc, cluster, alb)
        
        # Configure ALB routing
        self._configure_alb_routing(alb, backend_target_group, frontend_target_group)
        
        # Create outputs
        cdk.CfnOutput(
            self, "LoadBalancerDNS",
            value=alb.load_balancer_dns_name,
            description="Load Balancer DNS"
        )

    def _create_base_infrastructure(self) -> tuple[ec2.Vpc, ecs.Cluster, secretsmanager.Secret]:
        """Create and configure base infrastructure components"""
        vpc = ec2.Vpc(
            self, "AgentVpc",
            max_azs=2,
            nat_gateways=1  # for production 1 per AZ is recommended to reduce latency
        )
        
        cluster = ecs.Cluster(
            self, "AgentCluster",
            vpc=vpc
        )
        
        secret = secretsmanager.Secret.from_secret_name_v2(
            self, "AgentAppSecrets",
            "agent-app"
        )
        
        return vpc, cluster, secret

    def _create_alb(self, vpc: ec2.Vpc) -> elbv2.ApplicationLoadBalancer:
        """Create Application Load Balancer with its security group"""
        # Create ALB Security Group
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
        
        # Create ALB
        alb = elbv2.ApplicationLoadBalancer(
            self, "SharedALB",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_security_group
        )
        
        return alb

    def _create_backend_service(
        self,
        vpc: ec2.Vpc,
        cluster: ecs.Cluster,
        secret: secretsmanager.Secret
    ) -> elbv2.ApplicationTargetGroup:
        """Create backend service and its target group"""
        task_definition = ecs.FargateTaskDefinition(
            self, "BackendTask",
            cpu=512,
            memory_limit_mib=1024
        )
        
        task_definition.add_container(
            "BackendContainer",
            image=ecs.ContainerImage.from_asset("app/backend"),
            port_mappings=[ecs.PortMapping(container_port=8000)],
            secrets={
                "HF_TOKEN": ecs.Secret.from_secrets_manager(secret, "HF_TOKEN"),
                "OPENAI_API_KEY": ecs.Secret.from_secrets_manager(secret, "OPENAI_API_KEY"),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="backend",
                log_retention=aws_logs.RetentionDays.ONE_WEEK
            )
        )
        
        target_group = elbv2.ApplicationTargetGroup(
            self, "BackendTarget",
            vpc=vpc,
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check={
                "path": "/api/health", 
                "healthy_http_codes": "200"
            }
        )
        
        service = ecs.FargateService(
            self, "BackendService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            assign_public_ip=False
        )
        
        service.attach_to_application_target_group(target_group)
        return target_group

    def _create_frontend_service(
        self,
        vpc: ec2.Vpc,
        cluster: ecs.Cluster,
        alb: elbv2.ApplicationLoadBalancer
    ) -> elbv2.ApplicationTargetGroup:
        """Create frontend service and its target group"""
        task_definition = ecs.FargateTaskDefinition(
            self, "FrontendTask",
            cpu=256,
            memory_limit_mib=512
        )
        
        task_definition.add_container(
            "FrontendContainer",
            image=ecs.ContainerImage.from_asset("app/frontend"),
            port_mappings=[ecs.PortMapping(container_port=8501)],
            environment={
                "API_ENDPOINT": f"http://{alb.load_balancer_dns_name}/api"
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="frontend",
                log_retention=aws_logs.RetentionDays.ONE_WEEK
            )
        )
        
        target_group = elbv2.ApplicationTargetGroup(
            self, "FrontendTarget",
            vpc=vpc,
            port=8501,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check={
                "path": "/_stcore/health",  # streamlit healthcheck endpoint
                "healthy_http_codes": "200"
            }
        )
        
        service = ecs.FargateService(
            self, "FrontendService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            assign_public_ip=False
        )
        
        service.attach_to_application_target_group(target_group)
        return target_group

    def _configure_alb_routing(
        self,
        alb: elbv2.ApplicationLoadBalancer,
        backend_target_group: elbv2.ApplicationTargetGroup,
        frontend_target_group: elbv2.ApplicationTargetGroup
    ) -> None:
        """Configure ALB routing rules for frontend and backend services"""
        # Create main listener with frontend as default
        listener = alb.add_listener(
            "MainListener",
            port=80,
            default_action=elbv2.ListenerAction.forward([frontend_target_group])
        )
        
        # Add backend API routing rule
        listener.add_action(
            "BackendRule",
            priority=1,
            conditions=[
                elbv2.ListenerCondition.path_patterns(["/api/*"])
            ],
            action=elbv2.ListenerAction.forward([backend_target_group])
        )