from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Blog, Category, Comment, Reaction, Bookmark, Follow, UserProfile
from django.db.models import Q


def can_view_author_posts(viewer, author):
    profile, created = UserProfile.objects.get_or_create(user=author)
    if not profile.is_private:
        return True
    if viewer.is_authenticated and viewer == author:
        return True
    if viewer.is_authenticated:
        return Follow.objects.filter(
            follower=viewer,
            following=author,
            status='accepted',
        ).exists()
    return False


def visible_posts_for_user(user):
    posts = Blog.objects.filter(status='Published')
    if user.is_authenticated:
        blocked_private_authors = User.objects.filter(
            profile__is_private=True
        ).exclude(
            id=user.id
        ).exclude(
            followers__follower=user,
            followers__status='accepted',
        )
    else:
        blocked_private_authors = User.objects.filter(profile__is_private=True)
    return posts.exclude(author__in=blocked_private_authors)


def _follow_payload(request, target, follow_status=None):
    follow = Follow.objects.filter(
        follower=request.user,
        following=target,
    ).first()
    is_following = bool(follow and follow.status == 'accepted')
    has_pending_request = bool(follow and follow.status == 'pending')
    if follow_status is None:
        if is_following:
            follow_status = 'following'
        elif has_pending_request:
            follow_status = 'requested'
        else:
            follow_status = 'none'

    return {
        'is_following': is_following,
        'has_pending_request': has_pending_request,
        'follow_status': follow_status,
        'followers_count': target.followers.filter(status='accepted').count(),
        'following_count': target.following.filter(status='accepted').count(),
    }

def posts_by_category(request, category_id):
    # Fetch the posts that belongs to the category with the id category_id
    posts = visible_posts_for_user(request.user).filter(category=category_id)
    # Use try/except when we want to do some custom action if the category does not exists
    # try:
    #     category = Category.objects.get(pk=category_id)
    # except:
    #     # redirect the user to homepage
    #     return redirect('home')
    
    # Use get_object_or_404 when you want to show 404 error page if the category does not exist
    category = get_object_or_404(Category, pk=category_id)
    
    context = {
        'posts': posts,
        'category': category,
    }
    return render(request, 'posts_by_category.html', context)

def blogs(request, slug):
    single_blog = get_object_or_404(Blog, slug=slug, status='Published')
    if not can_view_author_posts(request.user, single_blog.author):
        return HttpResponseForbidden('This post belongs to a private account.')

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')
        comment = Comment()
        comment.user = request.user
        comment.blog = single_blog
        comment.comment = request.POST['comment']
        comment.save()
        return HttpResponseRedirect(request.path_info)

    # Comments
    comments = Comment.objects.filter(blog=single_blog)
    comment_count = comments.count()
    is_bookmarked = False

    if request.user.is_authenticated:
        is_bookmarked = Bookmark.objects.filter(user=request.user, post=single_blog).exists()
    
    context = {
        'single_blog': single_blog,
        'comments': comments,
        'comment_count': comment_count,
        'is_bookmarked': is_bookmarked,
    }
    return render(request, 'blogs.html', context)


def author_profile(request, username):
    author = get_object_or_404(User, username=username)
    profile, created = UserProfile.objects.get_or_create(user=author)
    can_view_posts = can_view_author_posts(request.user, author)
    posts = Blog.objects.none()
    if can_view_posts:
        posts = Blog.objects.filter(author=author, status='Published').order_by('-created_at')
    followers_count = author.followers.filter(status='accepted').count()
    following_count = author.following.filter(status='accepted').count()
    is_following = False
    has_pending_request = False
    pending_follow_requests = Follow.objects.none()

    if request.user.is_authenticated:
        follow = Follow.objects.filter(follower=request.user, following=author).first()
        is_following = bool(follow and follow.status == 'accepted')
        has_pending_request = bool(follow and follow.status == 'pending')
        if request.user == author:
            pending_follow_requests = Follow.objects.filter(
                following=author,
                status='pending',
            ).select_related('follower').order_by('-created_at')

    context = {
        'author': author,
        'profile': profile,
        'posts': posts,
        'followers_count': followers_count,
        'following_count': following_count,
        'is_following': is_following,
        'has_pending_request': has_pending_request,
        'can_view_posts': can_view_posts,
        'pending_follow_requests': pending_follow_requests,
    }
    return render(request, 'author_profile.html', context)


