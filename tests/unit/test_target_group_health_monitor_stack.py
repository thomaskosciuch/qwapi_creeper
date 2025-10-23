import aws_cdk as core
import aws_cdk.assertions as assertions

from target_group_health_monitor.target_group_health_monitor_stack import QwapiQweeperStack

# example tests. To run these tests, uncomment this file along with the example
# resource in target_group_health_monitor/target_group_health_monitor_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = QwapiQweeperStack(app, "qwapi-qweeper")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
