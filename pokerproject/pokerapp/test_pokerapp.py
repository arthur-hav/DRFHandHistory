import pytest
from freezegun import freeze_time
from django.test import Client
from pokerapp.models import HandHistory, Player, Seat, Action, Street
from pokerapp.views import HandHistoryViewSet
from django.contrib.auth.models import User


@pytest.fixture
def login(transactional_db):
    new_user = User.objects.create_user('test_user', 'someemail@somehost.org', 'password')
    client = Client()
    client.force_login(new_user)
    return client


@pytest.fixture
def insert_data():
    def insert(model, data):
        obj = model.objects.create(**data)
        obj.save()
        return obj
    return insert


class TestPokerApp:
    fixture = ['login']
    test_player = {'name': 'Test Player'}
    test_seat = {'chips': 2000, 'seat': 0}
    test_action = {'action': 0, 'amount': 100, 'sequence_no': 1}
    test_street = {'name': 0, 'cards': None}
    test_street_nested = {'name': 0, 'actions': [{'player': 'Test Player',
                                                  'action': 'Blind',
                                                  'amount': 100,
                                                  'sequence_no': 1}],}

    @pytest.fixture
    def setup_test_data(self, insert_data):
        self.player = insert_data(Player, self.test_player)
        self.hh = insert_data(HandHistory, {})
        self.seat = insert_data(Seat, dict(player=self.player, hand_history=self.hh, **self.test_seat))
        self.street = insert_data(Street, dict(hand_history=self.hh, **self.test_street))
        self.action = insert_data(Action, dict(player=self.player, street=self.street, **self.test_action))

    @pytest.mark.freeze_time('1999-12-31')
    def test_hand_history_single_get(self, login, setup_test_data):
        hh_data = login.get(f'/hand_history/{self.hh.id}/', content_type='application/json').json()

        assert 'date_played' in hh_data
        assert hh_data['date_played'] == '1999-12-31T00:00:00Z'
        assert 'id' in hh_data
        assert hh_data['id'] == self.hh.id
        assert 'seats' in hh_data
        assert hh_data['seats'] == [{'chips': 2000, 'seat': 'BB', 'player': 'Test Player', 'id': self.seat.id}]
        assert 'streets' in hh_data
        assert len(hh_data['streets']) == 1
        street = hh_data['streets'][0]
        assert street['cards'] is None
        assert street['actions'] == [{'action': 'Blind',
                                      'amount': 100,
                                      'player': 'Test Player',
                                      'sequence_no': 1,
                                      'id': self.action.id}]
        assert 'url' in hh_data

    @pytest.mark.parametrize("model,url,num_keys",
                             [(HandHistory, '/hand_history/', 5),
                              (Player, '/players/', 4),
                              (Seat, '/seats/', 6),
                              (Action, '/actions/', 7),
                              (Street, '/streets/', 6)])
    def test_list_get(self, login, model, url, num_keys, setup_test_data):
        data = login.get(url, content_type='application/json').json()
        assert {'count', 'next', 'previous'}.issubset(data.keys())
        assert 1 == data['count']
        assert 1 == len(data['results'])
        assert len(data['results'][0]) == num_keys

    def test_insert_cascade_street(self, login, insert_data):
        player = insert_data(Player, self.test_player)
        hh = insert_data(HandHistory, {})

        street = login.post('/streets/', data=dict(hand_history=hh.id, **self.test_street_nested),
                            content_type='application/json')
        assert street.status_code == 201
        assert len(list(Action.objects.all())) == 1
        assert len(list(Street.objects.all())) == 1
        action = next(iter(Action.objects.all()))
        street = next(iter(Street.objects.all()))
        assert action.street == street.id
        assert action.player == player.id
