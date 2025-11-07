from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Exists, OuterRef
from .models import Message, MessageRecipient
from .forms import MessageForm, ReplyMessageForm
from user_system.models import User

class CreateMessageView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request):
        form = MessageForm()
        return render(request, 'msg_system/create_message.html', {'form': form})

    def post(self, request):
        form = MessageForm(request.POST)
        if form.is_valid():
            sender = request.user
            message = form.save(commit=False)
            message.sender = sender
            message.save()

            is_pinned = form.cleaned_data.get('is_pinned', False)

            if form.cleaned_data['send_to_all']:
                recipients = User.objects.exclude(pk=sender.pk)
            else:
                recipients = form.cleaned_data['recipients']

            for recipient in recipients:
                MessageRecipient.objects.create(
                    message=message, 
                    user=recipient, 
                    is_pinned=is_pinned
                )
            
            return redirect('msg_system:sent_message_list')
        return render(request, 'msg_system/create_message.html', {'form': form})

class SentMessageListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Message
    template_name = 'msg_system/sent_message_list.html'
    context_object_name = 'messages'

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return Message.objects.filter(sender=self.request.user).prefetch_related('recipients').order_by('-timestamp')

class MessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'msg_system/message_list.html'
    context_object_name = 'messages'

    def get_queryset(self):
        user = self.request.user
        # Get the MessageRecipient status for the current user
        recipient_status = MessageRecipient.objects.filter(
            message=OuterRef('pk'),
            user=user
        )
        return Message.objects.filter(recipients=user).annotate(
            is_pinned_for_user=Exists(recipient_status.filter(is_pinned=True)),
            is_read_for_user=Exists(recipient_status.filter(is_read=True)),
        ).order_by('-is_pinned_for_user', '-timestamp')

class MessageDetailView(LoginRequiredMixin, DetailView):
    model = Message
    template_name = 'msg_system/message_detail.html'
    context_object_name = 'message'

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(Q(recipients=user) | Q(sender=user)).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        message = self.get_object()
        
        if user in message.recipients.all():
            status, created = MessageRecipient.objects.get_or_create(message=message, user=user)
            if not status.is_read:
                status.is_read = True
                status.save()
            context['recipient_status'] = status

        return context

class PinMessageView(LoginRequiredMixin, View):
    def post(self, request, pk):
        message = get_object_or_404(Message, pk=pk)
        status = get_object_or_404(MessageRecipient, message=message, user=request.user)
        status.is_pinned = not status.is_pinned
        status.save()
        return redirect('msg_system:message_list')

class DeleteMessageView(LoginRequiredMixin, View):
    def post(self, request, pk):
        message = get_object_or_404(Message, pk=pk)
        status = get_object_or_404(MessageRecipient, message=message, user=request.user)
        status.delete()
        # Optional: If the message has no other recipients, delete the message itself
        if not message.messagerecipient_set.exists():
            message.delete()
        return redirect('msg_system:message_list')

class ReplyMessageView(LoginRequiredMixin, View):
    def get(self, request, pk):
        original_message = get_object_or_404(Message, pk=pk, recipients=request.user)
        form = ReplyMessageForm(initial={
            'subject': f"Re: {original_message.subject}",
        })
        return render(request, 'msg_system/reply_message.html', {'form': form, 'original_message': original_message})

    def post(self, request, pk):
        original_message = get_object_or_404(Message, pk=pk, recipients=request.user)
        form = ReplyMessageForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.sender = request.user
            reply.save()
            MessageRecipient.objects.create(message=reply, user=original_message.sender)
            return redirect('msg_system:message_list')
        return render(request, 'msg_system/reply_message.html', {'form': form, 'original_message': original_message})