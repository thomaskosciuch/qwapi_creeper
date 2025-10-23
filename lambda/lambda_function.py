import json
import boto3
import requests
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger()
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

cloudwatch = boto3.client('cloudwatch')
elbv2 = boto3.client('elbv2')
events = boto3.client('events')
lambda_client = boto3.client('lambda')

TARGET_GROUP_ARN = os.getenv('TARGET_GROUP_ARN')
TARGET_GROUP_NAME = os.getenv('TARGET_GROUP_NAME')
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL')

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for target group health monitoring
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        if event.get('source') == 'aws.events' and event.get('detail-type') == 'Health Check Retrigger':
            return handle_retrigger_event(event, context)
        
        if event.get('Records') and event.get('Records')[0].get('Sns'):
            return handle_alarm_event(event, context)
        
        return handle_direct_check(event, context)
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        send_slack_message(
            f"🚨 *Error in Health Monitor Lambda*\n"
            f"Error: {str(e)}\n"
            f"Time: {datetime.now(timezone.utc).isoformat()}"
        )
        raise

def handle_alarm_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle CloudWatch alarm triggered event
    """
    logger.info("Handling CloudWatch alarm event")
    
    # Extract alarm information
    sns_message = json.loads(event['Records'][0]['Sns']['Message'])
    alarm_name = sns_message.get('AlarmName', 'Unknown')
    alarm_state = sns_message.get('NewStateValue', 'Unknown')
    
    logger.info(f"Alarm {alarm_name} is in state: {alarm_state}")
    
    if alarm_state == 'ALARM':
        # Check current target group health
        health_status = check_target_group_health()
        
        if health_status['unhealthy_count'] > 0:
            # Send initial alert and set up retrigger
            message = create_unhealthy_message(health_status, alarm_name)
            send_slack_message(message)
            setup_retrigger(health_status)
        else:
            # False alarm - targets are actually healthy
            send_slack_message(
                f"✅ *False Alarm - Targets Healthy*\n"
                f"Alarm: {alarm_name}\n"
                f"Time: {datetime.now(timezone.utc).isoformat()}\n"
                f"All targets in the group are healthy."
            )
    
    return {'statusCode': 200, 'body': 'Alarm event processed'}

def handle_retrigger_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle retrigger event to check health again
    """
    logger.info("Handling retrigger event")
    detail = event.get('detail', {})
    original_timestamp = detail.get('original_timestamp')
    channel = detail.get('channel', SLACK_CHANNEL)
    health_status = check_target_group_health()
    
    if health_status['unhealthy_count'] > 0:
        message = create_still_unhealthy_message(health_status, original_timestamp)
        send_slack_message(message, channel)
        setup_retrigger(health_status, channel)
    else:
        message = create_recovery_message(health_status, original_timestamp)
        send_slack_message(message, channel)
        disable_retrigger_rule()
    
    return {'statusCode': 200, 'body': 'Retrigger event processed'}

def handle_direct_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle direct invocation for testing
    """
    logger.info("Handling direct check")
    
    health_status = check_target_group_health()
    message = create_health_summary_message(health_status)
    send_slack_message(message)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Health check completed',
            'health_status': health_status
        })
    }

def check_target_group_health() -> Dict[str, Any]:
    """
    Check the health status of targets in the target group
    """
    try:
        response = elbv2.describe_target_health(TargetGroupArn=TARGET_GROUP_ARN)
        
        total_targets = len(response['TargetHealthDescriptions'])
        healthy_targets = 0
        unhealthy_targets = []
        
        for target in response['TargetHealthDescriptions']:
            target_id = target['Target']['Id']
            health_state = target['TargetHealth']['State']
            reason = target['TargetHealth'].get('Reason', 'Unknown')
            
            if health_state == 'healthy':
                healthy_targets += 1
            else:
                unhealthy_targets.append({
                    'target_id': target_id,
                    'state': health_state,
                    'reason': reason
                })
        
        return {
            'total_targets': total_targets,
            'healthy_count': healthy_targets,
            'unhealthy_count': len(unhealthy_targets),
            'unhealthy_targets': unhealthy_targets,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking target group health: {str(e)}")
        raise

def create_unhealthy_message(health_status: Dict[str, Any], alarm_name: str) -> str:
    """
    Create message for when targets become unhealthy
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    
    message = f"🚨 *Target Group Health Alert*\n"
    message += f"Target Group: `{TARGET_GROUP_NAME}`\n"
    message += f"Alarm: `{alarm_name}`\n"
    message += f"Time: `{timestamp}`\n\n"
    message += f"**Health Status:**\n"
    message += f"• Total Targets: {health_status['total_targets']}\n"
    message += f"• Healthy: {health_status['healthy_count']}\n"
    message += f"• Unhealthy: {health_status['unhealthy_count']}\n\n"
    
    if health_status['unhealthy_targets']:
        message += "**Unhealthy Targets:**\n"
        for target in health_status['unhealthy_targets']:
            message += f"• `{target['target_id']}` - {target['state']} ({target['reason']})\n"
    
    message += f"\nI'll check again in 2 minutes and update this message."
    
    return message

