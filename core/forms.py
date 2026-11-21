from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Transaction, Limit, Goal, Group, SharedExpense


INPUT_CLASS = 'w-full mt-1 border border-brand-200 rounded-xl px-4 py-3 focus:outline-none focus:border-brand-500'


class StyledFormMixin:
    def style_fields(self):
        for f in self.fields.values():
            f.widget.attrs.setdefault('class', INPUT_CLASS)
            if f.label is None:
                f.label = ''


class TransactionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['type', 'amount', 'category', 'date', 'comment']
        labels = {
            'type': 'Тип',
            'amount': 'Сума, ₴',
            'category': 'Категорія',
            'date': 'Дата',
            'comment': 'Коментар',
        }
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01'}),
            'comment': forms.TextInput(attrs={'placeholder': "Необов'язково"}),
        }
        error_messages = {
            'amount': {'required': 'Вкажи суму', 'invalid': 'Сума має бути числом'},
            'date': {'required': 'Вкажи дату', 'invalid': 'Некоректна дата'},
            'category': {'required': 'Обери категорію'},
            'type': {'required': 'Обери тип операції'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields['type'].choices = [('expense', 'Витрата'), ('income', 'Дохід')]

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('Сума має бути більшою за нуль')
        return amount


class LimitForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Limit
        fields = ['category', 'amount', 'month']
        labels = {
            'category': 'Категорія (порожньо — загальний ліміт)',
            'amount': 'Сума ліміту, ₴',
            'month': 'Місяць',
        }
        widgets = {
            'month': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01'}),
        }
        error_messages = {
            'amount': {'required': 'Вкажи суму ліміту', 'invalid': 'Сума має бути числом'},
            'month': {'required': 'Вкажи місяць', 'invalid': 'Некоректна дата'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('Ліміт має бути більшим за нуль')
        return amount


class GoalForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Goal
        fields = ['title', 'target', 'deadline']
        labels = {
            'title': 'Назва цілі',
            'target': 'Сума цілі, ₴',
            'deadline': 'Дедлайн',
        }
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'title': forms.TextInput(attrs={'placeholder': 'Наприклад, Ноутбук'}),
            'target': forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01'}),
        }
        error_messages = {
            'title': {'required': 'Вкажи назву цілі'},
            'target': {'required': 'Вкажи суму цілі', 'invalid': 'Сума має бути числом'},
            'deadline': {'required': 'Вкажи дедлайн', 'invalid': 'Некоректна дата'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean_target(self):
        target = self.cleaned_data['target']
        if target <= 0:
            raise forms.ValidationError('Сума цілі має бути більшою за нуль')
        return target


class SignUpForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(
        required=True,
        label='Email',
        error_messages={'required': 'Вкажи email', 'invalid': 'Некоректний email'},
    )
    first_name = forms.CharField(required=False, label="Ім'я")
    last_name = forms.CharField(required=False, label='Прізвище')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        labels = {'username': "Ім'я користувача"}
        error_messages = {
            'username': {'required': "Вкажи ім'я користувача", 'unique': 'Такий користувач уже є'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = 'Пароль'
        self.fields['password2'].label = 'Підтвердження пароля'
        self.fields['password1'].error_messages = {'required': 'Вкажи пароль'}
        self.fields['password2'].error_messages = {'required': 'Підтверди пароль'}
        self.style_fields()


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Ім'я користувача",
        error_messages={'required': "Вкажи ім'я користувача"},
        widget=forms.TextInput(attrs={'autofocus': True, 'class': INPUT_CLASS}),
    )
    password = forms.CharField(
        label='Пароль',
        strip=False,
        error_messages={'required': 'Вкажи пароль'},
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS}),
    )
    error_messages = {
        'invalid_login': "Неправильне ім'я користувача або пароль",
        'inactive': 'Акаунт вимкнено',
    }


class GroupForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']
        labels = {'name': 'Назва групи'}
        widgets = {'name': forms.TextInput(attrs={'placeholder': 'Назва групи'})}
        error_messages = {'name': {'required': 'Вкажи назву групи'}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class SharedExpenseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SharedExpense
        fields = ['amount', 'comment', 'date']
        labels = {'amount': 'Сума, ₴', 'comment': 'Коментар', 'date': 'Дата'}
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'placeholder': 'Сума, ₴', 'step': '0.01'}),
            'comment': forms.TextInput(attrs={'placeholder': "Коментар (обов'язково)"}),
        }
        error_messages = {
            'amount': {'required': 'Вкажи суму', 'invalid': 'Сума має бути числом'},
            'comment': {'required': "Коментар обов'язковий"},
            'date': {'required': 'Вкажи дату', 'invalid': 'Некоректна дата'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['comment'].required = True
        self.style_fields()

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('Сума має бути більшою за нуль')
        return amount


class PasswordChangeUAForm(PasswordChangeForm):
    old_password = forms.CharField(
        label='Поточний пароль',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS}),
        error_messages={'required': 'Введи поточний пароль'},
    )
    new_password1 = forms.CharField(
        label='Новий пароль',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS}),
        error_messages={'required': 'Введи новий пароль'},
    )
    new_password2 = forms.CharField(
        label='Підтвердження нового пароля',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS}),
        error_messages={'required': 'Підтверди новий пароль'},
    )
    error_messages = {
        'password_mismatch': 'Паролі не збігаються',
        'password_incorrect': 'Поточний пароль введено неправильно',
    }


class PasswordResetUAForm(PasswordResetForm):
    email = forms.EmailField(
        label='Email',
        error_messages={
            'required': 'Введи email',
            'invalid': 'Введи коректний email, наприклад name@gmail.com',
        },
        widget=forms.EmailInput(attrs={'class': INPUT_CLASS, 'autofocus': True}),
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        if not User.objects.filter(email__iexact=email, is_active=True).exists():
            raise forms.ValidationError('Такої адреси не знайдено. Перевір написання або зареєструйся.')
        return email

    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        from django.conf import settings
        link = f"{settings.SITE_URL}/accounts/reset/{context['uid']}/{context['token']}/"
        self.demo_link = link


class SetPasswordUAForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label='Новий пароль',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS}),
        error_messages={'required': 'Введи новий пароль'},
    )
    new_password2 = forms.CharField(
        label='Повтор пароля',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS}),
        error_messages={'required': 'Повтори новий пароль'},
    )
    error_messages = {
        'password_mismatch': 'Паролі не збігаються',
    }

    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError('Паролі не збігаються')
        try:
            validate_password(password2, self.user)
        except ValidationError as e:
            raise ValidationError([self._uk(m) for m in e.messages])
        return password2

    @staticmethod
    def _uk(msg):
        if 'too short' in msg:
            return 'Пароль занадто короткий, потрібно щонайменше 8 символів'
        if 'too common' in msg:
            return 'Цей пароль занадто простий'
        if 'entirely numeric' in msg:
            return 'Пароль не може складатися лише з цифр'
        if 'too similar' in msg:
            return 'Пароль занадто схожий на твої дані'
        return msg