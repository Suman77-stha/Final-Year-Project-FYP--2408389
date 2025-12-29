from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('Sign_Up/',views.SignUp_View,name='Sign_Up'),
    path('Sign_In/',views.Sign_In_view,name='Sign_In'),
    path('logout/',views.logout_view,name='logout'),
    path('dashboard/',views.dashboard_view,name='dashboard'),

    # Password reset URLs
    path(    'password_reset_done/',auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('forgot_password/', views.forgot_password, name='forgot_password'),
    # path('password_reset_done/', views.password_Reset_Done_View, name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password_reset_complete/', views.password_reset_complete_view, name='password_reset_complete'),

]