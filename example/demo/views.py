from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic.base import TemplateView

from pydantic import ValidationError

from django_ai_assistant.api.schemas import (
    ThreadIn,
    ThreadMessageIn,
)
from django_ai_assistant.helpers.use_cases import (
    create_message,
    create_thread,
    get_thread_messages,
    get_threads,
)
from django_ai_assistant.models import (
    Thread,
    Agent,
    Category,
    FAQ,
    Article,
    Language,
    ArticleType,
    ThreadChannel,
)


class KnowledgeBaseView(LoginRequiredMixin, TemplateView):
    template_name = "demo/knowledge_base.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assistant_id = self.kwargs.get("assistant_id")
        agent = get_object_or_404(Agent, name=assistant_id)
        
        context["agent"] = agent
        context["assistant_id"] = assistant_id
        
        # Stats filtered by agent
        context["stats"] = {
            "categories": Category.objects.filter(agent=agent).count(),
            "articles": Article.objects.filter(agent=agent).count(),
            "faqs": FAQ.objects.filter(agent=agent).count(),
            "tickets": 0, # Placeholder
            "external_sites": 0, # Placeholder
        }

        # Tab handling
        active_tab = self.request.GET.get("tab", "articles")
        context["active_tab"] = active_tab

        # Data retrieval based on active tab
        if active_tab == "articles":
            context["items"] = Article.objects.filter(agent=agent).select_related("category", "agent", "language", "article_type")
        elif active_tab == "faqs":
            context["items"] = FAQ.objects.filter(agent=agent).select_related("agent", "language")
        elif active_tab == "categories":
            context["items"] = Category.objects.filter(agent=agent).select_related("agent")

        # Filters (Simplified for now)
        context["languages"] = Language.objects.all()
        context["categories"] = Category.objects.filter(agent=agent)
        context["article_types"] = ArticleType.objects.all()
        
        return context



from django.views.generic import ListView

from django.db.models import Count

class AgentListView(LoginRequiredMixin, ListView):
    model = Agent
    template_name = "demo/agent_list.html"
    context_object_name = "agents"

    def get_queryset(self):
        # Annotate with counts for the enhanced UI
        return Agent.objects.annotate(
            article_count=Count('articles', distinct=True),
            faq_count=Count('faqs', distinct=True)
        ).all()


