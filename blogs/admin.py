from django.contrib import admin
from django.contrib.auth.models import Group
from django.utils.html import format_html

from .models import (Bookmark, Category, Blog, BlogContentAnalysis, Comment,
                     Follow, FollowRequest, Notification, Reaction, Tag,
                     UserProfile)
from .notifications import notify_status_changed


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('category_name', 'created_at', 'updated_at')
    search_fields = ('category_name',)
    ordering = ('category_name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'slug')


class BlogAdmin(admin.ModelAdmin):
    list_display = ('image_preview', 'title', 'category', 'author',
                    'status', 'ai_verdict', 'is_featured',  'created_at')
    list_filter = ('status', 'ai_verdict', 'is_featured',
                   'category', 'author', 'created_at')
    search_fields = ('id', 'title', 'short_description',
                     'blog_body', 'category__category_name', 'author__username')

    # Admin can still flip status quickly from the list page (click dropdown,
    # then click "Save" at the bottom of the list).
    list_editable = ('status',)

    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ['approve_posts', 'reject_posts', 'send_back_to_pending']

    # Everything about the post's actual content is read-only for admins.
    # Admins can only change: status, is_featured.
    readonly_fields = (
        'title_display', 'slug', 'category_display', 'author_display',
        'image_preview', 'short_description_display', 'blog_body_display',
        'tags_display',
        'reading_time', 'created_at', 'updated_at',
        'ai_verdict', 'ai_reason', 'ai_checked_at', 'reviewed_by',
    )

    fieldsets = (
        ('Post details (read-only — written by the author)', {
            'fields': ('title_display', 'slug', 'category_display', 'author_display',
                       'image_preview')
        }),
        ('Content (read-only — written by the author)', {
            'fields': ('short_description_display', 'blog_body_display', 'tags_display')
        }),
        ('Review decision (admin-editable)', {
            'fields': ('status', 'is_featured')
        }),
        ('AI Moderation (read-only)', {
            'fields': ('ai_verdict', 'ai_reason', 'ai_checked_at', 'reviewed_by')
        }),
        ('Timestamps', {
            'classes': ('collapse',),
            'fields': ('reading_time', 'created_at', 'updated_at')
        }),
    )

    @admin.display(description='Title')
    def title_display(self, obj):
        return obj.title

    @admin.display(description='Category')
    def category_display(self, obj):
        return obj.category

    @admin.display(description='Author')
    def author_display(self, obj):
        return obj.author

    @admin.display(description='Short description')
    def short_description_display(self, obj):
        return obj.short_description

    @admin.display(description='Blog body')
    def blog_body_display(self, obj):
        return format_html('<div style="white-space: pre-wrap; max-width: 700px;">{}</div>', obj.blog_body)

    @admin.display(description='Tags')
    def tags_display(self, obj):
        return ", ".join(tag.name for tag in obj.tags.all()) or "-"

    @admin.display(description='Image')
    def image_preview(self, obj):
        if obj.featured_image:
            return format_html(
                '<img src="{}" style="width:140px;height:100px;object-fit:cover;border-radius:8px;" />',
                obj.featured_image.url,
            )
        return '-'

    @admin.action(description='✅ Approve selected posts (publish)')
    def approve_posts(self, request, queryset):
        updated = self._change_status(queryset, 'Published', request.user)
        self.message_user(
            request, f'{updated} post(s) approved and published.')

    @admin.action(description='❌ Reject selected posts')
    def reject_posts(self, request, queryset):
        updated = self._change_status(queryset, 'Rejected', request.user)
        self.message_user(request, f'{updated} post(s) rejected.')

    @admin.action(description='↩ Send back to Pending Review')
    def send_back_to_pending(self, request, queryset):
        updated = self._change_status(
            queryset, 'Pending Review', request.user)
        self.message_user(
            request, f'{updated} post(s) sent back to pending review.')

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and 'status' in form.changed_data:
            old_status = Blog.objects.only('status').get(pk=obj.pk).status
            obj.reviewed_by = request.user
        super().save_model(request, obj, form, change)
        if old_status is not None:
            notify_status_changed(obj, old_status)

    @staticmethod
    def _change_status(queryset, new_status, reviewer):
        """Run bulk moderation while preserving per-post notifications."""
        updated = 0
        for post in queryset.select_related('author'):
            old_status = post.status
            if old_status == new_status:
                continue
            post.status = new_status
            post.reviewed_by = reviewer
            post.save(update_fields=['status', 'reviewed_by', 'updated_at'])
            notify_status_changed(post, old_status)
            updated += 1
        return updated

    def has_delete_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request):
        return False


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('short_comment', 'user', 'blog', 'created_at')
    list_filter = ('created_at', 'blog')
    search_fields = ('comment', 'user__username', 'blog__title')
    autocomplete_fields = ('user', 'blog')
    date_hierarchy = 'created_at'

    @admin.display(description='Comment')
    def short_comment(self, obj):
        return obj.comment[:80]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_private', 'updated_at')
    list_filter = ('is_private',)
    search_fields = ('user__username', 'user__email', 'bio')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('follower', 'following', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('follower__username', 'following__username')
    autocomplete_fields = ('follower', 'following')


@admin.register(FollowRequest)
class FollowRequestAdmin(admin.ModelAdmin):
    list_display = ('requester', 'target', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('requester__username', 'target__username')
    autocomplete_fields = ('requester', 'target')


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'post__title')
    autocomplete_fields = ('user', 'post')


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'post__title')
    autocomplete_fields = ('user', 'post')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'blog', 'status',
                    'is_read', 'created_at')
    list_filter = ('notification_type', 'status', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'blog__title', 'message')
    autocomplete_fields = ('recipient', 'blog')
    readonly_fields = ('created_at', 'read_at')


@admin.register(BlogContentAnalysis)
class BlogContentAnalysisAdmin(admin.ModelAdmin):
    list_display = ('blog', 'status', 'grammar_score', 'vocabulary_score',
                    'ai_generated_percentage', 'analyzed_at')
    list_filter = ('status', 'analyzed_at')
    search_fields = ('blog__title', 'blog__author__username', 'summary')
    readonly_fields = (
        'blog', 'status', 'grammar_score', 'vocabulary_score',
        'grammar_errors', 'spelling_errors', 'suggestions', 'summary',
        'ai_generated_percentage', 'content_hash', 'quality_model',
        'detector_model', 'error_message', 'analyzed_at', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(Blog, BlogAdmin)
admin.site.unregister(Group)
