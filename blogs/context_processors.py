from .models import Category, Notification

def get_categories(request):
    categories = Category.objects.all()
    return dict(categories=categories)


def notifications(request):
    """Expose a small navbar list and unread count on every authenticated page."""
    if not request.user.is_authenticated:
        return {
            'navbar_notifications': Notification.objects.none(),
            'unread_notification_count': 0,
        }

    user_notifications = Notification.objects.filter(
        recipient=request.user,
    ).select_related('blog')
    return {
        'navbar_notifications': user_notifications[:5],
        'unread_notification_count': user_notifications.filter(
            is_read=False).count(),
    }
