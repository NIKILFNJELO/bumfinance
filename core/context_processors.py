from .models import FriendRequest, Group, GroupRead, Notification


def unread_friend_requests(user):
    return FriendRequest.objects.filter(receiver=user, status='pending').count()


def unread_group_messages(user):
    total = 0
    for g in Group.objects.filter(memberships__user=user).distinct():
        read = GroupRead.objects.filter(user=user, group=g).first()
        qs = g.messages.exclude(author=user)
        if read:
            qs = qs.filter(created_at__gt=read.last_seen)
        total += qs.count()
    return total


def unread_notifications(user):
    return Notification.objects.filter(user=user, is_read=False).count()


def badges(request):
    if not request.user.is_authenticated:
        return {}
    return {
        'friend_requests_count': unread_friend_requests(request.user),
        'group_messages_count': unread_group_messages(request.user),
        'notifications_count': unread_notifications(request.user),
    }