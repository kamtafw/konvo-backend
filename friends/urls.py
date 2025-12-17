from django.urls import path
from .views import (
    FriendshipListView,
    FriendRequestListView,
    FriendRequestAcceptView,
    FriendRequestRejectView,
    friend_suggestions,
    send_friend_request,
)

urlpatterns = [
    path("", FriendshipListView.as_view(), name="list-friends"),
    path("request/", send_friend_request, name="send-request"),
    path("requests/", FriendRequestListView.as_view(), name="list-requests"),
    path("suggestions/", friend_suggestions, name="friend-suggestions"),
    path("accept/<str:id>/", FriendRequestAcceptView.as_view(), name="accept-request"),
    path("reject/<str:id>/", FriendRequestRejectView.as_view(), name="reject-request"),
]
