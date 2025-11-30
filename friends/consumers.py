import json
from channels.generic.websocket import AsyncWebsocketConsumer


class FriendConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "friend_consumer"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        event_type = data.get("type")
        message = data.get("message")
        # payload = data.get('payload', {})

        await self.channel_layer.group_send(self.group_name, {"type": "echo", "message": message})

    async def echo(self, event):
        message = event["message"]
        await self.send(text_data=json.dumps({"message": f"ECHO: {message}"}))
