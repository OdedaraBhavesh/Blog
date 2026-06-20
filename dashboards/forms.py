from django import forms
from blogs.models import Blog, Category, UserProfile
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'


class BlogPostForm(forms.ModelForm):
    class Meta:
        model = Blog
        fields = ('title', 'category', 'featured_image',
                  'short_description', 'blog_body')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Model fields are blank=True so the autosave endpoint can store
        # partial drafts. Re-enforce them here so a real Publish submission
        # still requires complete content.
        self.fields['category'].required = True
        self.fields['featured_image'].required = True
        self.fields['short_description'].required = True
        self.fields['blog_body'].required = True


class AddUserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active',
                  'is_staff', 'is_superuser', 'user_permissions')


class EditUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active',
                  'is_staff', 'is_superuser', 'groups', 'user_permissions')


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('bio', 'profile_picture', 'is_private')
