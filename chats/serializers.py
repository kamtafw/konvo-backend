from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Message

User = get_user_model()


class MessageSenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "profile_picture"]


class MessageSerializer(serializers.ModelSerializer):
    sender = MessageSenderSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "sender", "recipient", "message", "timestamp", "is_read"]
        read_only_fields = ["id", "timestamp"]


class ChatHistorySerializer(serializers.Serializer):
    messages = MessageSerializer(many=True, read_only=True)