def blogger_directory(request):
    bloggers = User.objects.select_related('profile').order_by('username')
    follow_map = {}

    if request.user.is_authenticated:
        follow_map = {
            follow.following_id: follow.status
            for follow in Follow.objects.filter(follower=request.user)
        }

    blogger_cards = [
        {
            'user': blogger,
            'profile': blogger.profile,
            'follow_status': follow_map.get(blogger.id, 'none'),
        }
        for blogger in bloggers
    ]

    return render(request, 'blogger_directory.html', {
        'blogger_cards': blogger_cards,
    })


def _basic_user_payload(request, user):
    profile, created = UserProfile.objects.get_or_create(user=user)
    avatar_url = ''
    if profile.profile_picture:
        avatar_url = request.build_absolute_uri(profile.profile_picture.url)

    return {
        'id': user.id,
        'name': user.get_full_name() or user.username,
        'avatar_url': avatar_url,
        'profile_url': request.build_absolute_uri(
            reverse('author_profile', kwargs={'username': user.username})
        ),
    }


def _can_view_follow_lists(request, author):
    return can_view_author_posts(request.user, author)


def api_user_followers(request, user_id):
    author = get_object_or_404(User, id=user_id)
    if not _can_view_follow_lists(request, author):
        return JsonResponse({'error': 'This account is private.'}, status=403)

    followers = User.objects.filter(
        following__following=author,
        following__status='accepted',
    ).select_related('profile').order_by('username')

    return JsonResponse({
        'users': [_basic_user_payload(request, user) for user in followers],
    })


def api_user_following(request, user_id):
    author = get_object_or_404(User, id=user_id)
    if not _can_view_follow_lists(request, author):
        return JsonResponse({'error': 'This account is private.'}, status=403)

    following = User.objects.filter(
        followers__follower=author,
        followers__status='accepted',
    ).select_related('profile').order_by('username')

    return JsonResponse({
        'users': [_basic_user_payload(request, user) for user in following],
    })

def search(request):
    keyword = request.GET.get('keyword')
    
    blogs = visible_posts_for_user(request.user).filter(Q(title__icontains=keyword) | Q(short_description__icontains=keyword) | Q(blog_body__icontains=keyword))
  
    context = {
        'blogs': blogs,
        'keyword': keyword,
    }
    return render(request, 'search.html', context)

@login_required(login_url='login')
def react_post(request, post_id):
    post = get_object_or_404(Blog, id=post_id, status='Published')
    if not can_view_author_posts(request.user, post.author):
        return HttpResponseForbidden('This post belongs to a private account.')

    user = request.user

    obj, created = Reaction.objects.get_or_create(user=user, post=post)

    if not created:
        obj.delete()

    next_url = request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)

    return redirect('blogs', slug=post.slug)

@login_required(login_url='login')
def bookmark_post(request, post_id):
    post = get_object_or_404(Blog, id=post_id, status='Published')
    if not can_view_author_posts(request.user, post.author):
        return HttpResponseForbidden('This post belongs to a private account.')

    user = request.user

    obj, created = Bookmark.objects.get_or_create(user=user, post=post)

    if not created:
        obj.delete()

    return redirect('blogs', slug=post.slug)


@login_required(login_url='login')
def my_bookmarks(request):
    bookmarks = Bookmark.objects.filter(user=request.user).select_related(
        'post',
        'post__author',
        'post__category',
    ).order_by('-created_at')

    context = {
        'bookmarks': bookmarks,
    }
    return render(request, 'my_bookmarks.html', context)

def _follow_response(request, target):
    payload = _follow_payload(request, target)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse(payload)

    return redirect('author_profile', username=target.username)


