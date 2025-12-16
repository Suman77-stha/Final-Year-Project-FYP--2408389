from django.urls import path
from . import views

urlpatterns = [
    path('Sign_Up/',views.SignUp_View,name='Sign_Up'),
    path('Sign_In/',views.Sign_In_view,name='Sign_In'),
    path('logout/',views.logout_view,name='logout'),
    path('dashboard/',views.dashboard_view,name='dashboard'),
    path('stock/',views.stock,name='stock')
]