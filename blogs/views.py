from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.models import User

from .models import Blog, Category, Comment, Reaction, Bookmark, Tag, Follow
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
        comment = Comment()
        comment.user = request.user
        comment.blog = single_blog
        comment.comment = request.POST['comment']
        comment.save()
        return HttpResponseRedirect(request.path_info)

    # Comments
    comments = Comment.objects.filter(blog=single_blog)
    comment_count = comments.count()
    
    context = {
        'single_blog': single_blog,
        'comments': comments,
        'comment_count': comment_count,
    }
    return render(request, 'blogs.html', context)

def search(request):
    keyword = request.GET.get('keyword')
    
    blogs = Blog.objects.filter(Q(title__icontains=keyword) | Q(short_description__icontains=keyword) | Q(blog_body__icontains=keyword), status='Published')
  
    context = {
        'blogs': blogs,
        'keyword': keyword,
    }
    return render(request, 'search.html', context)

def react_post(request, post_id):
    post = Blog.objects.get(id=post_id)
    user = request.user

    obj, created = Reaction.objects.get_or_create(user=user, post=post)

    if not created:
        obj.delete()

    return redirect('blogs', slug=post.slug)

def bookmark_post(request, post_id):
    post = Blog.objects.get(id=post_id)
    user = request.user

    obj, created = Bookmark.objects.get_or_create(user=user, post=post)

    if not created:
        obj.delete()

    return redirect('blogs', slug=post.slug)

def follow_user(request, user_id):
    target = User.objects.get(id=user_id)

    obj, created = Follow.objects.get_or_create(
        follower=request.user,
        following=target
    )

    if not created:
        obj.delete()

    return redirect('dashboard')

def post_detail(request, slug):
    post = Blog.objects.get(slug=slug)
    return render(request, 'blogs.html', {'post': post})