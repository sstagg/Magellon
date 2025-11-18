from fastapi import APIRouter, Depends
from uuid import UUID
import logging
import slack
from slack.errors import SlackApiError

from config import app_settings
from models.pydantic_models import SlackMessage
from dependencies.auth import get_current_user_id

###
# Config
###

slack_router = APIRouter()
logger = logging.getLogger(__name__)

client = slack.WebClient(app_settings.SLACK_TOKEN)


@slack_router.post('/send_message_to_slack')
async def send_message_to_slack(
    message: SlackMessage,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
) -> dict:
    """
    Send a message to a Slack channel.

    **Requires:** Authentication
    **Security:** Authenticated users can send Slack notifications
    """
    # channel name can be with or without #
    # channel = "slack-api-testing"
    channel = message.channel or "general"
    logger.info(f"User {user_id} sending Slack message to channel: {channel}")

    try:
        response = client.chat_postMessage(channel=channel, text=message.text)
        if not response["ok"]:
            logger.error(f"Failed to send Slack message for user {user_id} to channel {channel}")
            raise SlackApiError("Failed to send message to Slack")

        logger.info(f"User {user_id} successfully sent Slack message to channel: {channel}")
    except SlackApiError as e:
        logger.error(f"Slack API error for user {user_id}: {str(e)}")
        raise e

    return {
        'message': 'success',
        'user': message.text,
        'sent_by': str(user_id)
    }


@slack_router.get('/user/{email}')
async def get_user(
    email: str,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
) -> dict:
    """
    Look up a Slack user by email address.

    **Requires:** Authentication
    **Security:** Authenticated users can lookup Slack users
    """
    logger.debug(f"User {user_id} looking up Slack user: {email}")

    try:
        user = client.users_lookupByEmail(email=email).data

        logger.info(f"User {user_id} successfully looked up Slack user: {email}")
        return {
            'message': 'success',
            'user': user['user']
        }
    except SlackApiError as e:
        logger.error(f"Slack API error for user {user_id} looking up {email}: {str(e)}")
        raise e


@slack_router.post('/msg/{user_email}')
async def send_message_to_user(
    user_email: str,
    message: SlackMessage,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
) -> dict:
    """
    Send a direct message to a Slack user by email.

    **Requires:** Authentication
    **Security:** Authenticated users can send direct messages via Slack
    """
    logger.info(f"User {user_id} sending Slack DM to: {user_email}")

    try:
        user = client.users_lookupByEmail(email=user_email).data['user']
        user_name = user['real_name']

        client.chat_postMessage(
            channel=user['id'],
            text=f'Hi, {user_name}. {message.text}'
        )

        logger.info(f"User {user_id} successfully sent Slack DM to: {user_email}")
        return {
            'status': 'success',
            'sent_by': str(user_id)
        }
    except SlackApiError as e:
        logger.error(f"Slack API error for user {user_id} sending DM to {user_email}: {str(e)}")
        return {
            'status': 'error',
            'message': 'User not found'
        }
    except Exception as e:
        logger.error(f"Error for user {user_id} sending Slack DM to {user_email}: {str(e)}")
        return {
            'status': 'error',
            'message': 'User not found'
        }
