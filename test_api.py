import os
import django
import sys

# Setup Django environment
sys.path.append('C:\\Users\\Dell\\Desktop\\Final_Year_Project_Suman_Shrestha\\FYP')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FYP.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
sys.path.append('C:\\Users\\Dell\\Desktop\\Final_Year_Project_Suman_Shrestha\\FYP')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FYP.settings')
django.setup()

from FYP_APP.views import watchlist_ai_api

factory = RequestFactory()
request = factory.get('/FYP/api/watchlist-ai/')
# Assign the first user to the request
user = User.objects.first()
request.user = user

response = watchlist_ai_api(request)
print("Status Code:", response.status_code)
print("Content:", response.content.decode('utf-8'))
