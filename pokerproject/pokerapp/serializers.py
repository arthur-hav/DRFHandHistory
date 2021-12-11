from .models import Player, PlayerSeat, PlayerAction, HandHistory
from rest_framework.serializers import ListField, CharField, DateTimeField, ModelSerializer, Serializer


class PlayerSerializer(ModelSerializer):
    class Meta:
        model = Player
        fields = ['name']


class FlatPlayerSeatSerializer(ModelSerializer):
    player = PlayerSerializer(read_only=True)

    class Meta:
        model = PlayerSeat
        fields = ['player', 'seat', 'chips']


class FlatPlayerActionSerializer(ModelSerializer):
    player = PlayerSerializer(read_only=True)

    class Meta:
        model = PlayerAction
        fields = ['id', 'url', 'player', 'action', 'amount', 'sequence_no', 'action_no']


class PlayerSeatSerializer(ModelSerializer):

    class Meta:
        model = PlayerSeat
        fields = ['id', 'url', 'player', 'seat', 'chips', 'hand_history']


class PlayerActionSerializer(ModelSerializer):

    class Meta:
        model = PlayerAction
        fields = ['id', 'url', 'player', 'action', 'amount', 'sequence_no', 'action_no', 'hand_history']


class HandHistorySerializer(ModelSerializer):
    actions = FlatPlayerActionSerializer(many=True, read_only=True)
    seats = FlatPlayerSeatSerializer(many=True, read_only=True)

    class Meta:
        model = HandHistory
        fields = ['id', 'url', 'actions', 'flop_cards', 'date_played', 'turn_cards', 'river_card', 'seats']
