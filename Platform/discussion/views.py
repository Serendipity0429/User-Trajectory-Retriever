from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from .models import (
    Bulletin,
    Post,
    Comment,
    Attachment,
    Label,
    BulletinReadStatus,
    DiscussionSettings,
)
from .forms import PostForm, CommentForm, BulletinForm, DiscussionSettingsForm
from django.contrib.admin.views.decorators import staff_member_required
import markdown
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os
from user_system.models import User
from task_manager.models import ExtensionVersion
from msg_system.utils import send_system_message


@staff_member_required
def discussion_settings(request):
    settings = DiscussionSettings.load()
    if request.method == "POST":
        form = DiscussionSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            return redirect("discussion_settings")
    else:
        form = DiscussionSettingsForm(instance=settings)
    return render(request, "discussion_settings.html", {"form": form})


@login_required
def upload_image(request):
    if request.method == "POST" and request.FILES.get("image"):
        image = request.FILES["image"]
        fs = FileSystemStorage(
            location=os.path.join(settings.MEDIA_ROOT, "easymde_uploads")
        )
        filename = fs.save(image.name, image)
        image_url = os.path.join(settings.MEDIA_URL, "easymde_uploads", filename)
        return JsonResponse({"url": image_url})
    return JsonResponse({"error": "Invalid request"}, status=400)


@login_required
def label_autocomplete(request):
    if "term" in request.GET:
        qs = Label.objects.filter(name__icontains=request.GET.get("term"))
        labels = list(qs.values_list("name", flat=True))
        return JsonResponse(labels, safe=False)
    return JsonResponse([], safe=False)


@login_required
def discussion_home(request):
    # Pinned bulletins are always shown
    from django.utils import timezone

    now = timezone.now()

    pinned_bulletins_query = Bulletin.objects.filter(pinned=True)
    bulletin_list_query = Bulletin.objects.filter(pinned=False)

    if not request.user.is_staff:
        pinned_bulletins_query = pinned_bulletins_query.filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gt=now)
        )
        bulletin_list_query = bulletin_list_query.filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gt=now)
        )

    pinned_bulletins = pinned_bulletins_query.order_by("-updated_at")
    bulletin_list = bulletin_list_query.order_by("-created_at")

    # Paginate the non-pinned bulletins
    bulletin_paginator = Paginator(bulletin_list, 5)  # Show 5 bulletins per page
    bulletin_page_number = request.GET.get("bpage")
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

    # Base querysets
    pinned_posts = Post.objects.filter(pinned=True).order_by("-updated_at")
    posts_list = Post.objects.filter(pinned=False).order_by("-created_at")

    # Post creation limit for non-staff users
    post_limit_reached = False
    if not request.user.is_staff:
        from django.utils import timezone
        from datetime import timedelta

        settings = DiscussionSettings.load()
        one_day_ago = timezone.now() - timedelta(days=1)
        post_count_today = Post.objects.filter(
            author=request.user, created_at__gte=one_day_ago
        ).count()
        if post_count_today >= settings.post_limit_per_day:
            post_limit_reached = True

    # Filtering based on 'show' parameter
    show_filter = request.GET.get("show")
    if show_filter == "my_posts":
        posts_list = posts_list.filter(author=request.user)
        pinned_posts = pinned_posts.filter(author=request.user)
    elif show_filter == "open":
        posts_list = posts_list.filter(is_closed=False)
        pinned_posts = pinned_posts.filter(is_closed=False)
    elif show_filter == "closed":
        posts_list = posts_list.filter(is_closed=True)
        pinned_posts = pinned_posts.filter(is_closed=True)
    elif show_filter == "hidden" and request.user.is_staff:
        posts_list = posts_list.filter(is_hidden=True)
        pinned_posts = pinned_posts.filter(is_hidden=True)
    else:
        # Default filtering
        posts_list = posts_list.exclude(is_hidden=True)
        pinned_posts = pinned_posts.exclude(is_hidden=True)
        if not request.user.is_staff:
            posts_list = posts_list.filter(Q(is_private=False) | Q(author=request.user))
            pinned_posts = pinned_posts.filter(
                Q(is_private=False) | Q(author=request.user)
            )

    categories = Post.POST_CATEGORIES

    category_filter = request.GET.get("category")
    if category_filter:
        posts_list = posts_list.filter(category=category_filter)
        pinned_posts = pinned_posts.filter(category=category_filter)

    query = request.GET.get("q")
    if query:
        posts_list = posts_list.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )
        pinned_posts = pinned_posts.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )

    paginator = Paginator(posts_list, 10)  # Show 10 posts per page.
    page_number = request.GET.get("page")
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

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(
            request,
            "_post_list.html",
            {
                "pinned_posts": pinned_posts,
                "posts": posts,
                "post_page_range": post_page_range,
            },
        )

    return render(
        request,
        "discussion_home.html",
        {
            "now": now,
            "pinned_bulletins": pinned_bulletins,
            "bulletins": bulletins,
            "bulletin_page_range": bulletin_page_range,
            "pinned_posts": pinned_posts,
            "posts": posts,
            "post_page_range": post_page_range,
            "categories": categories,
            "post_limit_reached": post_limit_reached,
        },
    )


