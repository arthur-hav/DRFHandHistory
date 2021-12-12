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


class TestPokerApp:
    fixture = ['login']
    test_player = {'name': 'Test Player'}
    test_seat = {'chips': 2000, 'seat': 0}
    test_action = {'action': 0, 'amount': 100, 'sequence_no': 1}
    test_street = {'name': 0, 'cards': None}
    test_street_nested = {'name': 0, 'actions': [{'player': 'Test Player',
                                                  'action': 'Blind',
                                                  'amount': 100,
                                                  'sequence_no': 1}]}
    test_hh_full = {
        "id": 1,
        "url": "http://localhost:8000/hand_history/1/",
        "date_played": "2021-12-11T10:55:32.149294Z",
        "streets": [
            {
                "id": 2,
                "name": "Preflop",
                "actions": [
                    {
                        "id": 2,
                        "action": "Blind",
                        "sequence_no": 1,
                        "player": "Dom Twan",
                        "amount": 5
                        },
                    {
                        "id": 3,
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
                "id": 1,
                "player": "Dom Twan",
                "seat": "SB",
                "chips": 333
                },
            {
                "id": 2,
                "player": "Antrick Patonius",
                "seat": "BB",
                "chips": 444
                }
            ]
        }

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
                              (Player, '/players/', 3),
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
        print(street.json())

        assert street.status_code == 201
        assert len(list(Action.objects.all())) == 1
        assert len(list(Street.objects.all())) == 1
        action = next(iter(Action.objects.all()))
        street = next(iter(Street.objects.all()))
        assert action.street_id == street.id
        assert action.player_id == player.id

    def test_playerhand_view(self, login, insert_data):
        player1 = insert_data(Player, self.test_player)
        player2 = insert_data(Player, {'name': 'player2'})
        hh1 = insert_data(HandHistory, {})
        hh2 = insert_data(HandHistory, {})
        insert_data(Seat, dict(player=player1, hand_history=hh1, **self.test_seat))
        insert_data(Seat, dict(player=player2, hand_history=hh2, **self.test_seat))

        data = login.get('/player_hands/player2/', content_type='application/json').json()
        assert data == {'player2': [f'http://testserver/hand_history/{hh2.id}/']}

    def test_hand_history_post(self, login, insert_data):
        player = insert_data(Player, self.test_player)

        hh = login.post('/hand_history/', data=self.test_hh_full, content_type='application/json')

        print(hh.json())

        assert hh.status_code == 201
        assert len(list(Action.objects.all())) == 2
        assert len(list(Street.objects.all())) == 1
        assert len(list(Seat.objects.all())) == 2

