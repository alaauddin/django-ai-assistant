from typing import TYPE_CHECKING

from django.db import transaction

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    message_to_dict,
)


if TYPE_CHECKING:
    from django_ai_assistant.models import Message as DjangoMessage
    from django_ai_assistant.models import Thread


@transaction.atomic
def save_django_messages(
    messages: list[BaseMessage], 
    thread: "Thread",
    sender_type: str | None = None
) -> list["DjangoMessage"]:
    """
    Save a list of messages to the Django database.
    Note: Changes the message objects in place by changing each message.id to the Django ID.

    Args:
        messages (list[BaseMessage]): The list of messages to save.
        thread (Thread): The thread to save the messages to.
        sender_type (str | None): The sender type for the messages. If None, auto-determined.
    """

    from django_ai_assistant.models import Message as DjangoMessage, MessageSenderType

    existing_message_ids = [
        str(i)
        for i in DjangoMessage.objects.filter(thread=thread)
        .order_by("created_at")
        .values_list("id", flat=True)
    ]

    messages_to_create = [m for m in messages if m.id not in existing_message_ids]

    # Auto-determine sender type if not provided
    created_message_objects = []
    for msg in messages_to_create:
        # Determine sender type
        if sender_type:
            msg_sender_type = sender_type
        elif isinstance(msg, AIMessage):
            msg_sender_type = MessageSenderType.AI
        else:
            # Default to ANONYMOUS for human messages if not specified
            msg_sender_type = MessageSenderType.ANONYMOUS
        
        created_message_objects.append(
            DjangoMessage(thread=thread, message={}, sender_type=msg_sender_type)
        )

    created_messages = DjangoMessage.objects.bulk_create(created_message_objects)

    # Update langchain message IDs with Django message IDs
    for idx, created_message in enumerate(created_messages):
        message_with_id = messages_to_create[idx]
        message_with_id.id = str(created_message.id)
        created_message.message = message_to_dict(message_with_id)

    DjangoMessage.objects.bulk_update(created_messages, ["message"])
    return created_messages