@login_required
def bulletin_detail(request, pk):
    bulletin = get_object_or_404(Bulletin, pk=pk)
    from django.utils import timezone

    now = timezone.now()
    if (
        bulletin.expiry_date
        and bulletin.expiry_date < now
        and not request.user.is_staff
    ):
        return redirect("discussion_home")

    if request.user.is_authenticated and not request.user.is_staff:
        BulletinReadStatus.objects.get_or_create(bulletin=bulletin, user=request.user)

    read_count = BulletinReadStatus.objects.filter(bulletin=bulletin).count()

    return render(
        request,
        "bulletin_detail.html",
        {"bulletin": bulletin, "read_count": read_count, "now": now},
    )


@staff_member_required
def bulletin_read_status(request, pk):
    bulletin = get_object_or_404(Bulletin, pk=pk)

    read_users = User.objects.filter(bulletinreadstatus__bulletin=bulletin)
    unread_users = User.objects.exclude(
        id__in=read_users.values_list("id", flat=True)
    ).exclude(is_superuser=True)

    return render(
        request,
        "bulletin_read_status.html",
        {"bulletin": bulletin, "read_users": read_users, "unread_users": unread_users},
    )


@login_required
def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk)

    # Authorization check
    is_author = post.author == request.user
    is_staff = request.user.is_staff

    if post.is_hidden and not is_staff:
        return redirect("discussion_home")

    if post.is_private and not is_author and not is_staff:
        return redirect("discussion_home")

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.raw_content = form.cleaned_data["content"]
            comment.content = markdown.markdown(form.cleaned_data["content"])
            comment.save()
            return redirect("post_detail", pk=post.pk)
    else:
        form = CommentForm()
    return render(request, "post_detail.html", {"post": post, "form": form})


@login_required
def create_post(request):
    # Check for post frequency: if user posted in the last 5 minutes
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    five_minutes_ago = now - timedelta(minutes=5)
    recent_posts_count = Post.objects.filter(
        author=request.user, created_at__gte=five_minutes_ago
    ).count()
    require_captcha = recent_posts_count >= 1 and not request.user.is_staff

    if request.method == "POST":
        form = PostForm(
            request.POST,
            request.FILES,
            user=request.user,
            require_captcha=require_captcha,
        )
        files = request.FILES.getlist("attachments")

        # Check for duplicate filenames
        filenames = [f.name for f in files]
        if len(filenames) != len(set(filenames)):
            send_system_message(
                request.user,
                "File Upload Error",
                "Duplicate filenames are not allowed.",
            )
            return render(request, "create_post.html", {"form": form})

        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.raw_content = form.cleaned_data["content"]
            post.content = markdown.markdown(form.cleaned_data["content"])
            if "is_private" in form.cleaned_data:
                post.is_private = form.cleaned_data["is_private"]
            post.save()

            # Handle labels
            label_names = [
                name.strip()
                for name in form.cleaned_data["labels"].split(",")
                if name.strip()
            ]
            post.labels.clear()
            for name in label_names:
                label, created = Label.objects.get_or_create(name=name)
                post.labels.add(label)

            for f in files:
                Attachment.objects.create(post=post, file=f)
            return redirect("discussion_home")
    else:
        form = PostForm(user=request.user, require_captcha=require_captcha)
    return render(request, "create_post.html", {"form": form})