@login_required(login_url='login')
@require_POST
def follow_user(request, user_id):
    target = get_object_or_404(User, id=user_id)

    if target == request.user:
        return JsonResponse({'error': 'You cannot follow yourself.'}, status=400)

    target_profile, created = UserProfile.objects.get_or_create(user=target)
    status = 'pending' if target_profile.is_private else 'accepted'

    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        following=target,
        defaults={'status': status},
    )
    if not created and follow.status != 'accepted':
        follow.status = status
        follow.save(update_fields=['status'])

    return _follow_response(request, target)


@login_required(login_url='login')
@require_POST
def api_follow(request, user_id):
    target = get_object_or_404(User, id=user_id)

    if target == request.user:
        return JsonResponse({'error': 'You cannot follow yourself.'}, status=400)

    target_profile, created = UserProfile.objects.get_or_create(user=target)
    status = 'pending' if target_profile.is_private else 'accepted'
    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        following=target,
        defaults={'status': status},
    )

    if not created and follow.status != 'accepted':
        follow.status = status
        follow.save(update_fields=['status'])

    payload = _follow_payload(request, target)
    payload['relationship_id'] = follow.id
    return JsonResponse(payload)


@login_required(login_url='login')
@require_POST
def unfollow_user(request, user_id):
    target = get_object_or_404(User, id=user_id)

    Follow.objects.filter(
        follower=request.user,
        following=target
    ).delete()

    return _follow_response(request, target)


@login_required(login_url='login')
@require_http_methods(["DELETE", "POST"])
def api_unfollow(request, user_id):
    target = get_object_or_404(User, id=user_id)
    Follow.objects.filter(follower=request.user, following=target).delete()
    return JsonResponse(_follow_payload(request, target))


@login_required(login_url='login')
@require_POST
def update_profile_privacy(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    profile.is_private = request.POST.get('is_private') == 'on'
    profile.save(update_fields=['is_private', 'updated_at'])
    return redirect('author_profile', username=request.user.username)


@login_required(login_url='login')
@require_POST
def respond_follow_request(request, request_id):
    follow_request = get_object_or_404(
        Follow, id=request_id, following=request.user, status='pending')
    action = request.POST.get('action')

    if action == 'accept':
        follow_request.status = 'accepted'
        follow_request.save(update_fields=['status'])
    elif action == 'decline':
        follow_request.delete()

    return redirect('author_profile', username=request.user.username)


@login_required(login_url='login')
@require_POST
def api_accept_follow(request, request_id):
    follow_request = get_object_or_404(
        Follow, id=request_id, following=request.user, status='pending')
    follow_request.status = 'accepted'
    follow_request.save(update_fields=['status'])
    return JsonResponse({'status': 'accepted', 'request_id': follow_request.id})


@login_required(login_url='login')
@require_POST
def api_decline_follow(request, request_id):
    follow_request = get_object_or_404(
        Follow, id=request_id, following=request.user, status='pending')
    follow_request.delete()
    return JsonResponse({'status': 'declined', 'request_id': request_id})


@login_required(login_url='login')
def author_followers(request, username):
    author = get_object_or_404(User, username=username)
    if not can_view_author_posts(request.user, author):
        return JsonResponse({'error': 'This account is private.'}, status=403)

    followers = author.followers.filter(
        status='accepted').select_related('follower').order_by('-created_at')
    following = author.following.filter(
        status='accepted').select_related('following').order_by('-created_at')

    return JsonResponse({
        'followers_count': followers.count(),
        'following_count': following.count(),
        'followers': [
            {
                'id': item.follower.id,
                'username': item.follower.username,
                'name': item.follower.get_full_name(),
            }
            for item in followers
        ],
        'following': [
            {
                'id': item.following.id,
                'username': item.following.username,
                'name': item.following.get_full_name(),
            }
            for item in following
        ],
    })

def post_detail(request, slug):
    post = Blog.objects.get(slug=slug)
    return render(request, 'blogs.html', {'post': post})
