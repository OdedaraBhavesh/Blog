from django.urls import path
from . import views


urlpatterns = [
    path('<int:category_id>/', views.posts_by_category, name='posts_by_category'),
    path('react/<int:post_id>/', views.react_post, name='react_post'),
    path('bookmark/<int:post_id>/', views.bookmark_post, name='bookmark_post'),
    path('follow/<int:user_id>/', views.follow_user, name='follow_user'),
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),
]