from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Category(models.Model):
    category_name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.category_name


STATUS_CHOICES = (
    ("Draft", "Draft"),
    ("Pending Review", "Pending Review"),
    ("Published", "Published"),
    ("Rejected", "Rejected"),
)

FOLLOW_STATUS_CHOICES = (
    ("pending", "Pending"),
    ("accepted", "Accepted"),
)


class Tag(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Blog(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    # category & featured_image are now optional at the DB level so a partial
    # autosave (title/body only) can be stored as a Draft. Required-ness for
    # an actual Publish submission is enforced in dashboards/forms.py instead.
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    featured_image = models.ImageField(
        upload_to='uploads/%Y/%m/%d', null=True, blank=True)
    short_description = models.TextField(
        max_length=500, blank=True, default='')
    blog_body = models.TextField(max_length=2000, blank=True, default='')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Draft")
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tags = models.ManyToManyField(Tag, blank=True)
    reading_time = models.IntegerField(default=0)

    # AI moderation tracking
    ai_verdict = models.CharField(max_length=20, blank=True)
    ai_reason = models.TextField(blank=True)
    ai_checked_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_posts'
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.reading_time = len(self.blog_body.split()) // 200
        super().save(*args, **kwargs)


ANALYSIS_STATUS_CHOICES = (
    ('success', 'Success'),
    ('partial', 'Partial'),
    ('failed', 'Failed'),
    ('unavailable', 'Unavailable'),
)


class BlogContentAnalysis(models.Model):
    """Latest editorial analysis for a blog post.

    Safety moderation remains on Blog itself. This model stores writing-quality
    feedback and an experimental AI-generated likelihood for the author.
    """

    blog = models.OneToOneField(
        Blog, related_name='content_analysis', on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=ANALYSIS_STATUS_CHOICES, default='unavailable')
    grammar_score = models.PositiveSmallIntegerField(null=True, blank=True)
    vocabulary_score = models.PositiveSmallIntegerField(null=True, blank=True)
    grammar_errors = models.JSONField(default=list, blank=True)
    spelling_errors = models.JSONField(default=list, blank=True)
    suggestions = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True)
    ai_generated_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    quality_model = models.CharField(max_length=150, blank=True)
    detector_model = models.CharField(max_length=150, blank=True)
    error_message = models.TextField(blank=True)
    analyzed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'blog content analyses'

    @property
    def overall_score(self):
        scores = [
            score for score in (self.grammar_score, self.vocabulary_score)
            if score is not None
        ]
        return round(sum(scores) / len(scores)) if scores else None

    @property
    def has_quality_warning(self):
        available_scores = (
            self.grammar_score is not None and self.grammar_score < 60,
            self.vocabulary_score is not None and self.vocabulary_score < 60,
        )
        return any(available_scores) or bool(
            self.grammar_errors or self.spelling_errors)

    def __str__(self):
        return f'Analysis for {self.blog.title} ({self.status})'


NOTIFICATION_TYPES = (
    ("post_submitted", "Post submitted"),
    ("status_changed", "Post status changed"),
    ("follow_request", "Follow request"),
    ("follow_accepted", "Follow accepted"),
)


class Notification(models.Model):
    """A database-backed notification for one user and one blog post."""

    recipient = models.ForeignKey(
        User, related_name='notifications', on_delete=models.CASCADE)
    blog = models.ForeignKey(
        Blog, related_name='notifications', on_delete=models.CASCADE, null=True, blank=True)
    actor = models.ForeignKey(
        User, related_name='actor_notifications', on_delete=models.SET_NULL, null=True, blank=True)
    notification_type = models.CharField(
        max_length=30, choices=NOTIFICATION_TYPES)
    message = models.CharField(max_length=255)
    # Keep the status at the time of the event so notification history remains
    # meaningful even if an admin changes the post again later.
    status = models.CharField(max_length=20, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.recipient}: {self.message}'


class UserProfile(models.Model):
    user = models.OneToOneField(
        User, related_name='profile', on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    profile_picture = models.ImageField(
        upload_to='profiles/%Y/%m/%d', blank=True, null=True)
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        UserProfile.objects.get_or_create(user=instance)


class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE)
    comment = models.TextField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.comment


class Reaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Blog, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')


class Bookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Blog, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')


class Follow(models.Model):
    follower = models.ForeignKey(
        User, related_name='following', on_delete=models.CASCADE)
    following = models.ForeignKey(
        User, related_name='followers', on_delete=models.CASCADE)
    status = models.CharField(
        max_length=10, choices=FOLLOW_STATUS_CHOICES, default="accepted")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(follower=models.F('following')),
                name='prevent_self_follow',
            ),
        ]

    def __str__(self):
        return f'{self.follower} follows {self.following} ({self.status})'


class FollowRequest(models.Model):
    requester = models.ForeignKey(
        User, related_name='sent_follow_requests', on_delete=models.CASCADE)
    target = models.ForeignKey(
        User, related_name='received_follow_requests', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('requester', 'target')
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(requester=models.F('target')),
                name='prevent_self_follow_request',
            ),
        ]

    def __str__(self):
        return f'{self.requester} requested to follow {self.target}'