class BaseAIAssistantView(LoginRequiredMixin, TemplateView):
    def get_assistant_id(self, **kwargs):
        """Returns the assistant_id from URL or defaults."""
        return self.kwargs.get("assistant_id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assistant_id = self.get_assistant_id(**kwargs)
        agent = get_object_or_404(Agent, name=assistant_id)

        # For staff dashboard, get ALL threads for this assistant (not filtered by user)
        # This allows staff to see threads from anonymous users and other customers
        threads = get_threads(user=None, assistant_id=assistant_id)
        
        context.update(
            {
                "agent": agent,
                "assistant_id": assistant_id,
                "threads": list(threads),  # Convert generator to list
            }
        )
        return context


class AIAssistantChatThreadView(BaseAIAssistantView):
    template_name = "demo/chat_thread.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thread_id = self.kwargs["thread_id"]
        thread = get_object_or_404(Thread, id=thread_id)
        
        # For staff dashboard, get messages without user filter
        # This allows staff to view threads from anonymous users
        thread_messages = get_thread_messages(
            thread=thread,
            user=None,  # Staff can view any thread
            request=self.request,
        )
        
        # Fetch Django Message objects to get sender_type
        from django_ai_assistant.models import Message as DjangoMessage
        django_messages = DjangoMessage.objects.filter(thread=thread).order_by('created_at')
        
        # Create a mapping of message IDs to sender types
        sender_type_map = {str(msg.id): msg.sender_type for msg in django_messages}
        
        # Add sender_type attribute to each LangChain message
        for msg in thread_messages:
            if hasattr(msg, 'id') and msg.id:
                msg.sender_type = sender_type_map.get(str(msg.id), 'ai')
            else:
                msg.sender_type = 'ai'
        
        context.update(
            {
                "thread_id": self.kwargs["thread_id"],
                "thread_messages": thread_messages,
                "thread": thread,
            }
        )
        return context

    # POST to create message:
    def post(self, request, *args, **kwargs):
        assistant_id = self.get_assistant_id()
        thread_id = self.kwargs["thread_id"]
        thread = get_object_or_404(Thread, id=thread_id)

        try:
            message = ThreadMessageIn(
                assistant_id=assistant_id,
                content=request.POST.get("content") or None,
            )
        except ValidationError:
            messages.error(request, "Invalid message data")
            return redirect("chat_thread", assistant_id=assistant_id, thread_id=thread_id)

        # When staff replies, we activate handoff and skip the AI response
        thread.is_human_handoff = True
        thread.save()

        create_message(
            assistant_id=assistant_id,
            thread=thread,
            user=request.user,
            content=message.content,
            request=request,
            skip_ai=True,
            sender_type='support',  # Explicitly mark as support staff
        )
        # Check thread channel to redirect back to correct view
        if thread.channel == ThreadChannel.WHATSAPP:
            return redirect("whatsapp_chat_thread", assistant_id=assistant_id, thread_id=thread_id)
        return redirect("live_chat_thread", assistant_id=assistant_id, thread_id=thread_id)


class AgentChatHomeView(TemplateView):
    """View for customers to start a chat with the AI Agent. Public, no login required."""
    template_name = "demo/agent_chat.html"

    def get_assistant_id(self, **kwargs):
        return self.kwargs.get("assistant_id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assistant_id = self.get_assistant_id(**kwargs)
        agent = get_object_or_404(Agent, name=assistant_id)
        context["agent"] = agent
        context["assistant_id"] = assistant_id
        return context

    def post(self, request, *args, **kwargs):
        assistant_id = self.get_assistant_id()
        try:
            data = {k: v for k, v in request.POST.items() if k in ThreadIn.model_fields}
            thread_data = ThreadIn(**data)
        except ValidationError:
            messages.error(request, "Invalid thread data")
            return redirect("agent_chat_home", assistant_id=assistant_id)

        # Allow anonymous users
        user = request.user if request.user.is_authenticated else None
        thread = create_thread(
            name=thread_data.name,
            user=user,
            request=request,
            assistant_id=assistant_id,
        )
        # Customer started chats are LIVE_CHAT by default
        thread.channel = ThreadChannel.LIVE_CHAT
        thread.save()
        
        return redirect("agent_chat_thread", assistant_id=assistant_id, thread_id=thread.id)


class AgentChatThreadView(TemplateView):
    """View for customers to chat with the AI Agent in a dedicated UI. Public, no login required."""
    template_name = "demo/agent_chat_thread.html"

    def get_assistant_id(self, **kwargs):
        return self.kwargs.get("assistant_id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assistant_id = self.get_assistant_id(**kwargs)
        agent = get_object_or_404(Agent, name=assistant_id)
        thread_id = self.kwargs["thread_id"]
        thread = get_object_or_404(Thread, id=thread_id)
        
        # Allow anonymous users
        user = self.request.user if self.request.user.is_authenticated else None
        thread_messages = get_thread_messages(
            thread=thread,
            user=user,
            request=self.request,
        )
        
        # Fetch Django Message objects to get sender_type
        from django_ai_assistant.models import Message as DjangoMessage
        django_messages = DjangoMessage.objects.filter(thread=thread).order_by('created_at')
        
        # Create a mapping of message IDs to sender types
        sender_type_map = {str(msg.id): msg.sender_type for msg in django_messages}
        
        # Add sender_type attribute to each LangChain message
        for msg in thread_messages:
            if hasattr(msg, 'id') and msg.id:
                msg.sender_type = sender_type_map.get(str(msg.id), 'ai')
            else:
                msg.sender_type = 'ai'
        
        context.update({
            "agent": agent,
            "assistant_id": assistant_id,
            "thread_id": thread_id,
            "thread_messages": thread_messages,
            "thread": thread,
            "is_agent_view": True,
        })
        return context

    def post(self, request, *args, **kwargs):
        assistant_id = self.get_assistant_id()
        thread_id = self.kwargs["thread_id"]
        thread = get_object_or_404(Thread, id=thread_id)

        try:
            message = ThreadMessageIn(
                assistant_id=assistant_id,
                content=request.POST.get("content") or None,
            )
        except ValidationError:
            messages.error(request, "Invalid message data")
            return redirect("agent_chat_thread", assistant_id=assistant_id, thread_id=thread_id)

        # Allow anonymous users
        user = request.user if request.user.is_authenticated else None
        # If handoff is active, we skip the AI response for customer messages too
        create_message(
            assistant_id=assistant_id,
            thread=thread,
            user=user,
            content=message.content,
            request=request,
            skip_ai=thread.is_human_handoff,
        )
        return redirect("agent_chat_thread", assistant_id=assistant_id, thread_id=thread_id)


class AIAssistantChatHomeView(BaseAIAssistantView):
    """Main landing or redirect to correct chat interface."""
    def get(self, request, *args, **kwargs):
        return redirect("agent_chat_home", assistant_id=self.get_assistant_id())




class LiveChatView(BaseAIAssistantView):
    template_name = "demo/chat_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_channel"] = ThreadChannel.LIVE_CHAT
        context["threads"] = [t for t in context["threads"] if t.channel == ThreadChannel.LIVE_CHAT]
        context["page_title"] = "Live Chats"
        return context


class WhatsAppChatView(BaseAIAssistantView):
    template_name = "demo/chat_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_channel"] = ThreadChannel.WHATSAPP
        context["threads"] = [t for t in context["threads"] if t.channel == ThreadChannel.WHATSAPP]
        context["page_title"] = "WhatsApp Chats"
        return context


class LiveChatThreadView(AIAssistantChatThreadView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_channel"] = ThreadChannel.LIVE_CHAT
        context["threads"] = [t for t in context["threads"] if t.channel == ThreadChannel.LIVE_CHAT]
        context["page_title"] = "Live Chats"
        return context


class WhatsAppChatThreadView(AIAssistantChatThreadView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_channel"] = ThreadChannel.WHATSAPP
        context["threads"] = [t for t in context["threads"] if t.channel == ThreadChannel.WHATSAPP]
        context["page_title"] = "WhatsApp Chats"
        return context


class ThreadHandoffView(LoginRequiredMixin, View):
    """View to request human handoff."""
    def post(self, request, *args, **kwargs):
        thread_id = self.kwargs["thread_id"]
        assistant_id = self.kwargs["assistant_id"]
        thread = get_object_or_404(Thread, id=thread_id)
        thread.is_human_handoff = True
        thread.save()
        messages.success(request, "A human support agent has been notified.")
        return redirect("agent_chat_thread", assistant_id=assistant_id, thread_id=thread_id)
