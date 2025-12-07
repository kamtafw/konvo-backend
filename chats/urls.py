from django.urls import path
from .views import chat_history

urlpatterns = [
    path("<int:friend_id>/", chat_history, name="chat_history"),
]
