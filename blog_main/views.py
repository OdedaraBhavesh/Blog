
from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth import views as auth_views

from blogs.views import visible_posts_for_user
from assignments.models import About
from .forms import RegistrationForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import auth


class PasswordResetWithMessageView(auth_views.PasswordResetView):
    def form_valid(self, form):
        messages.success(
            self.request,
            'If an account exists for that email, we have sent password reset instructions.'
        )
        return super().form_valid(form)


def home(request):
    visible_posts = visible_posts_for_user(request.user)
    featured_posts = visible_posts.filter(
        is_featured=True).order_by('updated_at')
    posts = visible_posts.filter(is_featured=False)

    # Fetch about us
    try:
        about = About.objects.get()
    except:
        about = None
    context = {
        'featured_posts': featured_posts,
        'posts': posts,
        'about': about,
    }
    return render(request, 'home.html', context)


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth.login(request, user)
            messages.success(request, 'Welcome!')
            return redirect('home')
        messages.error(
            request, 'Please correct the highlighted errors and try again.')
    else:
        form = RegistrationForm()
    context = {
        'form': form,
    }
    return render(request, 'register.html', context)


def login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, request.POST)
        if form.is_valid():
            user = form.get_user()
            auth.login(request, user)
            messages.success(request, 'Welcome back!')
            if user.is_staff or user.is_superuser:
                return redirect('dashboard')
            return redirect('home')
        messages.error(request, 'Wrong credentials please provide correct.')
    else:
        form = AuthenticationForm()
    context = {
        'form': form,
    }
    return render(request, 'login.html', context)


def logout(request):
    auth.logout(request)
    return redirect('home')
