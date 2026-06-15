from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Blog, Category, Comment, Reaction, Bookmark, Follow, UserProfile
from django.db.models import Q

def posts_by_category(request, category_id):
    # Fetch the posts that belongs to the category with the id category_id
    posts = Blog.objects.filter(status='Published', category=category_id)
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
    posts = Blog.objects.filter(author=author, status='Published').order_by('-created_at')
    followers_count = author.followers.count()
    following_count = author.following.count()
    is_following = False

    if request.user.is_authenticated:
        is_following = Follow.objects.filter(follower=request.user, following=author).exists()

    context = {
        'author': author,
        'profile': profile,
        'posts': posts,
        'followers_count': followers_count,
        'following_count': following_count,
        'is_following': is_following,
    }
    return render(request, 'author_profile.html', context)

def search(request):
    keyword = request.GET.get('keyword')
    
    blogs = Blog.objects.filter(Q(title__icontains=keyword) | Q(short_description__icontains=keyword) | Q(blog_body__icontains=keyword), status='Published')
  
    context = {
        'blogs': blogs,
        'keyword': keyword,
    }
    return render(request, 'search.html', context)

@login_required(login_url='login')
def react_post(request, post_id):
    post = Blog.objects.get(id=post_id)
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
    payload = {
        'is_following': Follow.objects.filter(follower=request.user, following=target).exists(),
        'followers_count': target.followers.count(),
        'following_count': target.following.count(),
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse(payload)

    return redirect('author_profile', username=target.username)


@login_required(login_url='login')
@require_POST
def follow_user(request, user_id):
    target = get_object_or_404(User, id=user_id)

    if target == request.user:
        return JsonResponse({'error': 'You cannot follow yourself.'}, status=400)

    Follow.objects.get_or_create(
        follower=request.user,
        following=target
    )

    return _follow_response(request, target)


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
def author_followers(request, username):
    author = get_object_or_404(User, username=username)
    followers = author.followers.select_related('follower').order_by('-created_at')
    following = author.following.select_related('following').order_by('-created_at')

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
