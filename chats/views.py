from django.db.models import Q
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from friends.models import Friendship
from .models import Message
from .serializers import MessageSerializer

User = get_user_model()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chat_history(request, friend_id):
    """
    Get last 50 messages between current user and friend_id
    """
    user = request.user

    # get messages where user and friend are either sender or recipient
    messages = Message.objects.filter(Q(sender=user, recipient_id=friend_id) | Q(sender_id=friend_id, recipient=user)).order_by("-timestamp")[:50]
    messages = list(reversed(messages))  # reverse so oldest is first

    serializer = MessageSerializer(messages, many=True)

    return Response({"messages": serializer.data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recent_chats(request):
    """
    Get list of friends user has chatted with, ordered by last message
    """
    user = request.user

    friendships = Friendship.objects.filter(Q(user1=user) | Q(user2=user))

    chats = []

    for friendship in friendships:
        friend = friendship.user2 if friendship.user1 == user else friendship.user1
        last_message = Message.objects.filter(Q(sender=user, recipient=friend) | Q(sender=friend, recipient=user)).order_by("-timestamp").first()

        if last_message:
            unread_count = Message.objects.filter(sender=friend, recipient=user, is_read=False).count()

            chats.append(
                {
                    "friend": {
                        "id": friend.id,
                        "username": friend.username,
                        "profile_picture": friend.profile_picture,
                        "is_online": friend.is_online,
                    },
                    "last_message": MessageSerializer(last_message).data,
                    "unread_count": unread_count,
                }
            )

    chats.sort(key=lambda x: x["last_message"]["timestamp"], reverse=True)

    return Response({"chats": chats})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_messages_read(request, friend_id):
    """
    Mark all messages from friend_id as read
    """
    user = request.user

    updated = Message.objects.filter(sender_id=friend_id, recipient=user, is_read=False).update(is_read=True)

    return Response({"marked_read": updated})
