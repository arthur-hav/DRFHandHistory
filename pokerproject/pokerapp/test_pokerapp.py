from pytest import fixture
from django.test import Client
from pokerapp.models import HandHistory
from pokerapp.views import HandHistoryViewSet
from django.contrib.auth.models import User


@fixture
def login(transactional_db):
    new_user = User.objects.create_user('test_user', 'someemail@somehost.org', 'password')
    client = Client()
    client.force_login(new_user)
    return client


class TestPokerApp:
    fixture = ['login']

    def test_hand_history_get(self, login):
        hh = login.get('/hand_history/')
        assert hh.json() == {'count': 0, 'next': None, 'previous': None, 'results': []}