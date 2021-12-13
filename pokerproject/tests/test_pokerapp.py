"""Testing philosophical design revolves around testing the smallest possible units at once, while retaining a great
overall test coverage (we expect to see no less than 80-90% in production code).

It is also favored that tests contain the least possible complex logic as we would prefer to avoid having to reverse
engineer them or find bugs in them.

As a result, the number of test is typically big, and sometimes redundant, which is not considered an engineering
problem or priority."""

import pytest
from freezegun import freeze_time
from django.test import Client
from pokerapp.models import HandHistory, Player, Seat, Action, Street, AbstractRedisStat
from django.contrib.auth.models import User
from unittest import mock


@pytest.fixture
def mock_redis():
    patched_cursor = mock.MagicMock()
    patched_cursor.get.return_value = 666
    patched_redis = mock.MagicMock()
    patched_redis.return_value = patched_cursor
    with mock.patch('redis.Redis', patched_redis):
        yield patched_redis, patched_cursor


@pytest.fixture()
def fake_reset_hands_played():
    with mock.patch.object(AbstractRedisStat, 'reset',
                           side_effect=Exception('Unnecessary call to underlying reset method')) as fake_method:
        yield fake_method


@pytest.fixture
def login(transactional_db, mock_redis):
    new_user = User.objects.create_user('test_user', 'someemail@somehost.org', 'password')
    client = Client()
    client.force_login(new_user)
    return client


test_player = {'name': 'Test Player'}
test_seat = {'chips': 2000, 'seat': 0}
test_action = {'action': 0, 'amount': 100, 'sequence_no': 1}
test_street = {'name': 0, 'cards': None}

post_player = {'name': 'Other Player'}
post_seat = {'chips': 2000, 'seat': 0, 'player': 'Test Player'}
post_action = {'action': 0, 'amount': 200, 'sequence_no': 2, 'player': 'Test Player'}
post_street = {'name': 0, 'cards': None}

append_action = {'action': 0, 'amount': 200, 'player': 'Test Player'}

post_seat_missing = {'seat': 0, 'player': 'Test Player'}
post_action_missing = test_action
post_street_missing = {'cards': None}

test_street_nested = {'name': 0, 'actions': [{'player': 'Test Player',
                                              'action': 'Blind',
                                              'amount': 100}]}
test_hh_full = {
    "date_played": "2021-12-11T10:55:32.149294Z",
    "streets": [
        {
            "id": 2,
            "name": "Preflop",
            "actions": [
                {
                    "action": "Blind",
                    "player": "Dom Twan",
                    "amount": 5
                    },
                {
                    "action": "Blind",
                    "player": "Antrick Patonius",
                    "amount": 10
                    }
                ],
            "cards": None
            }
        ],
    "seats": [
        {
            "player": "Dom Twan",
            "seat": "SB",
            "chips": 333
            },
        {
            "player": "Antrick Patonius",
            "seat": "BB",
            "chips": 444
            }
        ]
    }


