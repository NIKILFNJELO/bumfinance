from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from core import views as core_views

from core.forms import LoginForm, PasswordResetUAForm, SetPasswordUAForm

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html', authentication_form=LoginForm), name='login'),
    path('accounts/password_reset/', core_views.DemoPasswordResetView.as_view(template_name='registration/reset_request_ua.html', email_template_name='registration/password_reset_email.txt', subject_template_name='registration/password_reset_subject.txt', form_class=PasswordResetUAForm, success_url='/accounts/password_reset/done/'), name='password_reset'),    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/reset_sent_ua.html'), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/reset_confirm_ua.html', form_class=SetPasswordUAForm, success_url='/accounts/reset/done/'), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/reset_done_ua.html'), name='password_reset_complete'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('core.urls')),
]