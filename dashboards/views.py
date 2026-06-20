from django.template.defaultfilters import slugify
from .forms import AddUserForm, BlogPostForm, CategoryForm, EditUserForm, UserProfileForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from blogs.content_analyzer import analyze_blog_content
from blogs.models import (Blog, BlogContentAnalysis, Bookmark, Category,
                          Notification, UserProfile)
from blogs.moderation import check_blog_content
from blogs.notifications import notify_post_submitted
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render

import logging


from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


@login_required(login_url='login')
def dashboard(request):
    blogs_count = Blog.objects.filter(author=request.user).count()
    bookmark_count = Bookmark.objects.filter(user=request.user).count()
    analyses = BlogContentAnalysis.objects.filter(
        blog__author=request.user,
    ).select_related('blog').order_by('-analyzed_at')
    poor_quality_count = sum(
        1 for analysis in analyses if analysis.has_quality_warning)

    context = {
        'blogs_count': blogs_count,
        'bookmark_count': bookmark_count,
        'poor_quality_count': poor_quality_count,
        'recent_analyses': analyses[:5],
    }
    return render(request, 'dashboard/dashboard.html', context)


@login_required(login_url='login')
@permission_required('blogs.view_category', raise_exception=True)
def categories(request):
    categories = Category.objects.all().order_by('category_name')
    return render(request, 'dashboard/categories.html', {'categories': categories})


@login_required(login_url='login')
@permission_required('blogs.add_category', raise_exception=True)
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('categories')
    form = CategoryForm()
    context = {
        'form': form,
    }
    return render(request, 'dashboard/add_category.html', context)


@login_required(login_url='login')
@permission_required('blogs.change_category', raise_exception=True)
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect('categories')
    form = CategoryForm(instance=category)
    context = {
        'form': form,
        'category': category,
    }
    return render(request, 'dashboard/edit_category.html', context)


@login_required(login_url='login')
@permission_required('blogs.delete_category', raise_exception=True)
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    category.delete()
    return redirect('categories')


@login_required(login_url='login')
def posts(request):
    posts = Blog.objects.filter(author=request.user).select_related(
        'category',
        'author',
        'content_analysis',
    ).order_by('-created_at')
    context = {
        'posts': posts,
    }
    return render(request, 'dashboard/posts.html', context)


@login_required(login_url='login')
def add_post(request):
    if request.method == 'POST':
        draft_id = request.POST.get('draft_post_id')
        existing_draft = None
        if draft_id:
            # Only allow taking over a draft that isn't already published,
            # and that actually belongs to this user.
            existing_draft = Blog.objects.filter(
                id=draft_id, author=request.user
            ).exclude(status='Published').first()

        form = BlogPostForm(request.POST, request.FILES,
                            instance=existing_draft)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            title = form.cleaned_data['title']
            post.slug = slugify(title) + '-' + str(post.id)

            logger.info(
                "Running AI moderation check for post id=%s title=%r", post.id, post.title)
            result = check_blog_content(
                post.title, post.short_description, post.blog_body)
            logger.info("AI moderation result for post id=%s: %s",
                        post.id, result)

            post.ai_verdict = result['verdict']
            post.ai_reason = result.get('reason', '')
            post.ai_checked_at = timezone.now()
            post.status = 'Published' if result['verdict'] == 'approved' else 'Pending Review'

            post.save()
            analyze_blog_content(post)
            # Autosave drafts are silent; only the explicit form submission
            # creates author confirmation and staff review notifications.
            notify_post_submitted(post)
            return redirect('posts')
        else:
            print('form is invalid')
            print(form.errors)
    form = BlogPostForm()
    context = {
        'form': form,
    }
    return render(request, 'dashboard/add_post.html', context)


@login_required(login_url='login')
def edit_post(request, pk):
    post = get_object_or_404(Blog, pk=pk, author=request.user)
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            post = form.save(commit=False)
            title = form.cleaned_data['title']
            post.slug = slugify(title) + '-' + str(post.id)

            # *** THE FIX ***
            # Previously this view just called form.save() and stopped —
            # `status` isn't a form field, so a Draft being submitted here
            # stayed 'Draft' forever and never ran the AI check.
            # We only re-check if it isn't already Published, so editing a
            # live post for a typo fix doesn't get silently re-moderated.
            if post.status != 'Published':
                logger.info(
                    "Running AI moderation check for post id=%s title=%r", post.id, post.title)
                result = check_blog_content(
                    post.title, post.short_description, post.blog_body)
                logger.info("AI moderation result for post id=%s: %s",
                            post.id, result)

                post.ai_verdict = result['verdict']
                post.ai_reason = result.get('reason', '')
                post.ai_checked_at = timezone.now()
                post.status = 'Published' if result['verdict'] == 'approved' else 'Pending Review'

            post.save()
            # Editorial analysis runs on every explicit edit, including live
            # posts, but never changes publication status.
            analyze_blog_content(post)
            return redirect('posts')
    form = BlogPostForm(instance=post)
    context = {
        'form': form,
        'post': post,
        'analysis': getattr(post, 'content_analysis', None),
    }
    return render(request, 'dashboard/edit_post.html', context)


