from django.urls import path
from . import views


urlpatterns = [
    path('<int:category_id>/', views.posts_by_category, name='posts_by_category'),
    path('react/<int:post_id>/', views.react_post, name='react_post'),
    path('bookmark/<int:post_id>/', views.bookmark_post, name='bookmark_post'),
    path('authors/<str:username>/', views.author_profile, name='author_profile'),
    path('authors/<str:username>/followers/',
         views.author_followers, name='author_followers'),
    path('bloggers/', views.blogger_directory, name='blogger_directory'),
    path('profile/privacy/', views.update_profile_privacy,
         name='update_profile_privacy'),
    path('follow-requests/<int:request_id>/respond/',
         views.respond_follow_request, name='respond_follow_request'),
    path('follow/<int:user_id>/', views.follow_user, name='follow_user'),
    path('unfollow/<int:user_id>/', views.unfollow_user, name='unfollow_user'),
    path('api/follow/<int:user_id>/', views.api_follow, name='api_follow'),
    path('api/follow/accept/<int:request_id>/',
         views.api_accept_follow, name='api_accept_follow'),
    path('api/follow/decline/<int:request_id>/',
         views.api_decline_follow, name='api_decline_follow'),
    path('api/unfollow/<int:user_id>/', views.api_unfollow, name='api_unfollow'),
    path('api/users/<int:user_id>/followers/',
         views.api_user_followers, name='api_user_followers'),
    path('api/users/<int:user_id>/following/',
         views.api_user_following, name='api_user_following'),
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),
]
