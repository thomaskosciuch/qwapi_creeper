#!/usr/bin/env python3
import os

import aws_cdk as cdk

from target_group_health_monitor.target_group_health_monitor_stack import QwapiQweeperStack


app = cdk.App()
QwapiQweeperStack(app, "QwapiQweeperStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION', 'ca-central-1')
    ),
    description="Stack for monitoring target group health and sending Slack notifications"
)

app.synth()
