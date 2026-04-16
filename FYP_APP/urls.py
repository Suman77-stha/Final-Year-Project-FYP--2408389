from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('Sign_Up/', views.SignUp_View, name='Sign_Up'),
    path('verify-signup-otp/', views.verify_signup_otp, name='verify_signup_otp'),
    path('Sign_In/', views.Sign_In_view, name='Sign_In'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('', views.landing_page_view, name='Home'),
    path('About/', views.about_view, name='About'),
    path('wallet/', views.wallet_view, name='wallet'),
    path('profile/', views.user_profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),
    path("get-live-price/", views.get_live_price, name="get_live_price"),
    path('AI_Assistance/', views.AI_Assistance_view, name='AI_Assistance'),
    path('api/stock-prediction/', views.stock_prediction_api, name='stock_prediction_api'),
    path('api/wallet-top5-donut/', views.wallet_top5_donut_api, name='wallet_top5_donut_api'),
    path('trading_bot/', views.trading_bot_view, name='trading_bot'),
    path("api/stock_6month_api/",views.stock_6month_api,name="stock_6month_api"),
    path('chatbot/', views.Ai_Assistance_view, name='chatbot'),
    path('chatbot/clear/', views.clear_chat, name='clear_chat'),
    path('forgot_password/', views.forgot_password, name='forgot_password'),
    path('password_reset_done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='password_reset_done.html'
         ),
         name='password_reset_done'),
    path(
        'password-reset-confirm/<str:user>/',
        views.password_reset_confirm,
        name='password_reset_confirm'
    ),
    path(
        'password_reset_complete/',
        views.password_reset_complete_view,
        name='password_reset_complete'
    ),
]