def create_still_unhealthy_message(health_status: Dict[str, Any], original_timestamp: str) -> str:
    """
    Create message for when targets are still unhealthy
    """
    current_time = datetime.now(timezone.utc).isoformat()
    
    message = f"⚠️ *Target Group Still Unhealthy*\n"
    message += f"Target Group: `{TARGET_GROUP_NAME}`\n"
    message += f"Original Alert: `{original_timestamp}`\n"
    message += f"Current Time: `{current_time}`\n\n"
    message += f"**Current Health Status:**\n"
    message += f"• Total Targets: {health_status['total_targets']}\n"
    message += f"• Healthy: {health_status['healthy_count']}\n"
    message += f"• Unhealthy: {health_status['unhealthy_count']}\n\n"
    
    if health_status['unhealthy_targets']:
        message += "**Still Unhealthy Targets:**\n"
        for target in health_status['unhealthy_targets']:
            message += f"• `{target['target_id']}` - {target['state']} ({target['reason']})\n"
    
    message += f"\nI'll check again in 2 minutes."
    
    return message

def create_recovery_message(health_status: Dict[str, Any], original_timestamp: str) -> str:
    """
    Create message for when targets recover
    """
    current_time = datetime.now(timezone.utc).isoformat()
    
    message = f"✅ *Target Group Recovered*\n"
    message += f"Target Group: `{TARGET_GROUP_NAME}`\n"
    message += f"Original Alert: `{original_timestamp}`\n"
    message += f"Recovery Time: `{current_time}`\n\n"
    message += f"**Current Health Status:**\n"
    message += f"• Total Targets: {health_status['total_targets']}\n"
    message += f"• Healthy: {health_status['healthy_count']}\n"
    message += f"• Unhealthy: {health_status['unhealthy_count']}\n\n"
    message += f"All targets are now healthy! 🎉"
    
    return message

def create_health_summary_message(health_status: Dict[str, Any]) -> str:
    """
    Create general health summary message
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    
    message = f"📊 *Target Group Health Summary*\n"
    message += f"Target Group: `{TARGET_GROUP_NAME}`\n"
    message += f"Time: `{timestamp}`\n\n"
    message += f"**Health Status:**\n"
    message += f"• Total Targets: {health_status['total_targets']}\n"
    message += f"• Healthy: {health_status['healthy_count']}\n"
    message += f"• Unhealthy: {health_status['unhealthy_count']}\n"
    
    return message

def send_slack_message(message: str, channel: str = None) -> bool:
    """
    Send message to Slack using bot token
    """
    if not SLACK_BOT_TOKEN:
        logger.warning("SLACK_BOT_TOKEN not configured, skipping Slack notification")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "channel": channel or SLACK_CHANNEL,
            "text": message,
            "username": "QwapiQweeper",
            "icon_emoji": ":aws:"
        }
        
        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        
        response_data = response.json()
        if not response_data.get('ok'):
            logger.error(f"Slack API error: {response_data.get('error', 'Unknown error')}")
            return False
        
        logger.info("Slack message sent successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send Slack message: {str(e)}")
        return False

def setup_retrigger(health_status: Dict[str, Any], channel: str = None) -> None:
    """
    Set up EventBridge rule to retrigger this Lambda in 2 minutes
    """
    try:
        rule_name = f"target-group-health-retrigger-{TARGET_GROUP_NAME}"
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Create or update the rule
        events.put_rule(
            Name=rule_name,
            Description="Retrigger health check for target group",
            ScheduleExpression="rate(2 minutes)",
            State="ENABLED"
        )
        
        # Add this Lambda as a target
        events.put_targets(
            Rule=rule_name,
            Targets=[{
                'Id': '1',
                'Arn': context.invoked_function_arn,
                'Input': json.dumps({
                    'source': 'aws.events',
                    'detail-type': 'Health Check Retrigger',
                    'detail': {
                        'original_timestamp': current_time,
                        'channel': channel or SLACK_CHANNEL,
                        'target_group_arn': TARGET_GROUP_ARN
                    }
                })
            }]
        )
        
        logger.info(f"Retrigger rule {rule_name} set up successfully")
        
    except Exception as e:
        logger.error(f"Failed to set up retrigger rule: {str(e)}")

def disable_retrigger_rule() -> None:
    """
    Disable the retrigger rule
    """
    try:
        rule_name = f"target-group-health-retrigger-{TARGET_GROUP_NAME}"
        
        events.disable_rule(Name=rule_name)
        logger.info(f"Retrigger rule {rule_name} disabled")
        
    except Exception as e:
        logger.error(f"Failed to disable retrigger rule: {str(e)}")