@login_required(login_url='login')
def delete_post(request, pk):
    post = get_object_or_404(Blog, pk=pk, author=request.user)
    post.delete()
    return redirect('posts')


@login_required(login_url='login')
def bookmarks(request):
    bookmarks = Bookmark.objects.filter(user=request.user).select_related(
        'user',
        'post',
        'post__author',
        'post__category',
    ).order_by('-created_at')
    context = {
        'bookmarks': bookmarks,
    }
    return render(request, 'dashboard/bookmarks.html', context)


@login_required(login_url='login')
def notifications(request):
    user_notifications = Notification.objects.filter(
        recipient=request.user,
    ).select_related('blog', 'actor')
    return render(request, 'dashboard/notifications.html', {
        'notifications': user_notifications,
    })


@login_required(login_url='login')
def open_notification(request, pk):
    """Mark one notification read, then send the user to its related post."""
    notification = get_object_or_404(
        Notification.objects.select_related('blog', 'actor'),
        pk=pk,
        recipient=request.user,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])

    # If the notification is related to a blog post, send the user there.
    if notification.blog:
        post = notification.blog
        if request.user == post.author:
            return redirect('edit_post', pk=post.pk)
        if request.user.has_perm('blogs.change_blog'):
            return redirect('admin:blogs_blog_change', object_id=post.pk)
        return redirect('posts')

    # Fallbacks for non-blog notifications (e.g. follow requests)
    if notification.notification_type in ('follow_request', 'follow_accepted') and notification.actor:
        return redirect('author_profile', username=notification.actor.username)

    return redirect('notifications')


@login_required(login_url='login')
@require_POST
def mark_notification_read(request, pk):
    notification = get_object_or_404(
        Notification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])
    return redirect('notifications')


@login_required(login_url='login')
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True, read_at=timezone.now())
    return redirect('notifications')


def users(request):
    users = User.objects.all()
    context = {
        'users': users,
    }
    return render(request, 'dashboard/users.html', context)


def add_user(request):
    if request.method == 'POST':
        form = AddUserForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('users')
        else:
            print(form.errors)
    form = AddUserForm()
    context = {
        'form': form,
    }
    return render(request, 'dashboard/add_user.html', context)


def edit_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    profile, created = UserProfile.objects.get_or_create(user=user)
    if request.method == 'POST':
        form = EditUserForm(request.POST, instance=user)
        profile_form = UserProfileForm(
            request.POST, request.FILES, instance=profile)
        if form.is_valid() and profile_form.is_valid():
            form.save()
            profile_form.save()
            return redirect('users')
    form = EditUserForm(instance=user)
    profile_form = UserProfileForm(instance=profile)
    context = {
        'form': form,
        'profile_form': profile_form,
    }
    return render(request, 'dashboard/edit_user.html', context)


def delete_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    user.delete()
    return redirect('users')


# ---------------------------------------------------------------------------
# Autosave Draft API
# ---------------------------------------------------------------------------

@login_required(login_url='login')
@require_POST
def api_save_draft(request):
    post_id = request.POST.get('post_id')
    title = request.POST.get('title', '').strip()
    blog_body = request.POST.get('blog_body', '').strip()
    short_description = request.POST.get('short_description', '').strip()
    category_id = request.POST.get('category')

    if not title and not blog_body:
        return JsonResponse({'error': 'Nothing to save yet.'}, status=400)

    if post_id:
        post = Blog.objects.filter(
            id=post_id, author=request.user
        ).exclude(status='Published').first()
        if post is None:
            return JsonResponse({'error': 'Draft not found or already published.'}, status=404)
        is_new = False
    else:
        post = Blog(author=request.user, status='Draft')
        is_new = True

    post.title = title or 'Untitled draft'
    post.blog_body = blog_body
    post.short_description = short_description
    if category_id:
        post.category = Category.objects.filter(id=category_id).first()
    post.status = 'Draft'
    post.save()

    if is_new:
        post.slug = f'draft-{post.id}'
        post.save(update_fields=['slug'])

    return JsonResponse({
        'id': post.id,
        'status': post.status,
        'updated_at': post.updated_at.isoformat(),
    })
