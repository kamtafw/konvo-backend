from django.urls import path
from .views import (
    FriendshipListView,
    FriendRequestListView,
    FriendRequestCreateView,
    FriendRequestAcceptView,
    FriendRequestRejectView,
    FriendSuggestionsList,
)

urlpatterns = [
    path("", FriendshipListView.as_view(), name="list-friends"),
    path("request/", FriendRequestCreateView.as_view(), name="send-request"),
    path("requests/", FriendRequestListView.as_view(), name="list-requests"),
    path("suggestions/", FriendSuggestionsList.as_view(), name="list-suggestions"),
    path("accept/<str:id>/", FriendRequestAcceptView.as_view(), name="accept-request"),
    path("reject/<str:id>/", FriendRequestRejectView.as_view(), name="reject-request"),
]
