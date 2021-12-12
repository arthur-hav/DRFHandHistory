import pytest
from freezegun import freeze_time
from django.test import Client
from pokerapp.models import HandHistory, Player, Seat, Action, Street
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


test_player = {'name': 'Test Player'}
test_seat = {'chips': 2000, 'seat': 0}
test_action = {'action': 0, 'amount': 100, 'sequence_no': 1}
test_street = {'name': 0, 'cards': None}

post_player = test_player
post_seat = {'chips': 2000, 'seat': 0, 'player': 'Test Player'}
post_action = {'action': 0, 'amount': 100, 'sequence_no': 1, 'player': 'Test Player'}
post_street = {'name': 0, 'cards': None}

post_seat_missing = {'seat': 0, 'player': 'Test Player'}
post_action_missing = test_action
post_street_missing = {'cards': None}

test_street_nested = {'name': 0, 'actions': [{'player': 'Test Player',
                                              'action': 'Blind',
                                              'amount': 100,
                                              'sequence_no': 1}]}
test_hh_full = {
    "date_played": "2021-12-11T10:55:32.149294Z",
    "streets": [
        {
            "id": 2,
            "name": "Preflop",
            "actions": [
                {
                    "action": "Blind",
                    "sequence_no": 1,
                    "player": "Dom Twan",
                    "amount": 5
                    },
                {
                    "action": "Blind",
                    "sequence_no": 2,
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


class TestPokerApp:
    fixture = ['login']

    @pytest.fixture
    def setup_test_data(self, insert_data):
        self.player = insert_data(Player, test_player)
        self.hh = insert_data(HandHistory, {})
        self.seat = insert_data(Seat, dict(player=self.player, hand_history=self.hh, **test_seat))
        self.street = insert_data(Street, dict(hand_history=self.hh, **test_street))
        self.action = insert_data(Action, dict(player=self.player, street=self.street, **test_action))

    @pytest.mark.freeze_time('1999-12-31')
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

    @pytest.mark.parametrize("model,url,num_keys",
                             [(HandHistory, '/hand_history/', 5),
                              (Player, '/players/', 5),
                              (Seat, '/seats/', 6),
                              (Action, '/actions/', 7),
                              (Street, '/streets/', 6)])
    def test_list_get(self, login, model, url, num_keys, setup_test_data):
        data = login.get(url, content_type='application/json').json()
        assert {'count', 'next', 'previous'}.issubset(data.keys())
        assert 1 == data['count']
        assert 1 == len(data['results'])
        assert len(data['results'][0]) == num_keys

    @pytest.mark.parametrize("model,post_data,url,num_keys",
                             [(HandHistory, {}, '/hand_history/', 5),
                              (Player, post_player, '/players/', 5),
                              (Seat, post_seat, '/seats/', 6),
                              (Action, post_action, '/actions/', 7),
                              (Street, post_street, '/streets/', 6)])
    def test_single_post(self, login, model, post_data, url, num_keys):
        data = login.post(url, content_type='application/json', data=post_data).json()
        db_data = model.objects.get(pk=data['id'])
        assert len(data.keys()) == num_keys

    def test_insert_cascade_street(self, login, insert_data):
        player = insert_data(Player, test_player)
        hh = insert_data(HandHistory, {})

        street = login.post('/streets/', data=dict(hand_history=hh.id, **test_street_nested),
                            content_type='application/json')

        assert street.status_code == 201
        assert len(list(Action.objects.all())) == 1
        assert len(list(Street.objects.all())) == 1
        action = next(iter(Action.objects.all()))
        street = next(iter(Street.objects.all()))
        assert action.street_id == street.id
        assert action.player_id == player.id

    def test_playerhand_view(self, login, insert_data):
        player1 = insert_data(Player, test_player)
        player2 = insert_data(Player, {'name': 'player2'})
        hh1 = insert_data(HandHistory, {})
        hh2 = insert_data(HandHistory, {})
        insert_data(Seat, dict(player=player1, hand_history=hh1, **test_seat))
        insert_data(Seat, dict(player=player2, hand_history=hh2, **test_seat))

        data = login.get('/player_hands/player2/', content_type='application/json').json()
        assert data == {'player2': [f'http://testserver/hand_history/{hh2.id}/']}

    def test_hand_history_post(self, login, insert_data):
        player = insert_data(Player, test_player)

        hh = login.post('/hand_history/', data=test_hh_full, content_type='application/json')

        assert hh.status_code == 201
        assert len(list(Action.objects.all())) == 2
        assert len(list(Street.objects.all())) == 1
        assert len(list(Seat.objects.all())) == 2

    @pytest.mark.parametrize("post_data,missing_key,url",
                             [(post_seat_missing, 'chips', '/seats/'),
                              (post_action_missing, 'player', '/actions/'),
                              (post_street_missing, 'name', '/streets/')])
    def test_400_field_required(self, login, post_data, missing_key, url):
        response = login.post(url, content_type='application/json', data=post_data)
        assert response.status_code == 400
        assert len(response.json()) == 1
        assert missing_key in response.json()
