from django.core.management.base import BaseCommand
from discussion.models import Bulletin, Post

class Command(BaseCommand):
    help = 'Removes dummy posts and bulletins created by the generate_dummy_data command.'

    def handle(self, *args, **options):
        
        posts_deleted, _ = Post.objects.filter(title__startswith='[DUMMY]').delete()
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {posts_deleted} dummy posts.'))

        bulletins_deleted, _ = Bulletin.objects.filter(title__startswith='[DUMMY]').delete()
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {bulletins_deleted} dummy bulletins.'))
        
        self.stdout.write(self.style.SUCCESS('Dummy data removal complete.'))