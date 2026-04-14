from django.contrib import admin
from .models import Bookmark, Category, Blog, Comment, Follow, Reaction, Tag, UserProfile

class BlogAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}
    list_display = ('title', 'category', 'author', 'status', 'is_featured')
    search_fields = ('id', 'title', 'category__category_name', 'status')
    list_editable = ('is_featured',)

admin.site.register(Category)
admin.site.register(Blog, BlogAdmin)
admin.site.register(Comment)
admin.site.register(Tag)
admin.site.register(UserProfile)
admin.site.register(Follow)
admin.site.register(Reaction)
admin.site.register(Bookmark)
