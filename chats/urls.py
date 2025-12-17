from django.urls import path
from .views import chat_history, recent_chats,mark_messages_read

urlpatterns = [
    path("recent/", recent_chats, name="recent_chats"),
    path("<int:friend_id>/", chat_history, name="chat_history"),
    path("<int:friend_id>/mark-read/", mark_messages_read, name="mark_messages_read"),
]
