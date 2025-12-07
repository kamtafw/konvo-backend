from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Message


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chat_history(request, friend_id):
    """
    Get last 50 messages between current user and friend_id
    """
    user = request.user

    # get messages where user and friend are either sender or recipient
    messages = Message.objects.filter(Q(sender=user, recipient_id=friend_id) | Q(sender_id=friend_id, recipient=user)).order_by("-timestamp")[:50]
    messages = reversed(messages)  # reverse so oldest is first

    return Response(
        {
            "messages": [
                {
                    "id": msg.id,
                    "message": msg.message,
                    "sender": {
                        "id": msg.sender.id,
                        "username": msg.sender.username,
                    },
                    "recipient_id": msg.recipient.id,
                    "timestamp": msg.timestamp.isoformat(),
                    "is_read": msg.is_read,
                }
                for msg in messages
            ]
        }
    )
