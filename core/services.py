from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import (
    Membership, SharedExpense, Share, Settlement,
    Transaction, Limit, Goal, Notification,
)


def group_balances(group):
    """Сальдо кожного учасника: + йому винні, − він винен."""
    members = [m.user for m in Membership.objects.filter(group=group).select_related('user')]
    member_ids = {u.pk for u in members}
    balance = {u.pk: Decimal('0') for u in members}

    for exp in SharedExpense.objects.filter(group=group):
        if exp.payer_id in member_ids:
            balance[exp.payer_id] += exp.amount
    for share in Share.objects.filter(expense__group=group):
        if share.user_id in member_ids:
            balance[share.user_id] -= share.amount

    # виконані перекази: боржник оплатив, тому його сальдо росте
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


def min_settlements(balances):
    """Хто кому має заплатити, щоб усі розрахувались (найменше переказів)."""
    debtors = [[b['user_id'], -b['amount']] for b in balances if b['amount'] < 0]
    creditors = [[b['user_id'], b['amount']] for b in balances if b['amount'] > 0]
    names = {b['user_id']: b['name'] for b in balances}

    result = []
    debtors.sort(key=lambda x: -x[1])
    creditors.sort(key=lambda x: -x[1])
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        d_id, d_amt = debtors[i]
        c_id, c_amt = creditors[j]
        pay = min(d_amt, c_amt)
        result.append({
            'from': names[d_id], 'to': names[c_id], 'amount': pay,
            'from_id': d_id, 'to_id': c_id,
        })
        debtors[i][1] -= pay
        creditors[j][1] -= pay
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return result


def check_notifications(user):
    """Створює сповіщення про ліміти і цілі, якщо їх ще немає."""
    today = timezone.localdate()
    spent_qs = Transaction.objects.filter(
        user=user, type='expense', date__year=today.year, date__month=today.month,
    )
    for lim in Limit.objects.filter(user=user, month__year=today.year, month__month=today.month):
        if lim.category:
            spent = spent_qs.filter(category=lim.category).aggregate(s=Sum('amount'))['s'] or 0
            name = lim.get_category_display()
        else:
            spent = spent_qs.aggregate(s=Sum('amount'))['s'] or 0
            name = 'Загальний ліміт'
        pct = int(spent / lim.amount * 100) if lim.amount else 0
        if pct > 100:
            kind, title = 'limit_over', 'Ліміт перевищено'
        elif pct >= 80:
            kind, title = 'limit_near', 'Наближення до ліміту'
        else:
            continue
        text = f'{name}: {spent} з {lim.amount} ₴ ({pct}%)'
        Notification.objects.get_or_create(
            user=user, kind=kind, text=text, defaults={'title': title},
        )

    for g in Goal.objects.filter(user=user):
        if g.is_closed:
            text = f'{g.title}: {g.saved} ₴ з {g.target} ₴'
            Notification.objects.get_or_create(
                user=user, kind='goal_done', text=text,
                defaults={'title': 'Ціль досягнута'},
            )

def unique_group_name(owner, base):
    """Повертає назву, якої ще немає у власника: «Велосипед», «Велосипед 2», ..."""
    from .models import Group
    name = base.strip()
    if not Group.objects.filter(owner=owner, name=name).exists():
        return name
    n = 2
    while Group.objects.filter(owner=owner, name=f'{name} {n}').exists():
        n += 1
    return f'{name} {n}'


def notify_group_event(users, text, title='Подія в групі', kind='group_event'):
    """Створює сповіщення для кожного з учасників."""
    from .models import Notification
    for u in users:
        Notification.objects.create(user=u, kind=kind, title=title, text=text)