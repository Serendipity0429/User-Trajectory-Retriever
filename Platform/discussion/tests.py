from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Post, Comment

User = get_user_model()


class CommentDeletionTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="author", password="password")
        self.admin = User.objects.create_superuser(
            username="admin", password="password", email="admin@example.com"
        )
        self.other_user = User.objects.create_user(
            username="other_user", password="password"
        )

        self.post = Post.objects.create(
            title="Test Post", content="Test Content", author=self.author
        )
        self.comment = Comment.objects.create(
            post=self.post, author=self.author, content="Test Comment"
        )

    def test_author_can_delete_comment(self):
        self.client.login(username="author", password="password")
        response = self.client.post(reverse("delete_comment", args=[self.comment.pk]))
        self.assertRedirects(response, reverse("post_detail", args=[self.post.pk]))
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_admin_can_delete_comment(self):
        self.client.login(username="admin", password="password")
        response = self.client.post(reverse("delete_comment", args=[self.comment.pk]))
        self.assertRedirects(response, reverse("post_detail", args=[self.post.pk]))
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_other_user_cannot_delete_comment(self):
        self.client.login(username="other_user", password="password")
        response = self.client.post(reverse("delete_comment", args=[self.comment.pk]))
        self.assertRedirects(response, reverse("post_detail", args=[self.post.pk]))
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())