@staff_member_required
def manage_bulletin(request):
    from django.utils import timezone

    now = timezone.now()
    bulletin_list = Bulletin.objects.all().order_by("-created_at")
    paginator = Paginator(bulletin_list, 10)  # Show 10 bulletins per page.
    page_number = request.GET.get("page")
    bulletins = paginator.get_page(page_number)
    if request.method == "POST":
        form = BulletinForm(request.POST, request.FILES)
        files = request.FILES.getlist("attachments")

        # Check for duplicate filenames
        filenames = [f.name for f in files]
        if len(filenames) != len(set(filenames)):
            send_system_message(
                request.user,
                "File Upload Error",
                "Duplicate filenames are not allowed.",
            )
            return render(
                request,
                "manage_bulletin.html",
                {"form": form, "bulletins": bulletins, "now": now},
            )

        if form.is_valid():
            bulletin = form.save(commit=False)
            bulletin.raw_content = form.cleaned_data["content"]
            bulletin.content = markdown.markdown(form.cleaned_data["content"])

            if request.POST.get("permanent") == "on":
                bulletin.expiry_date = None

            bulletin.save()
            for f in files:
                Attachment.objects.create(bulletin=bulletin, file=f)

            if form.cleaned_data.get("is_extension_update"):
                ExtensionVersion.objects.create(
                    version=form.cleaned_data["extension_version"],
                    update_link=reverse("bulletin_detail", args=[bulletin.pk]),
                    description=bulletin.raw_content,
                )

            return redirect("manage_bulletin")
    else:
        form = BulletinForm()
    return render(
        request,
        "manage_bulletin.html",
        {"form": form, "bulletins": bulletins, "now": now},
    )


@staff_member_required
def edit_bulletin(request, pk):
    bulletin = get_object_or_404(Bulletin, pk=pk)
    if request.method == "POST":
        form = BulletinForm(request.POST, request.FILES, instance=bulletin)
        files = request.FILES.getlist("attachments")

        remove_attachments_ids = request.POST.get("remove_attachments", "")
        attachment_ids_to_remove = [
            int(id) for id in remove_attachments_ids.split(",") if id.isdigit()
        ]

        # Check for duplicate filenames against attachments that are not being removed.
        existing_attachments = bulletin.attachments.exclude(
            id__in=attachment_ids_to_remove
        )
        existing_filenames = [
            os.path.basename(a.file.name) for a in existing_attachments
        ]
        new_filenames = [f.name for f in files]

        if len(new_filenames) != len(set(new_filenames)) or any(
            f in existing_filenames for f in new_filenames
        ):
            send_system_message(
                request.user,
                "File Upload Error",
                "Duplicate filenames are not allowed.",
            )
            return render(request, "edit_bulletin.html", {"form": form})

        if attachment_ids_to_remove:
            Attachment.objects.filter(
                id__in=attachment_ids_to_remove, bulletin=bulletin
            ).delete()

        if form.is_valid():
            bulletin = form.save(commit=False)
            bulletin.raw_content = form.cleaned_data["content"]
            bulletin.content = markdown.markdown(form.cleaned_data["content"])

            if request.POST.get("permanent") == "on":
                bulletin.expiry_date = None

            bulletin.save()
            for f in files:
                Attachment.objects.create(bulletin=bulletin, file=f)

            if form.cleaned_data.get("is_extension_update"):
                ExtensionVersion.objects.create(
                    version=form.cleaned_data["extension_version"],
                    update_link=reverse("bulletin_detail", args=[bulletin.pk]),
                    description=bulletin.raw_content,
                )

            return redirect("manage_bulletin")
    else:
        form = BulletinForm(instance=bulletin)
    return render(request, "edit_bulletin.html", {"form": form})


@staff_member_required
def delete_bulletin(request, pk):
    bulletin = get_object_or_404(Bulletin, pk=pk)
    if request.method == "POST":
        bulletin_title = bulletin.title
        bulletin.delete()
        send_system_message(
            request.user,
            "Bulletin Deleted",
            f"The bulletin '{bulletin_title}' was deleted successfully.",
        )
        return redirect("manage_bulletin")
    return render(request, "confirm_delete.html", {"object": bulletin})


