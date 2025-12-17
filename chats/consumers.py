import json
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Message

User = get_user_model()


class RealtimeConsumer(AsyncWebsocketConsumer):
    """
    Handles ALL real-time updates: chat messages, friend requests, status updates, etc.
    """

    async def connect(self):
        """Called when WebSocket connection is established"""
        self.user = self.scope["user"]

        if self.user.is_anonymous:
            await self.close()
            return

        self.user_channel = f"user_{self.user.id}"

        await self.channel_layer.group_add(self.user_channel, self.channel_name)
        await self.accept()

        # set user as online and broadcast to friends
        await self.set_user_online(True)
        await self.broadcast_online_status(True)

        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection",
                    "status": "connected",
                    "is_online": True,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )
        print(f"✅ {self.user.username} connected to realtime channel")

    async def disconnect(self, close_code):
        """Called when WebSocket connection is closed"""
        if hasattr(self, "user_channel"):
            await self.channel_layer.group_discard(self.user_channel, self.channel_name)

        if not self.user.is_anonymous:
            await self.set_user_online(False)
            await self.broadcast_online_status(False)
            print(f"❌ {self.user.username} disconnected from realtime channel")

    async def receive(self, text_data):
        """Route different message types"""

        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "chat_message":
                await self.handle_chat_message(data)
            # add more client-sent message types here if needed
            else:
                await self.send(text_data=json.dumps({"type": "error", "message": f"Unknown message type: {message_type}"}))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "message": "Invalid JSON"}))
        except Exception as e:
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    async def handle_chat_message(self, data):
        message_text = data.get("message", "").strip()
        recipient_id = data.get("recipient_id")
        temp_id = data.get("temp_id")

        if not message_text:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": "Message cannot be empty",
                        "temp_id": temp_id,
                    }
                )
            )
            return

        if not recipient_id:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": "Recipient ID required",
                        "temp_id": temp_id,
                    }
                )
            )
            return

        # check if recipient exists and is friend with sender
        recipient = await self.get_user(recipient_id)
        if not recipient:
            if not message_text:
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "message": "Recipient not found",
                            "temp_id": temp_id,
                        }
                    )
                )
                return

        # save message to database
        message = await self.save_message(sender=self.user, recipient=recipient, message_text=message_text)

        message_data = {
            "type": "chat_message",
            "id": message.id,
            "message": message.message,
            "sender": {
                "id": self.user.id,
                "username": self.user.username,
                "profile_picture": self.user.profile_picture,
            },
            "recipient_id": recipient.id,
            "timestamp": message.timestamp.isoformat(),
            "is_read": False,
            "temp_id": temp_id,
        }

        # send confirmation to sender
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_sent",
                    "id": message.id,
                    "timestamp": message.timestamp.isoformat(),
                    "temp_id": temp_id,
                }
            )
        )

        # send message to recipient (if they're online)
        await self.channel_layer.group_send(f"user_{recipient.id}", {"type": "chat_message_handler", "data": message_data})

        print(f"📨 {self.user.username} → {recipient.username}: {message_text[:30]}")

    # ==================== HANDLERS (called by channel_layer.group_send) ====================

    async def chat_message_handler(self, event):
        """Handler for sending chat messages to WebSocket"""
        message_data = event["data"]
        await self.send(text_data=json.dumps(message_data))

    async def friend_request_handler(self, event):
        """Handler for friend request notifications"""
        request_data = event["data"]
        print(f"Friend request sent: {request_data}")
        await self.send(text_data=json.dumps(request_data))

    async def friend_request_accepted_handler(self, event):
        """Handler for accepted friend request notifications"""
        request_data = event["data"]
        print(f"Friend request accepted: {request_data}")
        await self.send(text_data=json.dumps(request_data))

    async def friend_request_rejected_handler(self, event):
        """Handler for rejected friend request notifications"""
        request_data = event["data"]
        await self.send(text_data=json.dumps(request_data))

    async def user_status_handler(self, event):
        """Handler for online status broadcasts from other users"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "user_status",
                    "user_id": event["user_id"],
                    "is_online": event["is_online"],
                    "timestamp": event["timestamp"],
                }
            )
        )

    # ==================== DATABASE OPERATIONS ====================

    @database_sync_to_async
    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def get_user_friends(self):
        """Get list of user's friends"""
        try:
            from friends.models import Friendship

            friend_pairs = Friendship.objects.filter(Q(user1=self.user) | Q(user2=self.user)).values_list("user1_id", "user2_id")
            friend_ids = set()
            for user1, user2 in friend_pairs:
                friend_ids.add(user1)
                friend_ids.add(user2)

            friends = list(User.objects.filter(id__in=friend_ids).exclude(id=self.user.id))
            return friends
        except Exception as e:
            print(f"Error fetching friends: {e}")
            return []

    @database_sync_to_async
    def save_message(self, sender, recipient, message_text):
        return Message.objects.create(sender=sender, recipient=recipient, message=message_text)

    @database_sync_to_async
    def set_user_online(self, is_online):
        self.user.last_seen = timezone.now()
        self.user.is_online = is_online
        self.user.save(update_fields=["is_online", "last_seen"])

    async def broadcast_online_status(self, is_online):
        """Broadcast user's online status to all friends"""
        friends = await self.get_user_friends()

        status_data = {"type": "user_status_handler", "user_id": self.user.id, "is_online": is_online, "timestamp": self.user.last_seen.isoformat()}

        for friend in friends:
            await self.channel_layer.group_send(f"user_{friend.id}", status_data)
