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
        
        # Create VPC
        vpc = ec2.Vpc(self, "AgentVpc", max_azs=2, nat_gateways=1)
        
        # Create ECS Cluster
        cluster = ecs.Cluster(self, "AgentCluster", vpc=vpc)
        
        # Get secrets
        secret = secretsmanager.Secret.from_secret_name_v2(
            self, "AgentAppSecrets", "agent-app"
        )
        
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
        
        # Create Backend Service first so we can use its target group
        backend_task = ecs.FargateTaskDefinition(
            self, "BackendTask",
            cpu=512,
            memory_limit_mib=1024
        )
        
        backend_container = backend_task.add_container(
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
        
        backend_target_group = elbv2.ApplicationTargetGroup(
            self, "BackendTarget",
            vpc=vpc,
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check={
                "path": "/health",
                "healthy_http_codes": "200"
            }
        )
        
        backend_service = ecs.FargateService(
            self, "BackendService",
            cluster=cluster,
            task_definition=backend_task,
            desired_count=1,
            assign_public_ip=False
        )
        
        backend_service.attach_to_application_target_group(backend_target_group)
        
        # Frontend Service
        frontend_task = ecs.FargateTaskDefinition(
            self, "FrontendTask",
            cpu=256,
            memory_limit_mib=512
        )
        
        frontend_container = frontend_task.add_container(
            "FrontendContainer",
            image=ecs.ContainerImage.from_asset("app/frontend"),
            port_mappings=[ecs.PortMapping(container_port=8501)],
            environment={
                "API_ENDPOINT": f"http://{alb.load_balancer_dns_name}"
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="frontend",
                log_retention=aws_logs.RetentionDays.ONE_WEEK
            )
        )
        
        frontend_target_group = elbv2.ApplicationTargetGroup(
            self, "FrontendTarget",
            vpc=vpc,
            port=8501,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check={
                "path": "/_stcore/health",
                "healthy_http_codes": "200"
            }
        )
        
        frontend_service = ecs.FargateService(
            self, "FrontendService",
            cluster=cluster,
            task_definition=frontend_task,
            desired_count=1,
            assign_public_ip=False
        )
        
        frontend_service.attach_to_application_target_group(frontend_target_group)
        
        # Create main listener with frontend as default
        listener = alb.add_listener(
            "MainListener",
            port=80,
            default_action=elbv2.ListenerAction.forward([frontend_target_group])
        )
        
        # Add routing rules
        listener.add_action(
            "BackendRule",
            priority=1,
            conditions=[
                elbv2.ListenerCondition.path_patterns(["/api/*"])
            ],
            action=elbv2.ListenerAction.forward([backend_target_group])
        )
        
        # All other traffic goes to frontend (i think this is redundant since frontend is default anyways but check another time)
        listener.add_action(
            "FrontendRule",
            priority=2,
            conditions=[elbv2.ListenerCondition.path_patterns(["/*"])],
            action=elbv2.ListenerAction.forward([frontend_target_group])
        )
        
        # Output the ALB DNS
        cdk.CfnOutput(
            self, "LoadBalancerDNS",
            value=alb.load_balancer_dns_name,
            description="Load Balancer DNS"
        )