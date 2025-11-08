from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from .models import Bulletin, Post, Comment, Attachment, Label, BulletinReadStatus
from .forms import PostForm, CommentForm, BulletinForm
from django.contrib.admin.views.decorators import staff_member_required
import markdown
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os
from user_system.models import User
from msg_system.models import Message

@login_required
def upload_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        image = request.FILES['image']
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'easymde_uploads'))
        filename = fs.save(image.name, image)
        image_url = os.path.join(settings.MEDIA_URL, 'easymde_uploads', filename)
        return JsonResponse({'url': image_url})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def label_autocomplete(request):
    if 'term' in request.GET:
        qs = Label.objects.filter(name__icontains=request.GET.get('term'))
        labels = list(qs.values_list('name', flat=True))
        return JsonResponse(labels, safe=False)
    return JsonResponse([], safe=False)

@login_required
def discussion_home(request):
    # Pinned bulletins are always shown
    pinned_bulletins = Bulletin.objects.filter(pinned=True).order_by('-updated_at')
    
    # Paginate the non-pinned bulletins
    bulletin_list = Bulletin.objects.filter(pinned=False).order_by('-created_at')
    bulletin_paginator = Paginator(bulletin_list, 5)  # Show 5 bulletins per page
    bulletin_page_number = request.GET.get('bpage')
    bulletins = bulletin_paginator.get_page(bulletin_page_number)

    # Calculate page range for bulletins
    num_bulletin_pages = bulletin_paginator.num_pages
    current_bulletin_page = bulletins.number
    if num_bulletin_pages <= 5:
        bulletin_page_range = bulletin_paginator.page_range
    else:
        start = max(1, current_bulletin_page - 2)
        end = min(num_bulletin_pages, start + 4)
        if end - start < 4:
            start = max(1, end - 4)
        bulletin_page_range = range(start, end + 1)

    pinned_posts = Post.objects.filter(pinned=True).order_by('-updated_at')
    posts_list = Post.objects.filter(pinned=False).order_by('-created_at')
    categories = Post.POST_CATEGORIES

    category_filter = request.GET.get('category')
    if category_filter:
        posts_list = posts_list.filter(category=category_filter)
        pinned_posts = pinned_posts.filter(category=category_filter)

    query = request.GET.get('q')
    if query:
        posts_list = posts_list.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )
        pinned_posts = pinned_posts.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )

    paginator = Paginator(posts_list, 10) # Show 10 posts per page.
    page_number = request.GET.get('page')
    posts = paginator.get_page(page_number)

    # Calculate page range for posts
    num_post_pages = paginator.num_pages
    current_post_page = posts.number
    if num_post_pages <= 5:
        post_page_range = paginator.page_range
    else:
        start = max(1, current_post_page - 2)
        end = min(num_post_pages, start + 4)
        if end - start < 4:
            start = max(1, end - 4)
        post_page_range = range(start, end + 1)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, '_post_list.html', {
            'pinned_posts': pinned_posts,
            'posts': posts,
            'post_page_range': post_page_range,
        })

    return render(request, 'discussion_home.html', {
        'pinned_bulletins': pinned_bulletins,
        'bulletins': bulletins,
        'bulletin_page_range': bulletin_page_range,
        'pinned_posts': pinned_posts,
        'posts': posts,
        'post_page_range': post_page_range,
        'categories': [category[0] for category in categories]
    })

@login_required
def bulletin_detail(request, pk):
    bulletin = get_object_or_404(Bulletin, pk=pk)
    if request.user.is_authenticated and not request.user.is_staff:
        BulletinReadStatus.objects.get_or_create(bulletin=bulletin, user=request.user)
    
    read_count = BulletinReadStatus.objects.filter(bulletin=bulletin).count()
    
    return render(request, 'bulletin_detail.html', {'bulletin': bulletin, 'read_count': read_count})

@staff_member_required
def bulletin_read_status(request, pk):
    bulletin = get_object_or_404(Bulletin, pk=pk)
    
    read_users = User.objects.filter(bulletinreadstatus__bulletin=bulletin)
    unread_users = User.objects.exclude(id__in=read_users.values_list('id', flat=True)).exclude(is_superuser=True)

    return render(request, 'bulletin_read_status.html', {
        'bulletin': bulletin,
        'read_users': read_users,
        'unread_users': unread_users
    })

