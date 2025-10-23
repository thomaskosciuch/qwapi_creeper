# QwapiQweeper

An AWS CDK project that monitors the health of targets in an Application Load Balancer target group and sends Slack notifications when instances become unhealthy. The system includes automatic retriggering to continuously monitor and update on the health status.

## Features

- 🚨 **CloudWatch Alarm**: Monitors target group health metrics
- 📱 **Slack Notifications**: Sends alerts to configured Slack channel
- 🔄 **Auto-Retriggering**: Continuously checks health status and updates messages
- 📊 **Detailed Health Info**: Provides comprehensive health status and target details
- ✅ **Recovery Detection**: Notifies when targets become healthy again

## Architecture

```
CloudWatch Alarm → Lambda Function → Slack Notification
                      ↓
                 EventBridge Rule (2min retrigger)
                      ↓
                 Lambda Function (health check)
```

## Prerequisites

- AWS CLI configured with appropriate permissions
- AWS CDK v2 installed (`npm install -g aws-cdk`)
- Python 3.9+
- Slack bot token (recommended) or webhook URL

## Slack Bot Setup

### Option 1: Bot Token (Recommended)

1. Go to [Slack API](https://api.slack.com/apps) and create a new app
2. Choose "From scratch" and give your app a name
3. Select your workspace
4. Go to "OAuth & Permissions" in the sidebar
5. Add the following Bot Token Scopes:
   - `chat:write` - Send messages
   - `chat:write.public` - Send messages to channels the bot isn't a member of
6. Install the app to your workspace
7. Copy the "Bot User OAuth Token" (starts with `xoxb-`)

### Option 2: Webhook URL (Legacy)

1. Go to [Slack Apps](https://api.slack.com/apps)
2. Create a new app or use an existing one
3. Go to "Incoming Webhooks" and activate them
4. Add a new webhook to your desired channel
5. Copy the webhook URL

## Setup

### 1. Clone and Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install CDK dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Required: Slack bot token (recommended)
export SLACK_BOT_TOKEN="xoxb-your-bot-token-here"

# Alternative: Slack webhook URL (legacy)
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"

# Optional: Slack channel (defaults to #alerts)
export SLACK_CHANNEL="#your-alerts-channel"
```

### 3. Deploy the Stack

```bash
# Make deployment script executable
chmod +x deploy.sh

# Deploy the stack
./deploy.sh
```

Or deploy manually:

```bash
# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy the stack
cdk deploy
```

## Configuration

### Target Group ARN

The target group ARN is hardcoded in the stack:
```
arn:aws:elasticloadbalancing:ca-central-1:778983355679:targetgroup/osiris-prod-load-balancer/fb62f239363e4741
```

To change this, modify the `target_group_arn` variable in `target_group_health_monitor_stack.py`.

### CloudWatch Alarm Settings

- **Metric**: `AWS/ApplicationELB` - `UnHealthyHostCount`
- **Threshold**: 1 unhealthy target
- **Evaluation Periods**: 2 minutes
- **Datapoints to Alarm**: 1

### Lambda Function Settings

- **Runtime**: Python 3.9
- **Timeout**: 5 minutes
- **Memory**: 256 MB
- **Retrigger Interval**: 2 minutes

## How It Works

### 1. Initial Alert
When the CloudWatch alarm triggers (unhealthy targets detected):
- Lambda function checks current target group health
- Sends detailed Slack message with health status
- Sets up EventBridge rule for retriggering

### 2. Retriggering
Every 2 minutes, the Lambda function:
- Re-checks target group health
- Updates Slack message with current status
- If still unhealthy: continues retriggering
- If healthy: sends recovery message and stops retriggering

### 3. Message Types

**Initial Alert:**
```
🚨 Target Group Health Alert
Target Group: osiris-prod-load-balancer
Alarm: UnhealthyTargetsAlarm
Time: 2024-01-15T10:30:00Z

Health Status:
• Total Targets: 3
• Healthy: 1
• Unhealthy: 2

Unhealthy Targets:
• i-1234567890abcdef0 - unhealthy (Target.FailedHealthChecks)
• i-0987654321fedcba0 - unhealthy (Target.ResponseCodeMismatch)

I'll check again in 2 minutes and update this message.
```

**Still Unhealthy:**
```
⚠️ Target Group Still Unhealthy
Target Group: osiris-prod-load-balancer
Original Alert: 2024-01-15T10:30:00Z
Current Time: 2024-01-15T10:32:00Z

Current Health Status:
• Total Targets: 3
• Healthy: 1
• Unhealthy: 2

Still Unhealthy Targets:
• i-1234567890abcdef0 - unhealthy (Target.FailedHealthChecks)

I'll check again in 2 minutes.
```

**Recovery:**
```
✅ Target Group Recovered
Target Group: osiris-prod-load-balancer
Original Alert: 2024-01-15T10:30:00Z
Recovery Time: 2024-01-15T10:35:00Z

Current Health Status:
• Total Targets: 3
• Healthy: 3
• Unhealthy: 0

All targets are now healthy! 🎉
```

## Testing

### Test Lambda Function Directly

```bash
# Get the Lambda function name
aws lambda list-functions --query 'Functions[?contains(FunctionName, `QwapiQweeperLambda`)].FunctionName'

# Invoke the function
aws lambda invoke --function-name <FUNCTION_NAME> response.json

# Check the response
cat response.json
```

### Test CloudWatch Alarm

```bash
# Get alarm name
aws cloudwatch describe-alarms --query 'MetricAlarms[?contains(AlarmName, `UnhealthyTargets`)].AlarmName'

# Test alarm by setting it to ALARM state
aws cloudwatch set-alarm-state --alarm-name <ALARM_NAME> --state-value ALARM --state-reason "Testing alarm"
```

## Monitoring

### CloudWatch Logs

Monitor Lambda execution logs:
```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/QwapiQweeperStack"
```

### CloudWatch Metrics

The alarm monitors the `UnHealthyHostCount` metric for your target group.

## Troubleshooting

### Common Issues

1. **Slack messages not sending**
   - Check `SLACK_BOT_TOKEN` environment variable (recommended)
   - Verify bot token has correct scopes (`chat:write`, `chat:write.public`)
   - Check `SLACK_WEBHOOK_URL` environment variable (legacy)
   - Verify webhook URL is correct and active
   - Check Lambda logs for errors

2. **Lambda timeout**
   - Increase timeout in stack configuration
   - Check network connectivity to Slack

3. **Permission errors**
   - Verify IAM role has required permissions
   - Check CloudWatch and ELB permissions

4. **Alarm not triggering**
   - Verify target group ARN is correct
   - Check CloudWatch metrics are available
   - Ensure targets are actually unhealthy

### Debug Commands

```bash
# Check Lambda function configuration
aws lambda get-function --function-name <FUNCTION_NAME>

# Check CloudWatch alarm state
aws cloudwatch describe-alarms --alarm-names <ALARM_NAME>

# Check target group health
aws elbv2 describe-target-health --target-group-arn <TARGET_GROUP_ARN>

# Check EventBridge rules
aws events list-rules --name-prefix "target-group-health-retrigger"
```

## Cleanup

To remove all resources:

```bash
cdk destroy
```

## Security Considerations

- The Lambda function has minimal required permissions
- Slack webhook URL should be kept secure
- Consider using AWS Secrets Manager for sensitive configuration
- Monitor Lambda execution logs for any security issues

## Cost Optimization

- Lambda function only runs when alarm triggers or retriggers
- EventBridge rule is disabled when not needed
- CloudWatch logs have 1-week retention
- Consider adjusting retrigger interval based on your needs

## Support

For issues or questions:
1. Check CloudWatch logs for error details
2. Verify all environment variables are set correctly
3. Test individual components (Lambda, alarm, Slack webhook)
4. Review IAM permissions