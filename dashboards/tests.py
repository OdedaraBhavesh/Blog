from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from blogs.models import Blog, Category


class AccountAndPostWorkflowTests(TestCase):
    def test_user_can_register(self):
        response = self.client.post(reverse('register'), {
            'email': 'newuser@example.com',
            'username': 'newuser',
            'password1': 'StrongPass123',
            'password2': 'StrongPass123',
        })

        self.assertRedirects(response, reverse('home'))
        user = User.objects.get(username='newuser')
        self.assertEqual(int(self.client.session['_auth_user_id']), user.id)

    def test_regular_user_can_login_and_redirects_home(self):
        User.objects.create_user(username='writer', password='StrongPass123')

        response = self.client.post(reverse('login'), {
            'username': 'writer',
            'password': 'StrongPass123',
        })

        self.assertRedirects(response, reverse('home'))
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='writer').id)

    def test_staff_user_can_login_and_redirects_dashboard(self):
        User.objects.create_user(username='staff', password='StrongPass123', is_staff=True)

        response = self.client.post(reverse('login'), {
            'username': 'staff',
            'password': 'StrongPass123',
        })

        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='staff').id)

    def test_logged_in_user_can_post_blog(self):
        user = User.objects.create_user(username='writer', password='StrongPass123')
        category = Category.objects.create(category_name='Tech')
        self.client.login(username='writer', password='StrongPass123')

        image = SimpleUploadedFile(
            'test.gif',
            b'GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;',
            content_type='image/gif',
        )
        response = self.client.post(reverse('add_post'), {
            'title': 'My Test Blog',
            'category': category.id,
            'featured_image': image,
            'short_description': 'Short test description',
            'blog_body': 'This is the body of the blog post.',
            'status': 'Published',
            'is_featured': 'on',
        })

        self.assertRedirects(response, reverse('posts'))
        post = Blog.objects.get(title='My Test Blog')
        self.assertEqual(post.author, user)
        self.assertEqual(post.slug, f'my-test-blog-{post.id}')
