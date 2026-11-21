import calendar
import math
from decimal import Decimal, ROUND_DOWN, InvalidOperation

import csv
import io
import zipfile

from pathlib import Path
from django.conf import settings
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_PATH = Path(settings.BASE_DIR) / 'DejaVuSans.ttf'
pdfmetrics.registerFont(TTFont('DejaVu', str(FONT_PATH)))

from django.http import HttpResponse
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.utils import timezone as tz
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from .models import Profile
import csv
from django.http import HttpResponse
from django.utils import timezone
from .models import Share

from .forms import GoalForm, GroupForm, LimitForm, PasswordChangeUAForm, SharedExpenseForm, SignUpForm, TransactionForm
from .models import (
    Transaction, Limit, Goal, Group, Membership, SharedExpense,
    Share, Settlement, FriendRequest, GroupMessage, GroupRead, Notification,
)
from .services import check_notifications, group_balances, min_settlements

def user_balance(user):
    income = Transaction.objects.filter(user=user, type='income').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    expense = Transaction.objects.filter(user=user, type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    return income - expense

def unread_friend_requests(user):
    return FriendRequest.objects.filter(receiver=user, status='pending').count()


def unread_group_messages(request):
    seen = request.session.get('seen_messages', {})
    total = 0
    for g in Group.objects.filter(memberships__user=request.user).distinct():
        last = seen.get(str(g.pk))
        qs = g.messages.exclude(author=request.user)
        if last:
            qs = qs.filter(created_at__gt=last)
        total += qs.count()
    return total

def user_tx(request):
    return Transaction.objects.filter(user=request.user)


def user_limits(request):
    return Limit.objects.filter(user=request.user)


def user_goals(request):
    return Goal.objects.filter(user=request.user)


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')


def dashboard(request):
    today = timezone.localdate()
    qs = user_tx(request)

    income = qs.filter(type='income', date__year=today.year, date__month=today.month).aggregate(s=Sum('amount'))['s'] or 0
    expense = qs.filter(type='expense', date__year=today.year, date__month=today.month).aggregate(s=Sum('amount'))['s'] or 0
    today_expense = qs.filter(type='expense', date=today).aggregate(s=Sum('amount'))['s'] or 0

    expenses_by_cat = list(
        qs.filter(type='expense', date__year=today.year, date__month=today.month)
          .values('category')
          .annotate(total=Sum('amount'))
          .order_by('-total')
    )
    total_exp = sum(e['total'] for e in expenses_by_cat) or 1

    chart = []
    palette = ['#4A90D9', '#5BC0BE', '#F29E9E', '#F6C667', '#A3A8B8', '#9FB3C8']
    names = dict(Transaction.CATEGORY_CHOICES)
    for i, e in enumerate(expenses_by_cat):
        pct = round(e['total'] / total_exp * 100)
        chart.append({
            'name': names.get(e['category'], e['category']),
            'pct': pct,
            'color': palette[i % len(palette)],
        })

    slices = []
    angle = 0.0
    for c in chart:
        frac = c['pct'] / 100
        if frac >= 1:
            slices.append({'path': 'M1,0 A1,1 0 1,1 -1,0 A1,1 0 1,1 1,0 Z', 'color': c['color']})
            break
        a2 = angle + frac * 2 * math.pi
        x1, y1 = math.cos(angle), math.sin(angle)
        x2, y2 = math.cos(a2), math.sin(a2)
        large = 1 if frac > 0.5 else 0
        slices.append({
            'path': f'M0,0 L{x1:.4f},{y1:.4f} A1,1 0 {large},1 {x2:.4f},{y2:.4f} Z',
            'color': c['color'],
        })
        angle = a2

    return render(request, 'dashboard.html', {
        'slices': slices,
        'balance': income - expense,
        'today_expense': today_expense,
        'month_income': income,
        'recent': qs.order_by('-date', '-id')[:4],
        'chart': chart,
    })





def transactions(request):
    kind = request.GET.get('type', 'all')
    qs = user_tx(request)
    if kind in ('income', 'expense'):
        qs = qs.filter(type=kind)

    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.type == 'expense' and obj.amount > user_balance(request.user):
                form.add_error('amount', 'Сума більша за поточний баланс')
            else:
                obj.user = request.user
                obj.save()
                check_notifications(request.user)
                return redirect('transactions')
    else:
        form = TransactionForm(initial={'date': timezone.localdate()})

    return render(request, 'transactions.html', {
        'items': qs, 'form': form, 'kind': kind,
        'has_any': user_tx(request).exists(),
    })


def limits(request):
    today = timezone.localdate()

    if request.method == 'POST':
        form = LimitForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            return redirect('limits')
    else:
        form = LimitForm(initial={'month': today.replace(day=1)})

    spent_qs = user_tx(request).filter(type='expense', date__year=today.year, date__month=today.month)
    rows = []
    for lim in user_limits(request).filter(month__year=today.year, month__month=today.month):
        if lim.category:
            spent = spent_qs.filter(category=lim.category).aggregate(s=Sum('amount'))['s'] or 0
        else:
            spent = spent_qs.aggregate(s=Sum('amount'))['s'] or 0
        pct = int(spent / lim.amount * 100) if lim.amount else 0
        rows.append({'lim': lim, 'spent': spent, 'pct': min(pct, 100), 'real_pct': pct})

    return render(request, 'limits.html', {
        'rows': rows, 'form': form,
        'has_any': user_limits(request).exists(),
    })


def goals(request):
    if request.method == 'POST':
        form = GoalForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            return redirect('goals')
    else:
        form = GoalForm()

    return render(request, 'goals.html', {
        'goals': user_goals(request),
        'form': form,
        'has_any': user_goals(request).exists(),
    })


def goal_deposit(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == 'POST' and not goal.is_closed:
        try:
            amount = Decimal(request.POST.get('amount', '0'))
        except Exception:
            amount = Decimal('0')

        amount = min(amount, goal.left)

        income_total = user_tx(request).filter(type='income').aggregate(s=Sum('amount'))['s'] or 0
        expense_total = user_tx(request).filter(type='expense').aggregate(s=Sum('amount'))['s'] or 0
        balance = income_total - expense_total

        if 0 < amount <= balance:
            goal.saved += amount
            goal.save()
            check_notifications(request.user)
            Transaction.objects.create(
                user=request.user,
                type='expense',
                amount=amount,
                category='other',
                date=timezone.localdate(),
                comment=f'Поповнення цілі: {goal.title}',
            )
    return redirect('goals')


def notifications(request):
    today = timezone.localdate()
    items = []

    spent_qs = user_tx(request).filter(type='expense', date__year=today.year, date__month=today.month)
    for lim in user_limits(request).filter(month__year=today.year, month__month=today.month):
        if lim.category:
            spent = spent_qs.filter(category=lim.category).aggregate(s=Sum('amount'))['s'] or 0
            name = lim.get_category_display()
        else:
            spent = spent_qs.aggregate(s=Sum('amount'))['s'] or 0
            name = 'Загальний ліміт'
        pct = int(spent / lim.amount * 100) if lim.amount else 0

        if pct > 100:
            items.append({'type': 'danger', 'title': 'Ліміт перевищено',
                          'text': f'{name}: {spent} з {lim.amount} ₴ ({pct}%)'})
        elif pct >= 80:
            items.append({'type': 'warn', 'title': 'Наближення до ліміту',
                          'text': f'{name}: {spent} з {lim.amount} ₴ ({pct}%)'})

    for g in user_goals(request):
        if g.is_closed:
            items.append({'type': 'ok', 'title': 'Ціль досягнута',
                          'text': f'{g.title}: {g.saved} ₴ з {g.target} ₴'})

    filter_kind = request.GET.get('filter', 'all')
    if filter_kind == 'unread':
        items = []

    return render(request, 'notifications.html', {'items': items, 'filter_kind': filter_kind})


def forecast(request):
    today = timezone.localdate()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    day = today.day
    tx = user_tx(request)

    spent = tx.filter(
        type='expense', date__year=today.year, date__month=today.month
    ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    income = tx.filter(
        type='income', date__year=today.year, date__month=today.month
    ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    expected_expense = (spent / day * days_in_month).quantize(Decimal('1')) if day else Decimal('0')
    expected_income = income
    expected_left = expected_income - expected_expense

    daily = []
    running = Decimal('0')
    for d in range(1, days_in_month + 1):
        if d <= day:
            day_sum = tx.filter(
                type='expense', date__year=today.year, date__month=today.month, date__day=d
            ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
            running += day_sum
            daily.append({'day': d, 'actual': float(running), 'forecast': None})
        else:
            daily.append({'day': d, 'actual': None,
                          'forecast': float(spent / day * d) if day else 0})

    limit = user_limits(request).filter(category='', month__year=today.year, month__month=today.month).first()

    W, H = 1320, 400
    max_val = max([float(expected_expense), float(spent), 1]
                  + [d['forecast'] or 0 for d in daily]
                  + [float(limit.amount) if limit else 0])

    def X(d):
        return 40 + (d - 1) / (days_in_month - 1) * (W - 80)

    def Y(v):
        return H - 30 - v / max_val * (H - 60)

    actual_pts = " ".join(f"{X(d['day']):.1f},{Y(d['actual']):.1f}" for d in daily if d['actual'] is not None)
    last_actual = [d for d in daily if d['actual'] is not None][-1]
    forecast_list = [f"{X(last_actual['day']):.1f},{Y(last_actual['actual']):.1f}"]
    forecast_list += [f"{X(d['day']):.1f},{Y(d['forecast']):.1f}" for d in daily if d['forecast'] is not None]
    forecast_pts = " ".join(forecast_list)

    limit_y = Y(float(limit.amount)) if limit else None
    x_labels = [(d, X(d)) for d in (1, 10, 20, days_in_month)]

    # рекомендації
    tips = []
    if expected_left < 0:
        tips.append(f'За темпом витрат місяць закінчиться з дефіцитом близько {-expected_left} ₴. Скороти витрати в найбільших категоріях.')
    elif income > 0:
        tips.append(f'Очікуваний залишок на кінець місяця: {expected_left} ₴. Відклади частину на ціль або резерв.')
    if limit and expected_expense > limit.amount:
        tips.append(f'Прогноз витрат ({expected_expense} ₴) перевищує загальний ліміт ({limit.amount} ₴). Варто переглянути щоденні покупки.')
    if day and spent / day * days_in_month > income and income == 0:
        tips.append('Доходів за місяць ще немає, тож прогноз рахується лише за витратами.')
    if not tips:
        tips.append('Поки що все у нормі. Продовжуй вести витрати, щоб прогноз був точнішим.')

    return render(request, 'forecast.html', {
        'expected_expense': expected_expense,
        'expected_income': expected_income,
        'expected_left': expected_left,
        'limit': limit,
        'actual_pts': actual_pts,
        'forecast_pts': forecast_pts,
        'limit_y': limit_y,
        'W': W, 'H': H,
        'x_labels': x_labels,
        'tips': tips,
    })


def notifications(request):
    filter_kind = request.GET.get('filter', 'all')
    items = Notification.objects.filter(user=request.user)
    if filter_kind == 'unread':
        items = items.filter(is_read=False)
    items = list(items[:50])

    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    return render(request, 'notifications.html', {
        'items': items,
        'filter_kind': filter_kind,
        'has_any': Notification.objects.filter(user=request.user).exists(),
    })


def notifications_clear(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user).delete()
        messages.success(request, 'Сповіщення очищено.')
    return redirect('notifications')




def export(request):
    return render(request, 'export.html')


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})


def friends(request):
    me = request.user
    if request.method == 'POST':
        action = request.POST.get('action')
        target = User.objects.filter(pk=request.POST.get('user_id')).first()
        if action == 'request':
            if target and target != me:
                FriendRequest.objects.get_or_create(sender=me, receiver=target)
                messages.success(request, 'Запит успішно надіслано.')
            else:
                messages.error(request, 'Користувача не знайдено.')
        elif action == 'accept' and target:
            FriendRequest.objects.filter(sender=target, receiver=me).update(status='accepted')
            messages.success(request, 'Запит прийнято.')
        elif action == 'reject' and target:
            FriendRequest.objects.filter(sender=target, receiver=me).delete()
        return redirect('friends')

    q = request.GET.get('q', '').strip()
    found = []
    if q:
        found = User.objects.exclude(pk=me.pk).filter(username__iexact=q)[:10]
        if not found:
            messages.error(request, f'Користувача з логіном «{q}» не знайдено.')

    accepted = FriendRequest.objects.filter(status='accepted').filter(Q(sender=me) | Q(receiver=me))
    friend_ids = {(r.receiver_id if r.sender_id == me.pk else r.sender_id) for r in accepted}
    friend_list = User.objects.filter(pk__in=friend_ids)
    incoming = FriendRequest.objects.filter(receiver=me, status='pending').select_related('sender')
    sent = FriendRequest.objects.filter(sender=me, status='pending').values_list('receiver_id', flat=True)

    return render(request, 'friends.html', {
        'q': q, 'found': found, 'friends': friend_list,
        'incoming': incoming, 'sent_ids': set(sent),
    })


def shared(request):
    groups = list(Group.objects.filter(memberships__user=request.user).distinct())
    active_id = request.GET.get('group')
    active = next((g for g in groups if str(g.pk) == active_id), None) if active_id else None

    for g in groups:
        read = GroupRead.objects.filter(user=request.user, group=g).first()
        qs = g.messages.exclude(author=request.user)
        if read:
            qs = qs.filter(created_at__gt=read.last_seen)
        g.unread = qs.count()

    accepted = FriendRequest.objects.filter(status='accepted').filter(
        Q(sender=request.user) | Q(receiver=request.user)
    )
    friend_ids = {(r.receiver_id if r.sender_id == request.user.pk else r.sender_id) for r in accepted}
    friend_list = User.objects.filter(pk__in=friend_ids)

    members, feed, balances, settlements, candidates = [], [], [], [], []
    my_debt = Decimal('0')

    if active:
        GroupRead.objects.update_or_create(
            user=request.user, group=active,
            defaults={'last_seen': timezone.now()},
        )
        active.unread = 0

        members = [m.user for m in active.memberships.select_related('user')]
        expenses = active.expenses.prefetch_related('shares__user').select_related('payer')
        messages_qs = active.messages.select_related('author')
        feed = sorted(
            [{'kind': 'expense', 'obj': e, 'at': e.created_at} for e in expenses]
            + [{'kind': 'message', 'obj': m, 'at': m.created_at} for m in messages_qs],
            key=lambda x: x['at'],
        )
        balances = group_balances(active)
        settlements = min_settlements(balances)
        candidates = friend_list.exclude(pk__in=[m.pk for m in members])

        my_balance = next(
            (b['amount'] for b in balances if b['user_id'] == request.user.pk),
            Decimal('0'),
        )
        my_debt = -my_balance if my_balance < 0 else Decimal('0')

    return render(request, 'shared.html', {
        'groups': groups,
        'active': active,
        'members': members,
        'feed': feed,
        'balances': balances,
        'settlements': settlements,
        'friends': friend_list,
        'candidates': candidates,
        'group_form': GroupForm(),
        'expense_form': SharedExpenseForm(initial={'date': timezone.localdate()}),
        'user_balance': user_balance(request.user),
        'my_debt': my_debt,
    })


def group_balances(group):
    members = [m.user for m in Membership.objects.filter(group=group).select_related('user')]
    member_ids = {u.pk for u in members}
    balance = {u.pk: Decimal('0') for u in members}

    for exp in SharedExpense.objects.filter(group=group):
        if exp.payer_id in member_ids:
            balance[exp.payer_id] += exp.amount
    for share in Share.objects.filter(expense__group=group):
        if share.user_id in member_ids:
            balance[share.user_id] -= share.amount

    for s in Settlement.objects.filter(group=group, is_done=True):
        if s.from_user_id in member_ids:
            balance[s.from_user_id] += s.amount
        if s.to_user_id in member_ids:
            balance[s.to_user_id] -= s.amount

    names = {u.pk: (u.first_name or u.username) for u in members}
    return [
        {'user_id': uid, 'name': names[uid], 'amount': amt}
        for uid, amt in balance.items()
    ]


def group_create(request):
    if request.method != 'POST':
        return redirect('shared')

    form = GroupForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Введи назву групи.')
        return redirect('shared')

    name = form.cleaned_data['name']
    existing = Group.objects.filter(owner=request.user, name=name).first()
    if existing:
        return redirect(f"{reverse('shared')}?group={existing.pk}")

    group = form.save(commit=False)
    group.owner = request.user
    group.save()
    Membership.objects.get_or_create(group=group, user=request.user)

    friend_id = request.POST.get('member_ids', '').strip()
    if friend_id.isdigit():
        friend = User.objects.filter(pk=int(friend_id)).first()
        if friend:
            Membership.objects.get_or_create(group=group, user=friend)

    return redirect(f"{reverse('shared')}?group={group.pk}")


def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk, owner=request.user)
    if request.method == 'POST':
        group.delete()
    return redirect('shared')


def message_create(request, pk):
    group = get_object_or_404(Group, pk=pk, memberships__user=request.user)
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        if text:
            GroupMessage.objects.create(group=group, author=request.user, text=text[:500])
    return redirect(f"{reverse('shared')}?group={group.pk}")


def expense_create(request, pk):
    group = get_object_or_404(Group, pk=pk, memberships__user=request.user)
    if request.method != 'POST':
        return redirect(f"{reverse('shared')}?group={group.pk}")

    form = SharedExpenseForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Перевір суму й заповни коментар, він обов'язковий.")
        return redirect(f"{reverse('shared')}?group={group.pk}")

    amount = form.cleaned_data['amount']
    if user_balance(request.user) <= 0:
        messages.error(request, 'Баланс нульовий, додати витрату не можна.')
        return redirect(f"{reverse('shared')}?group={group.pk}")
    if user_balance(request.user) < amount:
        messages.error(request, 'Недостатньо коштів: баланс не може піти в мінус.')
        return redirect(f"{reverse('shared')}?group={group.pk}")

    members = [m.user for m in group.memberships.select_related('user')]
    count = len(members)
    part = (amount / count).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    rest = amount - part * count

    expense = form.save(commit=False)
    expense.group = group
    expense.payer = request.user
    expense.save()

    for i, u in enumerate(members):
        Share.objects.create(
            expense=expense,
            user=u,
            amount=part + (rest if i == 0 else Decimal('0')),
        )

    Transaction.objects.create(
        user=request.user,
        type='expense',
        amount=amount,
        category='other',
        date=expense.date,
        comment=f'Спільний чек: {group.name} (оплачено за групу)',
    )

    messages.success(request, f'Витрату {amount} ₴ додано.')
    return redirect(f"{reverse('shared')}?group={group.pk}")


def settlement_done(request, pk):
    if request.method != 'POST':
        return redirect('shared')
    group = get_object_or_404(Group, pk=pk, memberships__user=request.user)
    shared_url = f"{reverse('shared')}?group={group.pk}"

    try:
        to_user = User.objects.get(pk=request.POST.get('to_id'))
        amount = Decimal(request.POST.get('amount', '0'))
    except (User.DoesNotExist, ValueError, InvalidOperation):
        messages.error(request, 'Не вдалося обробити переказ.')
        return redirect(shared_url)

    if amount <= 0 or not group.memberships.filter(user=to_user).exists():
        messages.error(request, 'Некоректний переказ.')
        return redirect(shared_url)

    my_balance = next(
        (b['amount'] for b in group_balances(group) if b['user_id'] == request.user.pk),
        Decimal('0'),
    )
    debt = -my_balance
    if debt <= 0:
        messages.error(request, 'У тебе немає боргу в цій групі.')
        return redirect(shared_url)
    if amount > debt:
        messages.error(request, f'Борг становить {debt} ₴, сума більша за борг.')
        return redirect(shared_url)

    if user_balance(request.user) < amount:
        messages.error(request, 'Недостатньо коштів на балансі, щоб сплатити борг.')
        return redirect(shared_url)

    Settlement.objects.create(
        group=group, from_user=request.user, to_user=to_user,
        amount=amount, is_done=True,
    )
    comment = f'Переказ у групі: {group.name}'
    Transaction.objects.create(
        user=request.user, type='expense', amount=amount,
        category='other', date=timezone.localdate(), comment=comment,
    )
    Transaction.objects.create(
        user=to_user, type='income', amount=amount,
        category='other', date=timezone.localdate(), comment=comment,
    )

    messages.success(request, f'Сплачено {amount} ₴.')
    return redirect(shared_url)

def group_add_member(request, pk):
    group = get_object_or_404(Group, pk=pk, owner=request.user)
    if request.method == 'POST':
        uid = request.POST.get('user_id', '').strip()
        if uid.isdigit():
            u = User.objects.filter(pk=int(uid)).first()
            if u:
                Membership.objects.get_or_create(group=group, user=u)
                messages.success(request, f'{u.username} додано до групи.')
    return redirect(f"{reverse('shared')}?group={group.pk}")


def group_remove_member(request, pk, user_pk):
    group = get_object_or_404(Group, pk=pk, owner=request.user)
    if request.method == 'POST' and user_pk != request.user.pk:
        Membership.objects.filter(group=group, user_id=user_pk).delete()
        messages.success(request, 'Учасника видалено з групи.')
    return redirect(f"{reverse('shared')}?group={group.pk}")

def goal_delete(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == 'POST':
        goal.delete()
    return redirect('goals')

def settings_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    pwd_form = PasswordChangeUAForm(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'profile':
            name = request.POST.get('first_name', '').strip()
            if not name:
                messages.error(request, "Вкажи ім'я.")
            else:
                request.user.first_name = name
                request.user.save()
                messages.success(request, f'Ім\'я змінено на «{name}».')

        elif action == 'theme':
            profile.theme = 'dark' if request.POST.get('theme') == 'dark' else 'light'
            profile.save()
            messages.success(request, 'Тему змінено.')

        elif action == 'password':
            pwd_form = PasswordChangeUAForm(request.user, request.POST)
            if pwd_form.is_valid():
                pwd_form.save()
                update_session_auth_hash(request, pwd_form.user)
                messages.success(request, 'Пароль успішно змінено.')
                pwd_form = PasswordChangeUAForm(request.user)

        return redirect('settings') if action != 'password' or pwd_form.is_bound is False else render(
            request, 'settings.html', {'profile': profile, 'pwd_form': pwd_form}
        )

    return render(request, 'settings.html', {'profile': profile, 'pwd_form': pwd_form})


import csv
from django.http import HttpResponse


def export_view(request):
    if request.method != 'POST':
        return render(request, 'export.html', {
            'tx_count': user_tx(request).count(),
            'group_count': Group.objects.filter(memberships__user=request.user).distinct().count(),
            'friend_count': FriendRequest.objects.filter(status='accepted').filter(
                Q(sender=request.user) | Q(receiver=request.user)
            ).count(),
        })

    period = request.POST.get('period', 'month')
    what = request.POST.getlist('what')
    formats = request.POST.getlist('format') or ['csv']
    today = timezone.localdate()

    tx = user_tx(request)
    shares = Share.objects.filter(user=request.user).select_related('expense__group', 'expense__payer')
    if period == 'month':
        tx = tx.filter(date__year=today.year, date__month=today.month)
        shares = shares.filter(expense__date__year=today.year, expense__date__month=today.month)

    sections = []
    if 'tx' in what:
        sections.append(('Транзакції', ['Дата', 'Тип', 'Категорія', 'Сума', 'Коментар'],
            [[t.date, t.get_type_display(), t.get_category_display(), float(t.amount), t.comment] for t in tx]))
    if 'shared' in what:
        sections.append(('Спільні чеки', ['Група', 'Дата', 'Платник', 'Коментар', 'Загальна сума', 'Моя частка'],
            [[s.expense.group.name, s.expense.date, s.expense.payer.username, s.expense.comment,
              float(s.expense.amount), float(s.amount)] for s in shares]))
    if 'limits' in what:
        sections.append(('Ліміти', ['Ліміт', 'Місяць', 'Сума'],
            [[l.get_category_display() if l.category else 'Загальний', l.month, float(l.amount)]
             for l in user_limits(request)]))
        sections.append(('Цілі', ['Ціль', 'Дедлайн', 'Накопичено', 'Сума цілі'],
            [[g.title, g.deadline, float(g.saved), float(g.target)] for g in user_goals(request)]))

    files = []

    if 'csv' in formats:
        buf = io.StringIO()
        buf.write('\ufeff')
        writer = csv.writer(buf, delimiter=';')
        for title, header, rows in sections:
            writer.writerow([title])
            writer.writerow(header)
            writer.writerows(rows)
            writer.writerow([])
        files.append(('bumfinance.csv', buf.getvalue().encode('utf-8')))

    if 'excel' in formats:
        wb = Workbook()
        wb.remove(wb.active)
        for title, header, rows in sections:
            ws = wb.create_sheet(title=title[:31])
            ws.append(header)
            for r in rows:
                ws.append(r)
        out = io.BytesIO()
        wb.save(out)
        files.append(('bumfinance.xlsx', out.getvalue()))

    if 'pdf' in formats:
        out = io.BytesIO()
        doc = SimpleDocTemplate(
            out, pagesize=landscape(A4),
            title='BumFinance: експорт даних',
            author='BumFinance',
            subject='Експорт транзакцій, спільних чеків, лімітів і цілей',
            creator='BumFinance',
        )
        base = getSampleStyleSheet()
        title_style = ParagraphStyle('UATitle', parent=base['Title'], fontName='DejaVu')
        head_style = ParagraphStyle('UAHead', parent=base['Heading2'], fontName='DejaVu')
        story = [Paragraph('BumFinance: експорт', title_style), Spacer(1, 12)]
        for title, header, rows in sections:
            story.append(Paragraph(title, head_style))
            data = [header] + [[str(c) for c in r] for r in rows]
            if len(data) == 1:
                data.append(['—'] * len(header))
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#CFE3F8')),
            ]))
            story += [table, Spacer(1, 18)]
        doc.build(story)
        files.append(('bumfinance.pdf', out.getvalue()))

    if not files:
        return redirect('export')

    if len(files) == 1:
        name, data = files[0]
        ctype = {
            'csv': 'text/csv; charset=utf-8',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pdf': 'application/pdf',
        }[name.rsplit('.', 1)[1]]
        response = HttpResponse(data, content_type=ctype)
        response['Content-Disposition'] = f'attachment; filename="{name}"'
        return response

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files:
            z.writestr(name, data)
    response = HttpResponse(zbuf.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="bumfinance_export.zip"'
    return response


def transactions_clear(request):
    if request.method == 'POST':
        user_tx(request).delete()
        messages.success(request, 'Транзакції очищено.')
    return redirect('transactions')


def limits_clear(request):
    if request.method == 'POST':
        user_limits(request).delete()
        messages.success(request, 'Ліміти очищено.')
    return redirect('limits')


def goals_clear(request):
    if request.method == 'POST':
        user_goals(request).delete()
        messages.success(request, 'Цілі очищено.')
    return redirect('goals')