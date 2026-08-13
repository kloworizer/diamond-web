import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'diamond_web.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from diamond_web.models import Tiket, TiketPIC

User = get_user_model()
client = Client()
user = User.objects.first() # just get the first user
client.force_login(user)
tiket = Tiket.objects.filter(status_tiket=8).first() # STATUS_DIREKAM
if tiket:
    response = client.get(f'/tanda-terima-data/from-tiket/{tiket.pk}/create/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    print(f"User: {user.username}, Groups: {list(user.groups.values_list('name', flat=True))}")
    print(f"Tiket: {tiket.pk}")
    print(f"Response status: {response.status_code}")
    if response.status_code != 200:
        print(response.content)
else:
    print("No tiket found")