@login_required
def edit_post(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.user != post.author and not request.user.is_staff:
        return redirect("post_detail", pk=pk)
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post, user=request.user)
        files = request.FILES.getlist("attachments")

        remove_attachments_ids = request.POST.get("remove_attachments", "")
        attachment_ids_to_remove = [
            int(id) for id in remove_attachments_ids.split(",") if id.isdigit()
        ]

        # Check for duplicate filenames against attachments that are not being removed.
        existing_attachments = post.attachments.exclude(id__in=attachment_ids_to_remove)
        existing_filenames = [
            os.path.basename(a.file.name) for a in existing_attachments
        ]
        new_filenames = [f.name for f in files]

        if len(new_filenames) != len(set(new_filenames)) or any(
            f in existing_filenames for f in new_filenames
        ):
            send_system_message(
                request.user,
                "File Upload Error",
                "Duplicate filenames are not allowed.",
            )
            return render(request, "edit_post.html", {"form": form})

        if attachment_ids_to_remove:
            Attachment.objects.filter(
                id__in=attachment_ids_to_remove, post=post
            ).delete()

        if form.is_valid():
            post = form.save(commit=False)
            post.raw_content = form.cleaned_data["content"]
            post.content = markdown.markdown(form.cleaned_data["content"])
            if "is_private" in form.cleaned_data:
                post.is_private = form.cleaned_data["is_private"]
            post.save()

            # Handle labels
            label_names = [
                name.strip()
                for name in form.cleaned_data["labels"].split(",")
                if name.strip()
            ]
            post.labels.clear()
            for name in label_names:
                label, created = Label.objects.get_or_create(name=name)
                post.labels.add(label)

            for f in files:
                Attachment.objects.create(post=post, file=f)
            return redirect("post_detail", pk=post.pk)
    else:
        form = PostForm(instance=post, user=request.user)
    return render(request, "edit_post.html", {"form": form})


@login_required
def delete_post(request, pk):
    post = get_object_or_404(Post, pk=pk)

    if request.user != post.author and not request.user.is_staff:
        send_system_message(
            request.user,
            "Unauthorized Action",
            "You are not authorized to delete this post.",
        )
        return redirect("post_detail", pk=pk)

    if request.method == "POST":
        post_title = post.title
        post.delete()
        send_system_message(
            request.user,
            "Post Deleted",
            f"The post '{post_title}' was deleted successfully.",
        )
        return redirect("discussion_home")

    return render(request, "confirm_delete.html", {"object": post})


@login_required
def delete_comment(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    post_pk = comment.post.pk

    if request.user != comment.author and not request.user.is_staff:
        send_system_message(
            request.user,
            "Unauthorized Action",
            "You are not authorized to delete this comment.",
        )
        return redirect("post_detail", pk=post_pk)

    if request.method == "POST":
        comment.delete()
        send_system_message(
            request.user, "Comment Deleted", "Your comment was deleted successfully."
        )
        return redirect("post_detail", pk=post_pk)

    return render(request, "confirm_delete.html", {"object": comment})


@staff_member_required
def toggle_post_hidden(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == "POST":
        post.is_hidden = not post.is_hidden
        post.save()
    return redirect("post_detail", pk=pk)


@login_required
def toggle_post_private(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.user == post.author or request.user.is_staff:
        if request.method == "POST":
            post.is_private = not post.is_private
            post.save()
    return redirect("post_detail", pk=pk)


@login_required
def toggle_post_closed(request, pk):
    post = get_object_or_404(Post, pk=pk)

    # Allow author or staff to close the post
    if not post.is_closed and (request.user == post.author or request.user.is_staff):
        if request.method == "POST":
            post.is_closed = True
            post.save()
    # Only allow staff to reopen the post
    elif post.is_closed and request.user.is_staff:
        if request.method == "POST":
            post.is_closed = False
            post.save()

    return redirect("post_detail", pk=pk)


@staff_member_required
def toggle_comment_hidden(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if request.method == "POST":
        comment.is_hidden = not comment.is_hidden
        comment.save()
    return redirect("post_detail", pk=comment.post.pk)
