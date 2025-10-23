#!/bin/bash

# AWS CDK QwapiQweeper Deployment Script

set -e

echo "🚀 Deploying QwapiQweeper..."

# Load environment variables from .env file
if [ -f .env ]; then
    echo "📄 Loading environment variables from .env file..."
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "⚠️  No .env file found. Using environment variables from shell."
fi

# Check if required environment variables are set
if [ -z "$SLACK_BOT_TOKEN" ] && [ -z "$SLACK_WEBHOOK_URL" ]; then
    echo "❌ Error: Either SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL environment variable is required"
    echo "Please set one of them:"
    echo "  export SLACK_BOT_TOKEN='xoxb-your-bot-token'"
    echo "  export SLACK_WEBHOOK_URL='your_slack_webhook_url'"
    exit 1
fi

# Optional: Set Slack channel (defaults to #alerts)
if [ -z "$SLACK_CHANNEL" ]; then
    export SLACK_CHANNEL="#alerts"
    echo "ℹ️  Using default Slack channel: $SLACK_CHANNEL"
fi

echo "📋 Configuration:"
echo "   Target Group ARN: arn:aws:elasticloadbalancing:ca-central-1:778983355679:targetgroup/osiris-prod-load-balancer/fb62f239363e4741"
echo "   Slack Channel: $SLACK_CHANNEL"
echo "   Region: ca-central-1"

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Bootstrap CDK (if needed)
echo "🔧 Bootstrapping CDK..."
cdk bootstrap

# Deploy the stack
echo "🚀 Deploying stack..."
cdk deploy --require-approval never

echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Test the Lambda function by invoking it directly"
echo "   2. Monitor CloudWatch logs for any issues"
echo "   3. Verify the CloudWatch alarm is created and monitoring your target group"
echo ""
echo "🧪 To test the Lambda function:"
echo "   aws lambda invoke --function-name QwapiQweeperStack-QwapiQweeperLambda-XXXXX response.json"
