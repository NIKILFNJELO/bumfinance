from django.db import models
from django.contrib.auth.models import User


class Transaction(models.Model):
    TYPE_CHOICES = [('expense', 'Витрата'), ('income', 'Дохід')]
    CATEGORY_CHOICES = [
        ('food', 'Продукти'),
        ('transport', 'Транспорт'),
        ('health', 'Здоров\'я'),
        ('fun', 'Розваги'),
        ('home', 'Дім і комуналка'),
        ('other', 'Інше'),
        ('salary', 'Зарплата'),
        ('scholarship', 'Стипендія'),
        ('freelance', 'Підробіток'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
    type = models.CharField(max_length=7, choices=TYPE_CHOICES, default='expense')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    date = models.DateField()
    comment = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.get_type_display()} {self.amount} {self.get_category_display()}'


class Limit(models.Model):
    category = models.CharField(max_length=20, choices=Transaction.CATEGORY_CHOICES, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    month = models.DateField(help_text='Перше число місяця')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='limits', null=True, blank=True)


    class Meta:
        ordering = ['category']

    def __str__(self):
        name = self.get_category_display() if self.category else 'Загальний'
        return f'{name}: {self.amount}'


class Goal(models.Model):
    title = models.CharField(max_length=100)
    target = models.DecimalField(max_digits=10, decimal_places=2)
    saved = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deadline = models.DateField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='goals', null=True, blank=True)

    class Meta:
        ordering = ['deadline']

    def __str__(self):
        return self.title

    @property
    def percent(self):
        return min(int(self.saved / self.target * 100), 100) if self.target else 0

    @property
    def left(self):
        return max(self.target - self.saved, 0)

    @property
    def is_closed(self):
        return self.saved >= self.target


class Group(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='unique_group_name_per_owner'),
        ]

    def __str__(self):
        return self.name


class Membership(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'user')

    def __str__(self):
        return f'{self.user.username} в {self.group.name}'


class SharedExpense(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='expenses')
    payer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paid_expenses')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    comment = models.CharField(max_length=200, blank=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.group.name}: {self.amount} ({self.comment})'


class Share(models.Model):
    expense = models.ForeignKey(SharedExpense, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shares')
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'{self.user.username}: {self.amount}'


class Settlement(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='settlements')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='outgoing_settlements')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='incoming_settlements')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_done = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.from_user.username} → {self.to_user.username}: {self.amount}'


class FriendRequest(models.Model):
    STATUS = [('pending', 'Очікує'), ('accepted', 'Прийнято')]
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_requests')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_requests')
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f'{self.sender.username} → {self.receiver.username} ({self.status})'

class GroupMessage(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_messages')
    text = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

class GroupRead(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_reads')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='reads')
    last_seen = models.DateTimeField()

    class Meta:
        unique_together = ('user', 'group')

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=20)
    title = models.CharField(max_length=100)
    text = models.CharField(max_length=300)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Meta:
    ordering = ['-created_at']

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    theme = models.CharField(max_length=5, choices=[('light', 'Світла'), ('dark', 'Темна')], default='light')