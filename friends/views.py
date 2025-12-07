from django.contrib.auth import get_user_model
from django.db import models
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.serializers import UserSerializer
from .models import Friendship, FriendRequest
from .serializers import FriendshipSerializer, FriendRequestSerializer

User = get_user_model()


# **Send a friend request (create FriendRequest where from_user=me)
# **List pending friend requests (get all FriendRequest where to_user=me)
# Accept friend request (creates Friendship)
# Reject friend request (FriendRequest)
# **List my friends (get all Friendship)


class FriendshipListView(ListAPIView):
    """
    API view to return the list of user's friends.
    User must be authenticated.
    """

    serializer_class = FriendshipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Friendship.objects.filter(models.Q(user1=user) | models.Q(user2=user))


class FriendSuggestionsList(ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        excluded_ids = get_excluded_ids(user)
        suggestions = User.objects.exclude(id__in=excluded_ids).exclude(id=user.id)[:10]

        return Response(UserSerializer(suggestions, many=True).data)


class FriendRequestListView(ListAPIView):
    """
    API view to return the list of friend requests sent to user.
    User must also be authenticated.
    """

    serializer_class = FriendRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return FriendRequest.objects.filter(to_user=user, status="pending")


class FriendRequestCreateView(APIView):
    """
    Create a new friend request from the authenticated user to another user.
    Expects a POST request with JSON body containing:
    - "to_user_id": the ID of the user to whom the friend request should be sent (string or int).
    Requirements and permission:
    - Only accessible to authenticated users (IsAuthenticated).
    Validation and behavior:
    - Returns 400 Bad Request if "to_user_id" is missing.
    - Returns 400 Bad Request if the authenticated user attempts to send a request to self.
    - Returns 404 Not Found if no user exists with the provided "to_user_id".
    - Returns 400 Bad Request if the target user is already a friend (checked via user_is_friend).
    - If a FriendRequest between the two users does not exist, creates one with status "pending".
    - If a FriendRequest already exists, resets its status to "pending" and saves it.
    Response:
    - On success, returns 201 Created with the serialized FriendRequest (using FriendRequestSerializer).
    - On failure, returns an appropriate error response with a JSON error message and the corresponding HTTP status code.
    Side effects:
    - May create a FriendRequest record or update an existing one.
    - Uses request.user as the sender (from_user) of the friend request.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        to_user_id = request.data.get("to_user_id")

        if not to_user_id:
            return Response({"error": "A 'to_user_id' is required."}, status=status.HTTP_400_BAD_REQUEST)

        if to_user_id == str(request.user.id):
            return Response({"error": "You cannot send a request to yourself."}, status=status.HTTP_400_BAD_REQUEST)

        to_user = User.objects.filter(id=to_user_id).first()
        if not to_user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if user_is_friend(request.user, to_user):
            return Response({"error": "User is already a friend."}, status=status.HTTP_400_BAD_REQUEST)

        friend_request, created = FriendRequest.objects.get_or_create(from_user=request.user, to_user=to_user, defaults={"status": "pending"})

        if not created:
            friend_request.status = "pending"
            friend_request.save()

        data = FriendRequestSerializer(friend_request).data

        return Response(data, status=status.HTTP_201_CREATED)


class FriendRequestAcceptView(APIView):
    """
    API view for accepting friend requests.
    This view handles POST requests to accept a pending friend request.
    Only authenticated users can access this endpoint.
    Attributes:
      permission_classes (list): Restricts access to authenticated users only.
    Methods:
      post(request, pk): Accepts a friend request by ID.
        Args:
          request (Request): The HTTP request object containing the authenticated user.
          pk (int): The primary key (ID) of the friend request to accept.
        Returns:
          Response: A success message if the friend request was accepted.
          Response: A 404 error if the friend request does not exist or is not pending.
        Raises:
          FriendRequest.DoesNotExist: If the friend request with the given ID,
            recipient (to_user), and status "pending" does not exist.
        Process:
          1. Retrieves the friend request by ID, ensuring it's addressed to the
              current user and has a "pending" status.
          2. Updates the friend request status to "accepted".
          3. Creates or retrieves a friendship relationship between the current
              user and the friend request sender.
          4. Returns a success response.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        try:
            friend_request = FriendRequest.objects.get(id=id, to_user=request.user, status="pending")
            friend_request.status = "accepted"
            friend_request.save()

            get_or_create_friendship(request.user, friend_request.from_user)

            return Response({"message": "Friend request accepted."})
        except FriendRequest.DoesNotExist:
            return Response({"error": "Friend request does not exist."}, status=status.HTTP_404_NOT_FOUND)


class FriendRequestRejectView(APIView):
    """
    FriendRequestReject is a Django REST Framework API view that handles the rejection of friend requests.
    Methods:
      post(request, pk):
        Rejects a friend request identified by the primary key (pk) if it exists and is pending.
        Updates the status of the friend request to "rejected" and saves the change to the database.
        Parameters:
          request (Request): The HTTP request object containing the user making the request.
          pk (int): The primary key of the friend request to be rejected.
        Returns:
          Response: A JSON response indicating the result of the operation.
            - On success: {"message": "Friend request rejected."}
            - On failure: {"error": "Friend request does not exist."} with a 404 status code if the request does not exist.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        try:
            friend_request = FriendRequest.objects.get(id=id, to_user=request.user, status="pending")
            friend_request.status = "rejected"
            friend_request.save()

            return Response({"message": "Friend request rejected."})
        except FriendRequest.DoesNotExist:
            return Response({"error": "Friend request does not exist."}, status=status.HTTP_404_NOT_FOUND)


def user_is_friend(user1, user2):
    """
    Check if two users (user1 & user2) are already friends.
    """
    return Friendship.objects.filter(models.Q(user1=user1, user2=user2) | models.Q(user1=user2, user2=user1)).exists()


def get_or_create_friendship(user1, user2):
    """
    Helper to ensure consistent friendship creation with smaller ID first
    """
    if str(user1.id) < str(user2.id):
        return Friendship.objects.get_or_create(user1=user1, user2=user2)
    else:
        return Friendship.objects.get_or_create(user1=user2, user2=user1)


def get_excluded_ids(user):
    friend_pairs = Friendship.objects.filter(models.Q(user1=user) | models.Q(user2=user)).values_list("user1_id", "user2_id")
    friend_ids = set()
    for user1, user2 in friend_pairs:
        friend_ids.add(user1)
        friend_ids.add(user2)

    pending_request_pairs = FriendRequest.objects.filter(models.Q(from_user=user) | models.Q(to_user=user), status="pending").values_list(
        "from_user_id", "to_user_id"
    )
    pending_request_ids = set()
    for user1, user2 in pending_request_pairs:
        pending_request_ids.add(user1)
        pending_request_ids.add(user2)

    return friend_ids.union(pending_request_ids)
