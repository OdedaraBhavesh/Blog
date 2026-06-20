from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from blogs.models import Blog, Bookmark, Category, Notification


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
        self.assertTrue(Notification.objects.filter(
            recipient=user,
            blog=post,
            notification_type='post_submitted',
            status='Published',
        ).exists())

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


class NotificationWorkflowTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username='author', password='StrongPass123')
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@example.com',
            password='StrongPass123')
        self.other = User.objects.create_user(
            username='other', password='StrongPass123')
        self.category = Category.objects.create(category_name='News')
        self.post = Blog.objects.create(
            title='Review Me',
            slug='review-me',
            category=self.category,
            author=self.author,
            featured_image='uploads/test.gif',
            short_description='Description',
            blog_body='Post body',
            status='Pending Review',
        )

    def test_autosave_draft_does_not_create_notification(self):
        self.client.login(username='author', password='StrongPass123')

        response = self.client.post(reverse('api_save_draft'), {
            'title': 'Autosaved only',
            'blog_body': 'Partial body',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Notification.objects.exists())

    def test_submission_alerts_author_and_active_staff(self):
        from blogs.notifications import notify_post_submitted

        notify_post_submitted(self.post)

        recipients = set(Notification.objects.values_list(
            'recipient__username', flat=True))
        self.assertEqual(recipients, {'author', 'admin'})

    def test_admin_status_change_notifies_author(self):
        self.client.login(username='admin', password='StrongPass123')

        response = self.client.post(
            reverse('admin:blogs_blog_change', args=[self.post.pk]),
            {'status': 'Rejected', 'is_featured': '', '_save': 'Save'},
        )

        self.assertEqual(response.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'Rejected')
        self.assertEqual(self.post.reviewed_by, self.admin)
        notification = Notification.objects.get(
            recipient=self.author, notification_type='status_changed')
        self.assertEqual(notification.status, 'Rejected')
        self.assertIn('Pending Review to Rejected', notification.message)

    def test_admin_bulk_status_action_notifies_only_real_changes(self):
        published = Blog.objects.create(
            title='Already live', slug='already-live', category=self.category,
            author=self.author, status='Published')
        self.client.login(username='admin', password='StrongPass123')

        response = self.client.post(reverse('admin:blogs_blog_changelist'), {
            'action': 'approve_posts',
            '_selected_action': [self.post.pk, published.pk],
        })

        self.assertEqual(response.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'Published')
        self.assertEqual(Notification.objects.filter(
            notification_type='status_changed').count(), 1)

    def test_navbar_and_dashboard_show_unread_count(self):
        Notification.objects.create(
            recipient=self.author, blog=self.post,
            notification_type='status_changed', status='Published',
            message='Your post is published.')
        self.client.login(username='author', password='StrongPass123')

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'Unread Notifications')
        self.assertEqual(response.context['unread_notification_count'], 1)
        self.assertContains(response, 'Your post is published.')

    def test_open_notification_marks_read_and_links_to_own_post(self):
        notification = Notification.objects.create(
            recipient=self.author, blog=self.post,
            notification_type='status_changed', status='Rejected',
            message='Your post was rejected.')
        self.client.login(username='author', password='StrongPass123')

        response = self.client.get(
            reverse('open_notification', args=[notification.pk]))

        self.assertRedirects(response, reverse('edit_post', args=[self.post.pk]))
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_user_cannot_read_another_users_notification(self):
        notification = Notification.objects.create(
            recipient=self.author, blog=self.post,
            notification_type='status_changed', status='Rejected',
            message='Private notification.')
        self.client.login(username='other', password='StrongPass123')

        response = self.client.post(
            reverse('mark_notification_read', args=[notification.pk]))

        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_mark_all_read_only_updates_current_user(self):
        own = Notification.objects.create(
            recipient=self.author, blog=self.post,
            notification_type='status_changed', message='Own')
        other = Notification.objects.create(
            recipient=self.other, blog=self.post,
            notification_type='status_changed', message='Other')
        self.client.login(username='author', password='StrongPass123')

        response = self.client.post(reverse('mark_all_notifications_read'))

        self.assertRedirects(response, reverse('notifications'))
        own.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(own.is_read)
        self.assertFalse(other.is_read)
