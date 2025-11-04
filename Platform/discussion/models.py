from django.db import models
from user_system.models import User

class Bulletin(models.Model):
    BULLETIN_CATEGORIES = [
        ('General', 'General'),
        ('System Update', 'System Update'),
        ('Maintenance', 'Maintenance'),
        ('Important', 'Important'),
        ('Event', 'Event'),
        ('Warning', 'Warning'),
    ]
    title = models.CharField(max_length=200)
    content = models.TextField()
    raw_content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    pinned = models.BooleanField(default=False)
    category = models.CharField(max_length=50, choices=BULLETIN_CATEGORIES, default='General')

    def __str__(self):
        return self.title

class Post(models.Model):
    POST_CATEGORIES = [
        ('General', 'General'),
        ('Technical Support', 'Technical Support'),
        ('Feedback & Suggestions', 'Feedback & Suggestions'),
        ('Bugs & Issues', 'Bugs & Issues'),
    ]
    title = models.CharField(max_length=200)
    content = models.TextField()
    raw_content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=50, choices=POST_CATEGORIES, default='General')
    labels = models.ManyToManyField('Label', blank=True)
    pinned = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class Comment(models.Model):
    post = models.ForeignKey(Post, related_name='comments', on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    raw_content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment by {self.author} on {self.post}'

class Attachment(models.Model):
    post = models.ForeignKey(Post, related_name='attachments', on_delete=models.CASCADE, null=True, blank=True)
    bulletin = models.ForeignKey(Bulletin, related_name='attachments', on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(upload_to='attachments/')

    def __str__(self):
        return self.file.name



class Label(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name