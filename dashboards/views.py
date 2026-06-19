from django.template.defaultfilters import slugify
from .forms import AddUserForm, BlogPostForm, CategoryForm, EditUserForm, UserProfileForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from blogs.models import Blog, Bookmark, Category, UserProfile
from blogs.moderation import check_blog_content
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render

import logging


from django.contrib.auth.models import User

from blogs.moderation import check_blog_content

logger = logging.getLogger(__name__)


@login_required(login_url='login')
def dashboard(request):
    blogs_count = Blog.objects.filter(author=request.user).count()
    bookmark_count = Bookmark.objects.filter(user=request.user).count()

    context = {
        'blogs_count': blogs_count,
        'bookmark_count': bookmark_count,
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
    ).order_by('-created_at')
    context = {
        'posts': posts,
    }
    return render(request, 'dashboard/posts.html', context)


@login_required(login_url='login')
def add_post(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)  # temporarily saving the form
            post.author = request.user
            post.save()
            title = form.cleaned_data['title']
            post.slug = slugify(title) + '-' + str(post.id)

            # --- AI moderation check runs here, every single submission ---
            logger.info(
                "Running AI moderation check for post id=%s title=%r", post.id, post.title)
            result = check_blog_content(
                post.title, post.short_description, post.blog_body)
            logger.info("AI moderation result for post id=%s: %s",
                        post.id, result)

            post.ai_verdict = result['verdict']
            post.ai_reason = result.get('reason', '')
            post.ai_checked_at = timezone.now()

            if result['verdict'] == 'approved':
                post.status = 'Published'
            else:
                post.status = 'Pending Review'
            # --- end AI moderation block ---

            post.save()
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
            post = form.save()
            title = form.cleaned_data['title']
            post.slug = slugify(title) + '-'+str(post.id)
            post.save()
            return redirect('posts')
    form = BlogPostForm(instance=post)
    context = {
        'form': form,
        'post': post
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