@pytest.mark.freeze_time('1999-12-31')
class TestPokerApp:
    fixture = ['login']

    @pytest.fixture
    def setup_test_data(self):
        self.player = Player.objects.create(**test_player)
        self.hh = HandHistory.objects.create()
        self.seat = Seat.objects.create(**dict(player=self.player, hand_history=self.hh, **test_seat))
        self.street = Street.objects.create(**dict(hand_history=self.hh, **test_street))
        self.action = Action.objects.create(**dict(player=self.player, street=self.street, **test_action))

    def test_hand_history_single_get(self, login, setup_test_data):
        hh_data = login.get(f'/hand_history/{self.hh.id}/', content_type='application/json').json()

        assert 'date_played' in hh_data
        assert hh_data['date_played'] == '1999-12-31T00:00:00Z'
        assert 'id' in hh_data
        assert hh_data['id'] == self.hh.id
        assert 'seats' in hh_data
        assert hh_data['seats'] == [{'chips': 2000,
                                     'seat': 'BB',
                                     'player': 'Test Player',
                                     'url': 'http://testserver/seats/1/',
                                     'id': self.seat.id}]
        assert 'streets' in hh_data
        assert len(hh_data['streets']) == 1
        street = hh_data['streets'][0]
        assert street['cards'] is None
        assert street['actions'] == [{'action': 'Blind',
                                      'amount': 100,
                                      'player': 'Test Player',
                                      'sequence_no': 1,
                                      'url': 'http://testserver/actions/1/',
                                      'id': self.action.id}]
        assert 'url' in hh_data

    def test_list_get_hand_history(self, login, setup_test_data):
        data = login.get('/hand_history/', content_type='application/json').json()
        assert {'count', 'next', 'previous'}.issubset(data.keys())
        assert data['count'] == 1
        assert len(data['results']) == 1
        assert data['results'][0]['date_played'] == '1999-12-31T00:00:00Z'

    def test_list_get_player(self, fake_reset_hands_played, login, setup_test_data):
        data = login.get('/players/', content_type='application/json').json()
        assert {'count', 'next', 'previous'}.issubset(data.keys())
        assert data['count'] == 1
        assert len(data['results']) == 1
        assert data['results'][0]['hands_played'] == 666

    def test_hand_count_invalide_cache(self, mock_redis, login, setup_test_data):
        fake_redis, fake_cursor = mock_redis
        fake_cursor.get.return_value = None
        data = login.get('/players/', content_type='application/json').json()
        assert data['results'][0]['hands_played'] == 1
        assert data['results'][0]['vpip'] == 0
        assert mock.call(f'hands.{self.player.id}', 1) in fake_cursor.set.call_args_list
        assert mock.call(f'vpip.{self.player.id}', 0) in fake_cursor.set.call_args_list

    def test_increment_hand_count_cache(self, mock_redis, fake_reset_hands_played, login, setup_test_data):
        fake_redis, fake_cursor = mock_redis
        new_hh = HandHistory.objects.create()
        new_seat = Seat.objects.create(hand_history=new_hh, player=self.player, **test_seat)
        data = login.get('/players/', content_type='application/json').json()
        assert data['results'][0]['hands_played'] == 666
        assert mock.call(f'hands.{self.player.id}') in fake_cursor.incr.call_args_list
        assert mock.call(f'vpip.{self.player.id}') not in fake_cursor.incr.call_args_list

    def test_list_get_seat(self, login, setup_test_data):
        data = login.get('/seats/', content_type='application/json').json()
        assert {'count', 'next', 'previous'}.issubset(data.keys())
        assert data['count'] == 1
        assert len(data['results']) == 1
        assert {'seat', 'chips', 'player', 'id', 'url'}.issubset(set(data['results'][0].keys()))

    def test_list_get_action(self, login, setup_test_data):
        data = login.get('/actions/', content_type='application/json').json()
        assert {'count', 'next', 'previous'}.issubset(data.keys())
        assert data['count'] == 1
        assert len(data['results']) == 1
        assert {'action', 'amount', 'sequence_no', 'player', 'id', 'url'}.issubset(set(data['results'][0].keys()))

    def test_list_get_street(self, login, setup_test_data):
        data = login.get('/streets/', content_type='application/json').json()
        assert {'count', 'next', 'previous'}.issubset(data.keys())
        assert data['count'] == 1
        assert len(data['results']) == 1
        assert len(data['results'][0]['actions']) == 1

    @pytest.mark.parametrize("model,post_data,url,num_keys,test_data",
                             [(HandHistory, {}, '/hand_history/', 5, {}),
                              (Player, post_player, '/players/', 5, {}),
                              (Seat, post_seat, '/seats/', 6, {'hand_history': 'hh'}),
                              (Action, post_action, '/actions/', 7, {'street': 'street'}),
                              (Street, post_street, '/streets/', 6, {'hand_history': 'hh'})])
    def test_single_post(self, login, model, post_data, url, num_keys, test_data, setup_test_data):
        post_data = post_data
        for k, v in test_data.items():
            post_data[k] = getattr(self, v).id
        data = login.post(url, content_type='application/json', data=post_data).json()
        assert len(list(model.objects.all())) == 2
        db_data = model.objects.get(pk=data['id'])
        assert len(data.keys()) == num_keys

    def test_street_cascade_post(self, login):
        player = Player.objects.create(**test_player)
        hh = HandHistory.objects.create()

        street = login.post('/streets/', data=dict(hand_history=hh.id, **test_street_nested),
                            content_type='application/json')

        assert street.status_code == 201
        assert len(list(Action.objects.all())) == 1
        assert len(list(Street.objects.all())) == 1
        action = next(iter(Action.objects.all()))
        street = next(iter(Street.objects.all()))
        assert action.street_id == street.id
        assert action.player_id == player.id

    def test_playerhand_view(self, login):
        player1 = Player.objects.create(**test_player)
        player2 = Player.objects.create(name='player2')
        hh1 = HandHistory.objects.create()
        hh2 = HandHistory.objects.create()
        Seat.objects.create(**dict(player=player1, hand_history=hh1, **test_seat))
        Seat.objects.create(**dict(player=player2, hand_history=hh2, **test_seat))

        data = login.get('/player_hands/player2/', content_type='application/json').json()
        assert data == {'player2': [f'http://testserver/hand_history/{hh2.id}/']}

    def test_hand_history_cascade_post(self, login):
        player = Player.objects.create(**test_player)

        hh = login.post('/hand_history/', data=test_hh_full, content_type='application/json')

        assert hh.status_code == 201
        assert len(list(Action.objects.all())) == 2
        assert len(list(Street.objects.all())) == 1
        assert len(list(Seat.objects.all())) == 2

    def test_validator_append_action(self, login, setup_test_data):
        response = login.post('/actions/', data=dict(street=self.street.id, **append_action),
                              content_type='application/json')
        assert response.status_code == 201
        assert len(list(Action.objects.all())) == 2
        assert response.json()['sequence_no'] == 2

    def test_validator_400_action(self, login, setup_test_data):
        response = login.post('/actions/', data=dict(street=self.street.id, sequence_no=1, **append_action),
                              content_type='application/json')
        assert response.status_code == 400
        assert len(list(Action.objects.all())) == 1
        assert 'sequence_no' in response.json()['non_field_errors']

    @pytest.mark.parametrize("post_data,missing_key,url",
                             [(post_seat_missing, 'chips', '/seats/'),
                              (post_action_missing, 'player', '/actions/'),
                              (post_street_missing, 'name', '/streets/')])
    def test_400_field_required(self, login, post_data, missing_key, url):
        response = login.post(url, content_type='application/json', data=post_data)
        assert response.status_code == 400
        assert len(list(Action.objects.all())) == 0
        assert len(list(Street.objects.all())) == 0
        assert len(list(Seat.objects.all())) == 0
        assert missing_key in response.json()