@login_required
def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.raw_content = form.cleaned_data['content']
            comment.content = markdown.markdown(form.cleaned_data['content'])
            comment.save()
            return redirect('post_detail', pk=post.pk)
    else:
        form = CommentForm()
    return render(request, 'post_detail.html', {'post': post, 'form': form})

@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, user=request.user)
        files = request.FILES.getlist('attachments')
        
        # Check for duplicate filenames
        filenames = [f.name for f in files]
        if len(filenames) != len(set(filenames)):
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                Message.objects.create(
                    sender=admin_user,
                    recipient=request.user,
                    subject="File Upload Error",
                    body="Duplicate filenames are not allowed."
                )
            return render(request, 'create_post.html', {'form': form})

        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.raw_content = form.cleaned_data['content']
            post.content = markdown.markdown(form.cleaned_data['content'])
            post.save()

            # Handle labels
            label_names = [name.strip() for name in form.cleaned_data['labels'].split(',') if name.strip()]
            post.labels.clear()
            for name in label_names:
                label, created = Label.objects.get_or_create(name=name)
                post.labels.add(label)

            for f in files:
                Attachment.objects.create(post=post, file=f)
            return redirect('discussion_home')
    else:
        form = PostForm(user=request.user)
    return render(request, 'create_post.html', {'form': form})

@staff_member_required
def manage_bulletin(request):
    bulletin_list = Bulletin.objects.all().order_by('-created_at')
    paginator = Paginator(bulletin_list, 10) # Show 10 bulletins per page.
    page_number = request.GET.get('page')
    bulletins = paginator.get_page(page_number)
    if request.method == 'POST':
        form = BulletinForm(request.POST, request.FILES)
        files = request.FILES.getlist('attachments')

        # Check for duplicate filenames
        filenames = [f.name for f in files]
        if len(filenames) != len(set(filenames)):
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                Message.objects.create(
                    sender=admin_user,
                    recipient=request.user,
                    subject="File Upload Error",
                    body="Duplicate filenames are not allowed."
                )
            return render(request, 'manage_bulletin.html', {'form': form, 'bulletins': bulletins})

        if form.is_valid():
            bulletin = form.save(commit=False)
            bulletin.raw_content = form.cleaned_data['content']
            bulletin.content = markdown.markdown(form.cleaned_data['content'])
            bulletin.save()
            for f in files:
                Attachment.objects.create(bulletin=bulletin, file=f)
            return redirect('manage_bulletin')
    else:
        form = BulletinForm()
    return render(request, 'manage_bulletin.html', {'form': form, 'bulletins': bulletins})

@staff_member_required
def edit_bulletin(request, pk):
    bulletin = get_object_or_404(Bulletin, pk=pk)
    if request.method == 'POST':
        form = BulletinForm(request.POST, request.FILES, instance=bulletin)
        files = request.FILES.getlist('attachments')
        
        remove_attachments_ids = request.POST.get('remove_attachments', '')
        attachment_ids_to_remove = [int(id) for id in remove_attachments_ids.split(',') if id.isdigit()]

        # Check for duplicate filenames against attachments that are not being removed.
        existing_attachments = bulletin.attachments.exclude(id__in=attachment_ids_to_remove)
        existing_filenames = [os.path.basename(a.file.name) for a in existing_attachments]
        new_filenames = [f.name for f in files]
        
        if len(new_filenames) != len(set(new_filenames)) or any(f in existing_filenames for f in new_filenames):
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                Message.objects.create(
                    sender=admin_user,
                    recipient=request.user,
                    subject="File Upload Error",
                    body="Duplicate filenames are not allowed."
                )
            return render(request, 'edit_bulletin.html', {'form': form})

        if attachment_ids_to_remove:
            Attachment.objects.filter(id__in=attachment_ids_to_remove, bulletin=bulletin).delete()

        if form.is_valid():
            bulletin = form.save(commit=False)
            bulletin.raw_content = form.cleaned_data['content']
            bulletin.content = markdown.markdown(form.cleaned_data['content'])
            bulletin.save()
            for f in files:
                Attachment.objects.create(bulletin=bulletin, file=f)
            return redirect('manage_bulletin')
    else:
        form = BulletinForm(instance=bulletin)
    return render(request, 'edit_bulletin.html', {'form': form})

