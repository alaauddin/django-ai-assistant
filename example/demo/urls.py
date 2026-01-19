from django.urls import include, path

from demo import views


urlpatterns = [
    path("ai-assistant/", include("django_ai_assistant.urls")),
    path("<str:assistant_id>/knowledge-base/", views.KnowledgeBaseView.as_view(), name="knowledge_base"),
    path("", views.AgentListView.as_view(), name="agent_list"),

    # Agent Chat (Customer Facing)
    path("<str:assistant_id>/chat/", views.AgentChatHomeView.as_view(), name="agent_chat_home"),
    path(
        "<str:assistant_id>/chat/thread/<int:thread_id>/",
        views.AgentChatThreadView.as_view(),
        name="agent_chat_thread",
    ),
    path(
        "<str:assistant_id>/chat/thread/<int:thread_id>/handoff/",
        views.ThreadHandoffView.as_view(),
        name="thread_handoff",
    ),

    # Support / Dashboard Views (Staff Facing)
    path("<str:assistant_id>/", views.AIAssistantChatHomeView.as_view(), name="chat_home"),
    path(
        "<str:assistant_id>/live-chat/", views.LiveChatView.as_view(), name="live_chat"
    ),
    path(
        "<str:assistant_id>/live-chat/thread/<int:thread_id>/",
        views.LiveChatThreadView.as_view(),
        name="live_chat_thread",
    ),
    path(
        "<str:assistant_id>/whatsapp-chat/",
        views.WhatsAppChatView.as_view(),
        name="whatsapp_chat",
    ),
    path(
        "<str:assistant_id>/whatsapp-chat/thread/<int:thread_id>/",
        views.WhatsAppChatThreadView.as_view(),
        name="whatsapp_chat_thread",
    ),
    path(
        "<str:assistant_id>/thread/<int:thread_id>/",
        views.AIAssistantChatThreadView.as_view(),
        name="chat_thread",
    ),
]
