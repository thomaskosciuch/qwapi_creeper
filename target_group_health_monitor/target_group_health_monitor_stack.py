from aws_cdk import (
    Stack,
    Duration,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
)
from constructs import Construct
import os


class QwapiQweeperStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        target_group_arn = "arn:aws:elasticloadbalancing:ca-central-1:778983355679:targetgroup/osiris-prod-load-balancer/fb62f239363e4741"        
        target_group_name = target_group_arn.split('/')[-1]

        lambda_role = iam.Role(
            self, "TargetGroupHealthLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "CloudWatchAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "cloudwatch:GetMetricStatistics",
                                "cloudwatch:ListMetrics",
                                "cloudwatch:DescribeAlarms",
                                "cloudwatch:PutMetricData"
                            ],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "elasticloadbalancing:DescribeTargetHealth",
                                "elasticloadbalancing:DescribeTargetGroups"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        health_monitor_lambda = lambda_.Function(
            self, "QwapiQweeperLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset("lambda"),
            role=lambda_role,
            timeout=Duration.minutes(5),
            memory_size=256,
            environment={
                "TARGET_GROUP_ARN": target_group_arn,
                "TARGET_GROUP_NAME": target_group_name,
                "SLACK_WEBHOOK_URL": os.getenv("SLACK_WEBHOOK_URL", ""),
                "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN", ""),
                "SLACK_CHANNEL": os.getenv("SLACK_CHANNEL", "C09DH2G0K0Q"),
                "LOG_LEVEL": "INFO"
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )

        unhealthy_targets_alarm = cloudwatch.Alarm(
            self, "UnhealthyTargetsAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/ApplicationELB",
                metric_name="UnHealthyHostCount",
                dimensions_map={
                    "TargetGroup": target_group_arn.split('/')[-1],
                    "LoadBalancer": target_group_arn.split('/')[-2]
                },
                statistic="Average",
                period=Duration.minutes(1)
            ),
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            evaluation_periods=2,
            datapoints_to_alarm=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            alarm_description="Alert when target group has unhealthy instances"
        )

        # Add Lambda as alarm action
        unhealthy_targets_alarm.add_alarm_action(
            cloudwatch_actions.LambdaAction(health_monitor_lambda)
        )

        retrigger_rule = events.Rule(
            self, "HealthMonitorRetriggerRule",
            description="Rule to retrigger health check Lambda function",
            schedule=events.Schedule.rate(Duration.minutes(2)),
            enabled=False
        )

        retrigger_rule.add_target(
            targets.LambdaFunction(health_monitor_lambda)
        )

        health_monitor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:PutRule",
                    "events:DeleteRule",
                    "events:PutTargets",
                    "events:RemoveTargets",
                    "events:EnableRule",
                    "events:DisableRule"
                ],
                resources=["*"]
            )
        )
        health_monitor_lambda.add_permission(
            "SelfInvokePermission",
            principal=iam.ServicePrincipal("lambda.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=health_monitor_lambda.function_arn
        )

        self.target_group_arn = target_group_arn
        self.lambda_function_arn = health_monitor_lambda.function_arn
        self.alarm_name = unhealthy_targets_alarm.alarm_name