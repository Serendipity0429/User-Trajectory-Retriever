import random
import string
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from discussion.models import Bulletin, Post

User = get_user_model()

def generate_random_string(length=10):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

class Command(BaseCommand):
    help = 'Generates random bulletin and post data for testing.'

    def add_arguments(self, parser):
        parser.add_argument('--bulletins', type=int, help='Number of bulletins to create.', default=5)
        parser.add_argument('--posts', type=int, help='Number of posts to create.', default=15)

    def handle(self, *args, **options):
        num_bulletins = options['bulletins']
        num_posts = options['posts']

        try:
            test_user = User.objects.get(username='test')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('User "test" not found. Please create a user with the username "test".'))
            return

        bulletin_categories = [category[0] for category in Bulletin.BULLETIN_CATEGORIES]
        post_categories = [category[0] for category in Post.POST_CATEGORIES]

        for _ in range(num_bulletins):
            bulletin_title = '[DUMMY] ' + ' '.join(generate_random_string(random.randint(5, 10)).capitalize() for i in range(3))
            bulletin_content = ' '.join(generate_random_string(random.randint(5, 15)) for i in range(20))
            bulletin_category = random.choice(bulletin_categories)
            Bulletin.objects.create(
                title=bulletin_title,
                content=bulletin_content,
                category=bulletin_category
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created bulletin: "{bulletin_title}"'))

        for _ in range(num_posts):
            post_title = '[DUMMY] ' + ' '.join(generate_random_string(random.randint(5, 10)).capitalize() for i in range(4))
            post_content = ' '.join(generate_random_string(random.randint(5, 15)) for i in range(50))
            post_category = random.choice(post_categories)
            Post.objects.create(
                title=post_title,
                content=post_content,
                author=test_user,
                category=post_category
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created post: "{post_title}"'))

        self.stdout.write(self.style.SUCCESS('Dummy data generation complete.'))