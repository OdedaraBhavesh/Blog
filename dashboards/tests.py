from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from blogs.models import Blog, Bookmark, Category


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

    def test_logged_in_header_has_home_and_current_user_profile_links(self):
        User.objects.create_user(username='writer', password='StrongPass123')
        self.client.login(username='writer', password='StrongPass123')

        response = self.client.get(reverse('home'))

        self.assertContains(response, f'href="{reverse("home")}"')
        self.assertContains(response, f'href="{reverse("author_profile", args=["writer"])}"')
        self.assertContains(response, 'Profile')

    def test_anonymous_header_has_home_but_not_profile_link(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, f'href="{reverse("home")}"')
        self.assertNotContains(response, 'Profile')

    @patch('dashboards.views.check_blog_content')
    def test_logged_in_user_can_post_blog(self, mock_check_blog_content):
        mock_check_blog_content.return_value = {
            'verdict': 'approved',
            'reason': 'No unsafe content detected.',
        }
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

    def test_dashboard_counts_only_current_users_posts_and_bookmarks(self):
        writer = User.objects.create_user(username='writer', password='StrongPass123')
        other = User.objects.create_user(username='other', password='StrongPass123')
        category = Category.objects.create(category_name='Tech')
        writer_post = Blog.objects.create(
            title='Writer Post',
            slug='writer-post',
            category=category,
            author=writer,
            featured_image='uploads/test.gif',
            short_description='Short description',
            blog_body='Body text',
        )
        Blog.objects.create(
            title='Other Post',
            slug='other-post',
            category=category,
            author=other,
            featured_image='uploads/test.gif',
            short_description='Short description',
            blog_body='Body text',
        )
        Bookmark.objects.create(user=writer, post=writer_post)

        self.client.login(username='writer', password='StrongPass123')
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.context['blogs_count'], 1)
        self.assertEqual(response.context['bookmark_count'], 1)
        self.assertNotIn('category_count', response.context)

    def test_posts_dashboard_only_lists_current_users_posts(self):
        writer = User.objects.create_user(username='writer', password='StrongPass123')
        other = User.objects.create_user(username='other', password='StrongPass123')
        category = Category.objects.create(category_name='Tech')
        Blog.objects.create(
            title='Writer Post',
            slug='writer-post',
            category=category,
            author=writer,
            featured_image='uploads/test.gif',
            short_description='Short description',
            blog_body='Body text',
        )
        Blog.objects.create(
            title='Other Post',
            slug='other-post',
            category=category,
            author=other,
            featured_image='uploads/test.gif',
            short_description='Short description',
            blog_body='Body text',
        )

        self.client.login(username='writer', password='StrongPass123')
        response = self.client.get(reverse('posts'))

        self.assertContains(response, 'Writer Post')
        self.assertNotContains(response, 'Other Post')

    def test_user_cannot_edit_another_users_post_from_dashboard_url(self):
        writer = User.objects.create_user(username='writer', password='StrongPass123')
        other = User.objects.create_user(username='other', password='StrongPass123')
        category = Category.objects.create(category_name='Tech')
        other_post = Blog.objects.create(
            title='Other Post',
            slug='other-post',
            category=category,
            author=other,
            featured_image='uploads/test.gif',
            short_description='Short description',
            blog_body='Body text',
        )

        self.client.login(username='writer', password='StrongPass123')
        response = self.client.get(reverse('edit_post', args=[other_post.id]))

        self.assertEqual(response.status_code, 404)

    def test_bookmarks_dashboard_only_lists_current_users_bookmarks(self):
        writer = User.objects.create_user(username='writer', password='StrongPass123')
        other = User.objects.create_user(username='other', password='StrongPass123')
        category = Category.objects.create(category_name='Tech')
        writer_post = Blog.objects.create(
            title='Writer Saved Post',
            slug='writer-saved-post',
            category=category,
            author=writer,
            featured_image='uploads/test.gif',
            short_description='Short description',
            blog_body='Body text',
            status='Published',
        )
        other_post = Blog.objects.create(
            title='Other Saved Post',
            slug='other-saved-post',
            category=category,
            author=other,
            featured_image='uploads/test.gif',
            short_description='Short description',
            blog_body='Body text',
            status='Published',
        )
        Bookmark.objects.create(user=writer, post=writer_post)
        Bookmark.objects.create(user=other, post=other_post)

        self.client.login(username='writer', password='StrongPass123')
        response = self.client.get(reverse('dashboard_bookmarks'))

        self.assertContains(response, 'Writer Saved Post')
        self.assertNotContains(response, 'Other Saved Post')