from msg_system.models import Message

@staff_member_required
def delete_bulletin(request, pk):
    bulletin = get_object_or_404(Bulletin, pk=pk)
    if request.method == 'POST':
        bulletin_title = bulletin.title
        bulletin.delete()
        admin_user = User.objects.filter(is_superuser=True).first()
        if admin_user:
            Message.objects.create(
                sender=admin_user,
                recipient=request.user,
                subject="Bulletin Deleted",
                body=f"The bulletin '{bulletin_title}' was deleted successfully."
            )
        return redirect('manage_bulletin')
    return render(request, 'confirm_delete.html', {'object': bulletin})

@login_required
def edit_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.user != post.author and not request.user.is_staff:
        return redirect('post_detail', pk=pk)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post, user=request.user)
        files = request.FILES.getlist('attachments')
        
        remove_attachments_ids = request.POST.get('remove_attachments', '')
        attachment_ids_to_remove = [int(id) for id in remove_attachments_ids.split(',') if id.isdigit()]

        # Check for duplicate filenames against attachments that are not being removed.
        existing_attachments = post.attachments.exclude(id__in=attachment_ids_to_remove)
        existing_filenames = [os.path.basename(a.file.name) for a in existing_attachments]
        new_filenames = [f.name for f in files]

        if len(new_filenames) != len(set(new_filenames)) or any(f in existing_filenames for f in new_filenames):
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                Message.objects.create(
                    sender=admin_user,
                    recipient=request.user,
                    subject="File Upload Error",
                    body="Duplicate filenames are not allowed."
                )
            return render(request, 'edit_post.html', {'form': form})

        if attachment_ids_to_remove:
            Attachment.objects.filter(id__in=attachment_ids_to_remove, post=post).delete()

        if form.is_valid():
            post = form.save(commit=False)
            post.raw_content = form.cleaned_data['content']
            post.content = markdown.markdown(form.cleaned_data['content'])
            post.save()

            # Handle labels
            label_names = [name.strip() for name in form.cleaned_data['labels'].split(',') if name.strip()]
            post.labels.clear()
            for name in label_names:
                label, created = Label.objects.get_or_create(name=name)
                post.labels.add(label)

            for f in files:
                Attachment.objects.create(post=post, file=f)
            return redirect('post_detail', pk=post.pk)
    else:
        form = PostForm(instance=post, user=request.user)
    return render(request, 'edit_post.html', {'form': form})

@login_required
def delete_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    admin_user = User.objects.filter(is_superuser=True).first()

    if request.user != post.author and not request.user.is_staff:
        if admin_user:
            Message.objects.create(
                sender=admin_user,
                recipient=request.user,
                subject="Unauthorized Action",
                body="You are not authorized to delete this post."
            )
        return redirect('post_detail', pk=pk)

    if request.method == 'POST':
        post_title = post.title
        post.delete()
        if admin_user:
            Message.objects.create(
                sender=admin_user,
                recipient=request.user,
                subject="Post Deleted",
                body=f"The post '{post_title}' was deleted successfully."
            )
        return redirect('discussion_home')

    return render(request, 'confirm_delete.html', {'object': post})



@login_required
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    post_pk = comment.post.pk
    admin_user = User.objects.filter(is_superuser=True).first()

    if request.user != comment.author and not request.user.is_staff:
        if admin_user:
            Message.objects.create(
                sender=admin_user,
                recipient=request.user,
                subject="Unauthorized Action",
                body="You are not authorized to delete this comment."
            )
        return redirect('post_detail', pk=post_pk)

    if request.method == 'POST':
        comment.delete()
        if admin_user:
            Message.objects.create(
                sender=admin_user,
                recipient=request.user,
                subject="Comment Deleted",
                body="Your comment was deleted successfully."
            )
        return redirect('post_detail', pk=post_pk)

    return render(request, 'confirm_delete.html', {'object': comment})
