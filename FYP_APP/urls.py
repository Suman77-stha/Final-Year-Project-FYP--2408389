from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('Sign_Up/', views.SignUp_View, name='Sign_Up'),
    path('Sign_In/', views.Sign_In_view, name='Sign_In'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('', views.landing_page_view, name='Home'),
    path('About/', views.about_view, name='About'),
    path('wallet/', views.wallet_view, name='wallet'),
    path("get-live-price/", views.get_live_price, name="get_live_price"),
    path('AI_Assistance/', views.AI_Assistance_view, name='AI_Assistance'),
    path('api/stock-prediction/', views.stock_prediction_api, name='stock_prediction_api'),
    path("api/profit-loss/", views.profit_loss_api, name="profit_loss_api"),
    path('trading_bot/', views.trading_bot_view, name='trading_bot'),
    path("api/stock_6month_api/",views.stock_6month_api,name="stock_6month_api"),

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
