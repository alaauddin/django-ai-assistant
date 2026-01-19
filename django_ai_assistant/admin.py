from typing import ClassVar, List, Type

from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.urls import reverse
from django.utils.safestring import mark_safe

from django_ai_assistant.models import Message, Thread


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("pk", "message_type", "content", "created_at")
    readonly_fields = fields
    ordering = ("created_at",)
    show_change_link = True

    def pk(self, obj):
        display_text = "<a href={}>{}</a>".format(
            reverse(
                f"admin:{Message._meta.app_label}_{Message._meta.model_name}_change", args=(obj.pk,)
            ),
            obj.pk,
        )
        return mark_safe(display_text)  # noqa: S308

    def message_type(self, obj):
        return obj.message.get("type") if obj.message else None

    def content(self, obj):
        return obj.message.get("data", {}).get("content") if obj.message else None

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ("name", "assistant_id", "channel", "customer_user", "created_by", "created_at", "updated_at")
    search_fields = ("name", "assistant_id")
    list_filter = ("channel", "created_at", "updated_at")
    raw_id_fields = ("created_by", "customer_user")
    inlines: ClassVar[List[Type[InlineModelAdmin]]] = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "created_at")
    search_fields = ("thread__name", "message")
    list_filter = ("created_at",)
    raw_id_fields = ("thread",)


from django_ai_assistant.models import (
    Agent,
    Category,
    FAQ,
    Article,
    Tag,
    Language,
    FAQTag,
    ArticleType,
    CustomerUser,
)

@admin.register(CustomerUser)
class CustomerUserAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "external_id", "django_user", "created_at")
    search_fields = ("full_name", "email", "phone", "external_id", "django_user__username")
    list_filter = ("created_at", "updated_at")
    raw_id_fields = ("django_user",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)

@admin.register(FAQTag)
class FAQTagAdmin(admin.ModelAdmin):
    list_display = ("faq", "tag", "created_at", "updated_at")
    list_filter = ("tag", "created_at")

@admin.register(ArticleType)
class ArticleTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name", "model", "temperature", "created_at", "updated_at")
    search_fields = ("name", "display_name", "description")
    list_filter = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "display_name", "description")}),
        ("Configuration", {"fields": ("instructions", "model", "temperature")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "agent", "is_active", "created_at", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("agent", "is_active")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    # Removed category, status. Added language, is_published, is_active
    list_display = ("question", "agent", "language", "is_published", "is_active", "updated_at")
    search_fields = ("question", "answer")
    list_filter = ("is_published", "is_active", "agent", "language", "created_at")


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    # Removed status. Added category, article_type, language, is_published, is_active
    list_display = ("title", "agent", "category", "article_type", "language", "is_published", "is_active", "updated_at")
    search_fields = ("title", "content")
    list_filter = ("is_published", "is_active", "agent", "category", "article_type", "language", "created_at")


