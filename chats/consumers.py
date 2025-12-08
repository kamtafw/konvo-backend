import json
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Message

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if self.user.is_anonymous:
            await self.close()
            return

        self.user_channel = f"user_{self.user.id}"

        await self.channel_layer.group_add(self.user_channel, self.channel_name)

        await self.accept()

        await self.set_user_online(True)

        print(f"✅ {self.user.username} connected")

    async def disconnect(self, close_code):
        if hasattr(self, "user_channel"):
            await self.channel_layer.group_discard(self.user_channel, self.channel_name)

        if not self.user.is_anonymous:
            await self.set_user_online(False)
            print(f"❌ {self.user.username} disconnected")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "chat_message":
                await self.handle_chat_message(data)
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
        await self.channel_layer.group_send(f"user_{recipient.id}", {"type": "chat_message_handler", "message_data": message_data})

        print(f"📨 {self.user.username} → {recipient.username}: {message_text[:30]}")

    async def chat_message_handler(self, event):
        message_data = event["message_data"]
        await self.send(text_data=json.dumps(message_data))

    @database_sync_to_async
    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def save_message(self, sender, recipient, message_text):
        return Message.objects.create(sender=sender, recipient=recipient, message=message_text)

    @database_sync_to_async
    def set_user_online(self, is_online):
        self.user.is_online = is_online
        self.user.save(update_fields=["is_online"])
