import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_secretsmanager as secretsmanager,
    aws_logs,
)
from constructs import Construct

class CombinedFrontendBackendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Initialize infrastructure
        vpc, cluster, secret, alb = self._create_base_infrastructure()
        
        # Create services
        backend_service, main_listener = self._create_backend_service(cluster, alb, secret)
        frontend_service = self._create_frontend_service(cluster, alb, main_listener)
        
        # Configure auto scaling
        self._configure_service_autoscaling(backend_service, frontend_service)
        
        # Create outputs
        self._create_stack_outputs(alb)

    def _create_base_infrastructure(self):
        """Create and configure base infrastructure components."""
        vpc = ec2.Vpc(self, "AgentVpc", max_azs=2)
        cluster = ecs.Cluster(self, "AgentCluster", vpc=vpc)
        secret = secretsmanager.Secret.from_secret_name_v2(
            self, "AgentAppSecrets", "agent-app"
        )
        
        # Create shared ALB
        alb = elbv2.ApplicationLoadBalancer(
            self, "SharedALB",
            vpc=vpc,
            internet_facing=True
        )
        
        return vpc, cluster, secret, alb

    def _create_backend_service(
        self,
        cluster: ecs.Cluster,
        alb: elbv2.ApplicationLoadBalancer,
        secret: secretsmanager.Secret
    ):
        """Create and configure the backend Fargate service."""
        task_definition = ecs.FargateTaskDefinition(
            self, "BackendTaskDef",
            cpu=512,
            memory_limit_mib=1024
        )
        
        container = task_definition.add_container(
            "BackendContainer",
            image=ecs.ContainerImage.from_asset("app/backend"),
            container_name="backend",
            port_mappings=[ecs.PortMapping(container_port=8000)],
            secrets={
                "HF_TOKEN": ecs.Secret.from_secrets_manager(secret, "HF_TOKEN"),
                "OPENAI_API_KEY": ecs.Secret.from_secrets_manager(secret, "OPENAI_API_KEY"),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="Agent-backend",
                log_retention=aws_logs.RetentionDays.ONE_WEEK
            )
        )

        service = ecs.FargateService(
            self, "BackendService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1
        )

        # Create target group for backend
        backend_target_group = elbv2.ApplicationTargetGroup(
            self, "BackendTargetGroup",
            vpc=cluster.vpc,
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/health",  # Adjust based on your backend health check endpoint
                port="8000"
            )
        )

        service.attach_to_application_target_group(backend_target_group)

        # Create main listener with backend as path-based rule
        main_listener = alb.add_listener(
            "MainListener",
            port=80,
            default_action=elbv2.ListenerAction.forward([backend_target_group])
        )

        # Add path pattern for /api/* to route to backend
        main_listener.add_action(
            "BackendPathRule",
            priority=1,  # Lower number = higher priority
            conditions=[elbv2.ListenerCondition.path_patterns(["/api/*"])],
            action=elbv2.ListenerAction.forward([backend_target_group])
        )

        return service, main_listener

    def _create_frontend_service(
        self,
        cluster: ecs.Cluster,
        alb: elbv2.ApplicationLoadBalancer,
        main_listener: elbv2.ApplicationListener
    ):
        """Create and configure the frontend Fargate service."""
        task_definition = ecs.FargateTaskDefinition(
            self, "FrontendTaskDef",
            cpu=256,
            memory_limit_mib=512
        )
        
        container = task_definition.add_container(
            "FrontendContainer",
            image=ecs.ContainerImage.from_asset("app/frontend"),
            container_name="frontend",
            port_mappings=[ecs.PortMapping(container_port=8501)],
            environment={
                "API_ENDPOINT": f"http://{alb.load_balancer_dns_name}/api"  # Note the /api path
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="Agent-frontend",
                log_retention=aws_logs.RetentionDays.ONE_WEEK
            )
        )

        service = ecs.FargateService(
            self, "FrontendService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1
        )

        # Create target group for frontend
        frontend_target_group = elbv2.ApplicationTargetGroup(
            self, "FrontendTargetGroup",
            vpc=cluster.vpc,
            port=8501,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/",  # Adjust based on your frontend health check endpoint
                port="8501"
            )
        )

        service.attach_to_application_target_group(frontend_target_group)

        # Update main listener to add frontend as default action
        main_listener.default_action = elbv2.ListenerAction.forward([frontend_target_group])

        return service

    def _configure_service_autoscaling(
        self,
        backend_service: ecs.FargateService,
        frontend_service: ecs.FargateService
    ):
        """Configure auto scaling for both services."""
        # Backend auto scaling
        backend_scaling = backend_service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=2
        )
        backend_scaling.scale_on_cpu_utilization("BackendCpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=cdk.Duration.seconds(60),
            scale_out_cooldown=cdk.Duration.seconds(60)
        )

        # Frontend auto scaling
        frontend_scaling = frontend_service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=2
        )
        frontend_scaling.scale_on_cpu_utilization("FrontendCpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=cdk.Duration.seconds(60),
            scale_out_cooldown=cdk.Duration.seconds(60)
        )

    def _create_stack_outputs(self, alb: elbv2.ApplicationLoadBalancer):
        """Create CloudFormation outputs."""
        cdk.CfnOutput(self, "LoadBalancerDNS",
            value=alb.load_balancer_dns_name,
            description="Shared Load Balancer DNS",
            export_name="AgentSharedALBDNS"
        )