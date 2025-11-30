from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import FriendRequest, Friendship

User = get_user_model()


class FriendSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone_number", "username", "email", "bio", "profile_picture", "last_seen", "is_online"]


class FriendshipSerializer(serializers.ModelSerializer):
    friend = serializers.SerializerMethodField()

    class Meta:
        model = Friendship
        fields = ["friend"]

    def get_friend(self, obj):
        me = self.context["request"].user
        friend = obj.user2 if obj.user1 == me else obj.user1
        return FriendSerializer(friend, context=self.context).data


class FriendRequestSerializer(serializers.ModelSerializer):
    from_user = FriendSerializer(read_only=True)
    to_user = FriendSerializer(read_only=True)

    class Meta:
        model = FriendRequest
        fields = ["id", "from_user", "to_user", "status", "created_at"]
