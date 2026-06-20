from django.contrib import admin
from django.urls import include, path, reverse_lazy
from . import views
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.auth import views as auth_views
from blogs import views as BlogsView
from dashboards import views as DashboardViews

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('category/', include('blogs.urls')),
    path('blogs/<slug:slug>/', BlogsView.blogs, name='blogs'),
    path('authors/<str:username>/',
         BlogsView.author_profile, name='author_profile'),
    path('authors/<str:username>/followers/',
         BlogsView.author_followers, name='author_followers'),
    path('bloggers/', BlogsView.blogger_directory, name='blogger_directory'),
    path('profile/privacy/', BlogsView.update_profile_privacy,
         name='update_profile_privacy'),
    path('follow-requests/<int:request_id>/respond/',
         BlogsView.respond_follow_request, name='respond_follow_request'),
    path('follow/<int:user_id>/', BlogsView.follow_user, name='follow_user'),
    path('unfollow/<int:user_id>/', BlogsView.unfollow_user, name='unfollow_user'),
    path('api/follow/<int:user_id>/', BlogsView.api_follow, name='api_follow'),
    path('api/follow/accept/<int:request_id>/',
         BlogsView.api_accept_follow, name='api_accept_follow'),
    path('api/follow/decline/<int:request_id>/',
         BlogsView.api_decline_follow, name='api_decline_follow'),
    path('api/unfollow/<int:user_id>/',
         BlogsView.api_unfollow, name='api_unfollow'),
    path('api/users/<int:user_id>/followers/',
         BlogsView.api_user_followers, name='api_user_followers'),
    path('api/users/<int:user_id>/following/',
         BlogsView.api_user_following, name='api_user_following'),
    path('api/posts/draft/', DashboardViews.api_save_draft, name='api_save_draft'),
    path('bookmarks/', BlogsView.my_bookmarks, name='my_bookmarks'),
    path('search/', BlogsView.search, name='search'),
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('profile/edit/', BlogsView.edit_profile, name='edit_profile'),
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='registration/password_change_form.html',
        success_url=reverse_lazy('password_change_done')
    ), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='registration/password_change_done.html'
    ), name='password_change_done'),
    path('password_reset/', views.PasswordResetWithMessageView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done')
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete')
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),

    path('dashboard/', include('dashboards.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
