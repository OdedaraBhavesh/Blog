from django.contrib import admin
from django.urls import include, path
from . import views
from django.conf.urls.static import static
from django.conf import settings
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

    path('dashboard/', include('dashboards.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
