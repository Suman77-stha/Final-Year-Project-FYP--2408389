from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('Sign_Up/',views.SignUp_View,name='Sign_Up'),
    path('Sign_In/',views.Sign_In_view,name='Sign_In'),
    path('logout/',views.logout_view,name='logout'),
    path('dashboard/',views.dashboard_view,name='dashboard'),
    path('stock/',views.stock,name='stock'),
    #password reset urls through django
     path('password-reset/', auth_views.PasswordResetView.as_view(template_name='forgetPassword.html'), name='Forget_Password'),
     path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'),
         name='password_reset_complete'),


]