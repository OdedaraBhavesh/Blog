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

    def test_private_author_follow_creates_request_not_follow(self):
        self.author.profile.is_private = True
        self.author.profile.save()
        self.client.login(username='reader', password='pass12345')

        response = self.client.post(
            reverse('follow_user', kwargs={'user_id': self.author.id}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Follow.objects.filter(
            follower=self.reader,
            following=self.author,
            status='pending',
        ).exists())
        self.assertTrue(response.json()['has_pending_request'])
        self.assertEqual(response.json()['follow_status'], 'requested')

    def test_private_author_can_accept_follow_request(self):
        self.author.profile.is_private = True
        self.author.profile.save()
        follow_request = Follow.objects.create(
            follower=self.reader,
            following=self.author,
            status='pending',
        )
        self.client.login(username='author', password='pass12345')

        response = self.client.post(
            reverse('respond_follow_request', kwargs={'request_id': follow_request.id}),
            {'action': 'accept'},
        )

        self.assertRedirects(response, reverse('author_profile', kwargs={'username': self.author.username}))
        self.assertTrue(Follow.objects.filter(
            follower=self.reader,
            following=self.author,
            status='accepted',
        ).exists())

    def test_private_author_can_decline_follow_request(self):
        self.author.profile.is_private = True
        self.author.profile.save()
        follow_request = Follow.objects.create(
            follower=self.reader,
            following=self.author,
            status='pending',
        )
        self.client.login(username='author', password='pass12345')

        response = self.client.post(
            reverse('respond_follow_request', kwargs={'request_id': follow_request.id}),
            {'action': 'decline'},
        )

        self.assertRedirects(response, reverse('author_profile', kwargs={'username': self.author.username}))
        self.assertFalse(Follow.objects.filter(follower=self.reader, following=self.author).exists())

    def test_private_author_posts_hidden_from_non_followers_everywhere(self):
        self.author.profile.is_private = True
        self.author.profile.save()
        self.client.login(username='reader', password='pass12345')

        profile_response = self.client.get(reverse('author_profile', kwargs={'username': self.author.username}))
        home_response = self.client.get(reverse('home'))
        category_response = self.client.get(reverse('posts_by_category', kwargs={'category_id': self.category.id}))
        search_response = self.client.get(reverse('search'), {'keyword': 'Published'})
        direct_response = self.client.get(reverse('blogs', kwargs={'slug': self.post.slug}))
        followers_response = self.client.get(reverse('author_followers', kwargs={'username': self.author.username}))

        self.assertContains(profile_response, 'This account is private.')
        self.assertNotContains(profile_response, self.post.title)
        self.assertNotContains(home_response, self.post.title)
        self.assertNotContains(category_response, self.post.title)
        self.assertNotContains(search_response, self.post.title)
        self.assertEqual(direct_response.status_code, 403)
        self.assertEqual(followers_response.status_code, 403)

        Follow.objects.create(follower=self.reader, following=self.author, status='accepted')

        profile_response = self.client.get(reverse('author_profile', kwargs={'username': self.author.username}))
        home_response = self.client.get(reverse('home'))
        category_response = self.client.get(reverse('posts_by_category', kwargs={'category_id': self.category.id}))
        search_response = self.client.get(reverse('search'), {'keyword': 'Published'})
        direct_response = self.client.get(reverse('blogs', kwargs={'slug': self.post.slug}))
        followers_response = self.client.get(reverse('author_followers', kwargs={'username': self.author.username}))

        self.assertContains(profile_response, self.post.title)
        self.assertContains(home_response, self.post.title)
        self.assertContains(category_response, self.post.title)
        self.assertContains(search_response, self.post.title)
        self.assertContains(direct_response, self.post.title)
        self.assertEqual(followers_response.status_code, 200)

    def test_private_author_can_view_own_posts(self):
        self.author.profile.is_private = True
        self.author.profile.save()
        self.client.login(username='author', password='pass12345')

        profile_response = self.client.get(reverse('author_profile', kwargs={'username': self.author.username}))
        home_response = self.client.get(reverse('home'))
        direct_response = self.client.get(reverse('blogs', kwargs={'slug': self.post.slug}))

        self.assertContains(profile_response, self.post.title)
        self.assertContains(home_response, self.post.title)
        self.assertContains(direct_response, self.post.title)

    def test_guest_cannot_view_private_author_posts(self):
        self.author.profile.is_private = True
        self.author.profile.save()

        profile_response = self.client.get(reverse('author_profile', kwargs={'username': self.author.username}))
        home_response = self.client.get(reverse('home'))
        direct_response = self.client.get(reverse('blogs', kwargs={'slug': self.post.slug}))

        self.assertContains(profile_response, 'This account is private.')
        self.assertNotContains(profile_response, self.post.title)
        self.assertNotContains(home_response, self.post.title)
        self.assertEqual(direct_response.status_code, 403)

    def test_public_follow_lists_are_visible_to_guests(self):
        self.reader.first_name = 'Reader'
        self.reader.last_name = 'User'
        self.reader.save()
        Follow.objects.create(follower=self.reader, following=self.author, status='accepted')
        Follow.objects.create(follower=self.author, following=self.reader, status='accepted')

        followers_response = self.client.get(reverse('api_user_followers', kwargs={'user_id': self.author.id}))
        following_response = self.client.get(reverse('api_user_following', kwargs={'user_id': self.author.id}))

        self.assertEqual(followers_response.status_code, 200)
        self.assertEqual(followers_response.json()['users'][0]['name'], 'Reader User')
        self.assertEqual(following_response.status_code, 200)
        self.assertEqual(following_response.json()['users'][0]['name'], 'Reader User')
        self.assertIn('avatar_url', followers_response.json()['users'][0])

    def test_private_follow_lists_require_owner_or_accepted_follower(self):
        self.author.profile.is_private = True
        self.author.profile.save()
        Follow.objects.create(follower=self.reader, following=self.author, status='pending')

        guest_response = self.client.get(reverse('api_user_followers', kwargs={'user_id': self.author.id}))
        self.assertEqual(guest_response.status_code, 403)

        self.client.login(username='reader', password='pass12345')
        pending_response = self.client.get(reverse('api_user_followers', kwargs={'user_id': self.author.id}))
        self.assertEqual(pending_response.status_code, 403)

        Follow.objects.filter(follower=self.reader, following=self.author).update(status='accepted')
        accepted_response = self.client.get(reverse('api_user_followers', kwargs={'user_id': self.author.id}))
        self.assertEqual(accepted_response.status_code, 200)

        self.client.logout()
        self.client.login(username='author', password='pass12345')
        owner_response = self.client.get(reverse('api_user_following', kwargs={'user_id': self.author.id}))
        self.assertEqual(owner_response.status_code, 200)

    def test_profile_renders_follow_list_modal_for_allowed_viewer(self):
        Follow.objects.create(follower=self.reader, following=self.author, status='accepted')
        self.client.login(username='reader', password='pass12345')

        response = self.client.get(reverse('author_profile', kwargs={'username': self.author.username}))

        self.assertContains(response, 'id="follow-list-modal"')
        self.assertContains(response, reverse('api_user_followers', kwargs={'user_id': self.author.id}))
        self.assertContains(response, reverse('api_user_following', kwargs={'user_id': self.author.id}))

    def test_pending_follow_does_not_unlock_private_posts(self):
        self.author.profile.is_private = True
        self.author.profile.save()
        Follow.objects.create(follower=self.reader, following=self.author, status='pending')
        self.client.login(username='reader', password='pass12345')

        profile_response = self.client.get(reverse('author_profile', kwargs={'username': self.author.username}))
        home_response = self.client.get(reverse('home'))
        direct_response = self.client.get(reverse('blogs', kwargs={'slug': self.post.slug}))

        self.assertContains(profile_response, 'This account is private.')
        self.assertNotContains(home_response, self.post.title)
        self.assertEqual(direct_response.status_code, 403)

    def test_blogger_directory_shows_privacy_badge_and_follow_state(self):
        self.author.profile.is_private = True
        self.author.profile.bio = 'Writes about technology.'
        self.author.profile.save()
        Follow.objects.create(follower=self.reader, following=self.author, status='pending')
        self.client.login(username='reader', password='pass12345')

        response = self.client.get(reverse('blogger_directory'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Explore Bloggers')
        self.assertContains(response, 'Private')
        self.assertContains(response, 'Writes about technology.')
        self.assertContains(response, 'Requested')

    def test_api_follow_public_private_accept_decline_and_unfollow(self):
        self.client.login(username='reader', password='pass12345')

        public_response = self.client.post(reverse('api_follow', kwargs={'user_id': self.author.id}))
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(public_response.json()['follow_status'], 'following')
        self.assertTrue(Follow.objects.filter(
            follower=self.reader,
            following=self.author,
            status='accepted',
        ).exists())

        Follow.objects.filter(follower=self.reader, following=self.author).delete()
        self.author.profile.is_private = True
        self.author.profile.save()

        private_response = self.client.post(
            reverse('api_follow', kwargs={'user_id': self.author.id})
        )
        self.assertEqual(private_response.status_code, 200)
        self.assertEqual(private_response.json()['follow_status'], 'requested')
        follow = Follow.objects.get(follower=self.reader, following=self.author)
        self.assertEqual(follow.status, 'pending')

        self.client.logout()
        self.client.login(username='author', password='pass12345')
        accept_response = self.client.post(reverse('api_accept_follow', kwargs={'request_id': follow.id}))
        self.assertEqual(accept_response.status_code, 200)
        follow.refresh_from_db()
        self.assertEqual(follow.status, 'accepted')

        self.client.logout()
        self.client.login(username='reader', password='pass12345')
        unfollow_response = self.client.delete(reverse('api_unfollow', kwargs={'user_id': self.author.id}))
        self.assertEqual(unfollow_response.status_code, 200)
        self.assertFalse(Follow.objects.filter(follower=self.reader, following=self.author).exists())

        self.client.post(reverse('api_follow', kwargs={'user_id': self.author.id}))
        follow = Follow.objects.get(follower=self.reader, following=self.author)
        self.client.logout()
        self.client.login(username='author', password='pass12345')
        decline_response = self.client.post(reverse('api_decline_follow', kwargs={'request_id': follow.id}))
        self.assertEqual(decline_response.status_code, 200)
        self.assertFalse(Follow.objects.filter(id=follow.id).exists())
