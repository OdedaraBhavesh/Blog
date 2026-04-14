from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Blog, Category, Follow


class AuthorProfileTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username='author', password='pass12345')
        self.reader = User.objects.create_user(username='reader', password='pass12345')
        self.category = Category.objects.create(category_name='Tech')
        self.post = Blog.objects.create(
            title='Published Post',
            slug='published-post',
            category=self.category,
            author=self.author,
            featured_image='uploads/test.jpg',
            short_description='Short description',
            blog_body='Post body',
            status='Published',
        )

    def test_author_profile_shows_author_posts(self):
        response = self.client.get(reverse('author_profile', kwargs={'username': self.author.username}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.author.username)
        self.assertContains(response, self.post.title)

    def test_follow_requires_login(self):
        response = self.client.post(reverse('follow_user', kwargs={'user_id': self.author.id}))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_user_can_follow_and_unfollow_author(self):
        self.client.login(username='reader', password='pass12345')

        follow_response = self.client.post(
            reverse('follow_user', kwargs={'user_id': self.author.id}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(follow_response.status_code, 200)
        self.assertTrue(Follow.objects.filter(follower=self.reader, following=self.author).exists())
        self.assertEqual(follow_response.json()['followers_count'], 1)

        unfollow_response = self.client.post(
            reverse('unfollow_user', kwargs={'user_id': self.author.id}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(unfollow_response.status_code, 200)
        self.assertFalse(Follow.objects.filter(follower=self.reader, following=self.author).exists())
        self.assertEqual(unfollow_response.json()['followers_count'], 0)

    def test_user_cannot_follow_self(self):
        self.client.login(username='author', password='pass12345')

        response = self.client.post(
            reverse('follow_user', kwargs={'user_id': self.author.id}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Follow.objects.filter(follower=self.author, following=self.author).exists())
