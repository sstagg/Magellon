from fastapi import APIRouter
import slack
from slack.errors import SlackApiError

from config.config import SLACK_TOKEN
from models.pydantic_models import SlackMessage

###
# Config
###

slack_router = APIRouter()

client = slack.WebClient(SLACK_TOKEN)


@slack_router.post('/send_message_to_slack')
async def send_message_to_slack(message: SlackMessage) -> dict:
    # channel name can be with or without #
    # channel = "slack-api-testing"
    channel = message.channel or "general"
    try:
        response = client.chat_postMessage(channel=channel, text=message.text)
        if not response["ok"]:
            raise SlackApiError("Failed to send message to Slack")
    except SlackApiError as e:
        raise e

    return {
        'message': 'success',
        'user': message.text
    }


@slack_router.get('/user/{email}')
async def get_user(email: str) -> dict:
    user = client.users_lookupByEmail(email=email).data

    return {
        'message': 'success',
        'user': user['user']
    }


@slack_router.post('/msg/{user_email}')
async def send_message_to_user(user_email: str, message: SlackMessage) -> dict:
    try:
        user = client.users_lookupByEmail(email=user_email).data['user']
        user_name = user['real_name']

        client.chat_postMessage(
            channel=user['id'],
            text=f'Hi, {user_name}. {message.text}'
        )

        return {
            'status': 'success',
        }
    except:  # noqa: E722
        return {
            'status': 'error',
            'message': 'User not found'
        }
