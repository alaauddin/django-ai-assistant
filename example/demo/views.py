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
from django_ai_assistant.models import Thread, Agent


from django.views.generic import ListView

class AgentListView(LoginRequiredMixin, ListView):
    model = Agent
    template_name = "demo/agent_list.html"
    context_object_name = "agents"

    def get_queryset(self):
        # Ensure we return valid agents that are in the registry or DB
        # For now, just all DB agents since we are moving to DB-first
        return Agent.objects.all()


class BaseAIAssistantView(LoginRequiredMixin, TemplateView):
    def get_assistant_id(self, **kwargs):
        """Returns the assistant_id from URL or defaults."""
        return self.kwargs.get("assistant_id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assistant_id = self.get_assistant_id(**kwargs)

        # Filter threads by the current assistant if selected
        threads = get_threads(user=self.request.user, assistant_id=assistant_id)
        
        context.update(
            {
                "assistant_id": assistant_id,
                "threads": list(threads),  # Convert generator to list
            }
        )
        return context


class AIAssistantChatHomeView(BaseAIAssistantView):
    template_name = "demo/chat_home.html"

    # POST to create thread:
    def post(self, request, *args, **kwargs):
        assistant_id = self.get_assistant_id()
        try:
            # We filter POST data to avoid validation errors with extra fields like csrfmiddlewaretoken
            data = {k: v for k, v in request.POST.items() if k in ThreadIn.model_fields}
            thread_data = ThreadIn(**data)
        except ValidationError:

            messages.error(request, "Invalid thread data")
            return redirect("chat_home", assistant_id=assistant_id)

        thread = create_thread(
            name=thread_data.name,
            user=request.user,
            request=request,
            assistant_id=assistant_id,
        )
        return redirect("chat_thread", assistant_id=assistant_id, thread_id=thread.id)


class AIAssistantChatThreadView(BaseAIAssistantView):
    template_name = "demo/chat_thread.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thread_id = self.kwargs["thread_id"]
        thread = get_object_or_404(Thread, id=thread_id)
        
        # Ensure the thread belongs to the current assistant context if we enforce that
        # valid_assistant_id = thread.assistant_id
        
        thread_messages = get_thread_messages(
            thread=thread,
            user=self.request.user,
            request=self.request,
        )
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

        create_message(
            assistant_id=assistant_id,
            thread=thread,
            user=request.user,
            content=message.content,
            request=request,
        )
        return redirect("chat_thread", assistant_id=assistant_id, thread_id=thread_id)
