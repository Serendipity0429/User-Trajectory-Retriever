from django.urls import path
from .views import (
    MessageListView,
    MessageDetailView,
    PinMessageView,
    DeleteMessageView,
    CreateMessageView,
    ReplyMessageView,
    SentMessageListView,
)

app_name = "msg_system"

urlpatterns = [
    path("", MessageListView.as_view(), name="message_list"),
    path("sent/", SentMessageListView.as_view(), name="sent_message_list"),
    path("create/", CreateMessageView.as_view(), name="create_message"),
    path("<int:pk>/", MessageDetailView.as_view(), name="message_detail"),
    path("<int:pk>/pin/", PinMessageView.as_view(), name="pin_message"),
    path("<int:pk>/delete/", DeleteMessageView.as_view(), name="delete_message"),
    path("reply/<int:pk>/", ReplyMessageView.as_view(), name="reply_message"),
]
