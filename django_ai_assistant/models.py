import json
import logging
import os
import shutil
from typing import Any, Sequence, cast

from django.conf import settings
from django.db import models
from django.db.models import F, Index, Manager
from django.utils.translation import gettext_lazy as _

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    messages_from_dict,
)
from django.contrib.auth import get_user_model
User = get_user_model()


class ThreadChannel(models.TextChoices):
    """Channels through which a thread can be conducted."""
    LIVE_CHAT = "live_chat", _("Live Chat")
    WHATSAPP = "whatsapp", _("WhatsApp")


class CustomerUser(models.Model):
    """External customer who interacts with AI agents."""
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    external_id = models.CharField(max_length=255, unique=True, null=True, blank=True, help_text="ID from external system (e.g. WhatsApp ID)")
    django_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="customer_users",
        null=True,
        blank=True,
        help_text="Associated Django user for authentication/internal use.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Customer User"
        verbose_name_plural = "Customer Users"

    def __str__(self) -> str:
        return self.full_name or self.email or self.external_id or f"Customer {self.id}"


class Thread(models.Model):
    """Thread model. A thread is a collection of messages between a user and the AI assistant.
    Also called conversation or session."""

    id: Any  # noqa: A003
    messages: Manager["Message"]
    name = models.CharField(max_length=255, blank=True)
    """Name of the thread. Can be blank."""
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ai_assistant_threads",
        null=True,
    )
    """User who created the thread. Can be null. Set to null/None when user is deleted."""
    assistant_id = models.CharField(max_length=255, blank=True)
    """Associated assistant ID. Can be empty."""
    customer_user = models.ForeignKey(
        CustomerUser,
        on_delete=models.SET_NULL,
        related_name="threads",
        null=True,
        blank=True,
    )
    """External customer associated with this thread."""
    channel = models.CharField(
        max_length=50,
        choices=ThreadChannel.choices,
        default=ThreadChannel.LIVE_CHAT,
        help_text="The channel through which this conversation is happening.",
    )
    """The channel used for this thread."""
    is_human_handoff = models.BooleanField(
        default=False,
        help_text="True if a human support agent should take over this conversation.",
    )
    """True if human intervention is requested/required."""
    created_at = models.DateTimeField(auto_now_add=True)
    """Date and time when the thread was created.
    Automatically set when the thread is created."""
    updated_at = models.DateTimeField(auto_now=True)
    """Date and time when the thread was last updated.
    Automatically set when the thread is updated."""

    class Meta:
        verbose_name = "Thread"
        verbose_name_plural = "Threads"
        ordering = ("-created_at",)
        indexes = (Index(F("created_at").desc(), name="thread_created_at_desc"),)

    def __str__(self) -> str:
        """Return the name of the thread as the string representation of the thread."""
        return self.name

    def __repr__(self) -> str:
        """Return the string representation of the thread like '<Thread name>'"""
        return f"<Thread {self.name}>"

    def get_messages(self, include_extra_messages: bool = False) -> list[BaseMessage]:
        """
        Get LangChain messages objects from the thread.

        Args:
            include_extra_messages (bool): Whether to include non-chat messages (like tool calls).

        Returns:
            list[BaseMessage]: List of messages
        """

        messages = messages_from_dict(
            cast(
                Sequence[dict[str, BaseMessage]],
                Message.objects.filter(thread=self)
                .order_by("created_at")
                .values_list("message", flat=True),
            )
        )
        if not include_extra_messages:
            messages = [
                m
                for m in messages
                if isinstance(m, HumanMessage | ChatMessage)
                or (isinstance(m, AIMessage) and not m.tool_calls)
            ]
        return cast(list[BaseMessage], messages)


class MessageSenderType(models.TextChoices):
    """Type of sender for a message."""
    AI = "ai", _("AI Assistant")
    CUSTOMER = "customer", _("Customer")
    SUPPORT = "support", _("Support Staff")
    ANONYMOUS = "anonymous", _("Anonymous User")


class Message(models.Model):
    """Message model. A message is a text that is part of a thread.
    A message can be sent by a user or the AI assistant.\n
    The message data is stored as a JSON field called `message`."""

    id: Any  # noqa: A003
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="messages")
    """Thread to which the message belongs."""
    thread_id: Any
    message = models.JSONField()
    """Message content. This is a serialized LangChain `BaseMessage` that was serialized
    with `message_to_dict` and can be deserialized with `messages_from_dict`."""
    sender_type = models.CharField(
        max_length=20,
        choices=MessageSenderType.choices,
        default=MessageSenderType.AI,
        help_text="Type of sender: AI, customer, support staff, or anonymous user.",
    )
    """The type of sender who created this message."""
    created_at = models.DateTimeField(auto_now_add=True)
    """Date and time when the message was created.
    Automatically set when the message is created."""

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ("created_at",)
        indexes = (Index(F("created_at"), name="message_created_at"),)

    def __str__(self) -> str:
        """Return internal message data from `message` attribute
        as the string representation of the message."""
        return json.dumps(self.message)

    def __repr__(self) -> str:
        """Return the string representation of the message like '<Message id at thread_id>'"""
        return f"<Message {self.id} at {self.thread_id}>"



class Tag(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Language(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Agent(models.Model):
    """Agent model. An agent is a configuration for an AI assistant.
    The agent configuration is stored in the database."""

    id: Any  # noqa: A003
    name = models.CharField(max_length=255, unique=True)
    """Name of the agent. Must be unique."""
    instructions = models.TextField()
    """Instructions for the AI assistant knowing what to do. This is the LLM system prompt."""
    model = models.CharField(max_length=255)
    """LLM model name to use for the assistant."""
    temperature = models.FloatField(default=1.0)
    """Temperature to use for the assistant LLM model. Defaults to 1.0."""
    display_name = models.CharField(max_length=255, blank=True)
    """Human-readable name for the agent. If blank, the unique name is used."""
    description = models.TextField(blank=True)
    """Description of the agent. Can be blank."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agents"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="categories", null=True, blank=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return f"{self.agent.name} - {self.name}" if self.agent else self.name


class FAQ(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="faqs", null=True, blank=True)
    question = models.CharField(max_length=500)
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, blank=True)
    

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question

class FAQTag(models.Model):
    faq = models.ForeignKey(FAQ, on_delete=models.CASCADE, related_name="tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="faqs")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_faq_tags")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="updated_faq_tags")

    class Meta:
        verbose_name = "FAQ Tag"
        verbose_name_plural = "FAQ Tags"




class ArticleType(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Article(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="articles", null=True, blank=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    article_type = models.ForeignKey(ArticleType, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_articles")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="updated_articles")

    def __str__(self):
        return self.title


