from .models import Player, Seat, Action, HandHistory, Street
from django.db.models import ObjectDoesNotExist
from django.http import request
from rest_framework import serializers
import frozendict


class PlayerName(serializers.RelatedField):
    def __init__(self, **kwargs):
        kwargs['queryset'] = Player.objects.all()
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        try:
            player = Player.objects.get(name=data)
        except ObjectDoesNotExist:
            player = Player.objects.create(name=data)
        return player

    def to_representation(self, value):
        return value.name


class ChoicesDisplay(serializers.IntegerField):

    def __init__(self, choice_list, **kwargs):
        self.__choice_list = choice_list
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if isinstance(data, int):
            return data
        try:
            return self.__choice_list.index(data)
        except IndexError:
            raise ValueError(f'Invalid closed list {data}. Possible values {self.__choice_list}')

    def to_representation(self, value):
        return self.__choice_list[value]


class ModelAccessor(serializers.RelatedField):
    """Permit a nested view of the models.

    To make the api usable post behavior is being changed to either linking with an existing nested object id,
    or creating one of these nested objects in place if all required fields are provided.
    Limitation : Due to django internals the url field can't be used inside the provided serializer.
    """

    def __init__(self, model, serializer, **kwargs):
        self.__related_model = model
        self.__related_serializer = serializer
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if isinstance(data, int):
            return self.__related_model.objects.get(pk=data)
        return self.__related_model.objects.create(**data)

    def to_representation(self, value):
        #  Frozendict is a workaround to django drf templates, which is broken when a plain dict is returned.
        return frozendict.frozendict(self.__related_serializer(value).data)


class BaseSeatSerializer(serializers.ModelSerializer):
    seat = ChoicesDisplay(Seat.SEATS)

    class Meta:
        ordering = ['seat']
        model = Seat
        fields = ['seat', 'chips']


class BaseActionSerializer(serializers.ModelSerializer):
    player = PlayerName()
    action = ChoicesDisplay(Action.ACTIONS)

    class Meta:
        model = Action
        ordering = ['sequence_no']
        fields = ['player', 'action', 'amount', 'sequence_no']


class BaseStreetSerializer(serializers.ModelSerializer):
    name = ChoicesDisplay(Street.STREET_NAMES)

    class Meta:
        model = Street
        ordering = ['hand_history', 'name']
        fields = ['name', 'cards']


class BaseHandHistorySerializer(serializers.ModelSerializer):

    class Meta:
        model = HandHistory
        ordering = ['date_played']
        fields = ['id', 'date_played']


class PlayerSeatSerializer(BaseSeatSerializer):
    hand_history = ModelAccessor(HandHistory, BaseHandHistorySerializer, queryset=HandHistory.objects.all())

    class Meta(BaseSeatSerializer.Meta):
        fields = BaseSeatSerializer.Meta.fields + ['id', 'url', 'hand_history']


class PlayerSerializer(serializers.ModelSerializer):
    seats = PlayerSeatSerializer(many=True, read_only=True)

    class Meta:
        model = Player
        fields = ['id', 'url', 'name', 'seats']


class StreetSerializer(BaseStreetSerializer):
    actions = BaseActionSerializer(many=True, read_only=True)
    hand_history = ModelAccessor(HandHistory, BaseHandHistorySerializer, queryset=HandHistory.objects.all())

    class Meta(BaseStreetSerializer.Meta):
        fields = BaseStreetSerializer.Meta.fields + ['id', 'url', 'actions',  'hand_history']


class PlayerActionStreetSerializer(BaseStreetSerializer):
    hand_history = ModelAccessor(HandHistory, BaseHandHistorySerializer, queryset=HandHistory.objects.all())

    class Meta(BaseStreetSerializer.Meta):
        fields = BaseStreetSerializer.Meta.fields + ['hand_history']


class HandHistoryStreetSerializer(BaseStreetSerializer):
    actions = BaseActionSerializer(many=True, read_only=True)

    class Meta(BaseStreetSerializer.Meta):
        fields = BaseStreetSerializer.Meta.fields + ['actions']


class ActionSerializer(BaseActionSerializer):
    street = ModelAccessor(Street, PlayerActionStreetSerializer, queryset=Street.objects.all())

    class Meta(BaseActionSerializer.Meta):
        fields = BaseActionSerializer.Meta.fields + ['id', 'url', 'street']


class HandHistorySeatSerializer(BaseSeatSerializer):
    player = PlayerName()

    class Meta(BaseSeatSerializer.Meta):
        fields = BaseSeatSerializer.Meta.fields + ['player']


class SeatSerializer(BaseSeatSerializer):
    hand_history = ModelAccessor(HandHistory, BaseHandHistorySerializer, queryset=HandHistory.objects.all())
    player = PlayerName()

    class Meta(BaseSeatSerializer.Meta):
        fields = BaseSeatSerializer.Meta.fields + ['hand_history', 'player']


class HandHistorySerializer(BaseHandHistorySerializer):
    streets = HandHistoryStreetSerializer(many=True, read_only=True)
    seats = BaseSeatSerializer(many=True, read_only=True)

    class Meta(BaseHandHistorySerializer.Meta):
        fields = BaseHandHistorySerializer.Meta.fields + ['id', 'url', 'streets', 'seats']
