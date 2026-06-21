from django.contrib.auth.models import User

from .models import Notification


def notify_post_submitted(post):
    """Confirm submission to the author and alert active staff reviewers."""
    Notification.objects.create(
        recipient=post.author,
        blog=post,
        notification_type='post_submitted',
        status=post.status,
        message=f'Your post "{
            post.title}" was submitted with status {post.status}.',
    )

    reviewers = User.objects.filter(
        is_active=True,
        is_staff=True,
    ).exclude(pk=post.author_id)
    Notification.objects.bulk_create([
        Notification(
            recipient=reviewer,
            blog=post,
            notification_type='post_submitted',
            status=post.status,
            message=f'{post.author.username} submitted "{
                post.title}" for review.',
        )
        for reviewer in reviewers
    ])


def notify_status_changed(post, old_status):
    """Notify the author after a real admin moderation status transition."""
    if old_status == post.status:
        return None

    return Notification.objects.create(
        recipient=post.author,
        blog=post,
        notification_type='status_changed',
        status=post.status,
        message=(
            f'Your post "{post.title}" changed from {old_status} '
            f'to {post.status}.'
        ),
    )


def notify_follow_request(follow):
    """Notify a user that someone requested to follow them."""
    return Notification.objects.create(
        recipient=follow.following,
        actor=follow.follower,
        blog=None,
        notification_type='follow_request',
        status='',
        message=f'{follow.follower.username} requested to follow you.',
    )


def notify_follow_accepted(follow):
    """Notify the requester that their follow request was accepted."""
    return Notification.objects.create(
        recipient=follow.follower,
        actor=follow.following,
        blog=None,
        notification_type='follow_accepted',
        status='',
        message=f'{follow.following.username} accepted your follow request.',
    )
