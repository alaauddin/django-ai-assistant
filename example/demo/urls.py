from django.urls import include, path

from demo import views


urlpatterns = [
    path("ai-assistant/", include("django_ai_assistant.urls")),
    path("", views.AgentListView.as_view(), name="agent_list"),
    path("<str:assistant_id>/", views.AIAssistantChatHomeView.as_view(), name="chat_home"),
    path(
        "<str:assistant_id>/thread/<int:thread_id>/",
        views.AIAssistantChatThreadView.as_view(),
        name="chat_thread",
    ),
]


