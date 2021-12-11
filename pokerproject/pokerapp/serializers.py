from abc import ABC

from .models import Player, Seat, Action, HandHistory, Street
from django.db.models import ObjectDoesNotExist, Manager
from rest_framework import serializers, relations


class PlayerName(serializers.RelatedField):
    """Abstracts player to a single string to reduce nested depth."""

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
    """Allow the display of choices fields through their display values.

    Allow serialization using either the internal value or the display one.
    This behavior could be dangerous for same-type choices list where it could have collisions, use with caution.
    """

    def __init__(self, choice_list, **kwargs):
        self.__choice_list = choice_list
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if isinstance(data, int):
            return data
        for internal_value, display_value in self.__choice_list:
            if display_value == data:
                return internal_value
        raise ValueError(f'Invalid closed list {data}. Possible values {[choice[1] for choice in self.__choice_list]}')

    def to_representation(self, value):
        return self.__choice_list[value][1]


class ExcludeFieldListSerializer(serializers.ListSerializer, ABC):

    def to_representation_exclude(self, data, exclude=None):
        iterable = data.all() if isinstance(data, Manager) else data
        if isinstance(self.child, (ExcludeFieldListSerializer, ModelAccessor)):
            return [self.child.to_representation_exclude(item, exclude) for item in iterable]
        return [self.child.to_representation(item) for item in iterable]

    def to_representation(self, data):
        return self.to_representation_exclude(data)


class ModelAccessor(serializers.HyperlinkedModelSerializer):
    """Permit a modified nested view of the models.

    Serializers using this accessor for a related model field have access to 3 behaviors:
    - When using GET, display the inner model fields
    - When using POST with a PK, link to an existing object
    - When using POST with data, create a son object in cascade
    """
    cascade_create = []

    def to_internal_value(self, data):
        if isinstance(data, int):
            return data
        return super().to_internal_value(data)

    def create(self, validated_data):
        cascade_fields = {}
        for k, value in list(validated_data.items()):
            if k in self.cascade_create:
                cascade_fields[k] = validated_data.pop(k)
            elif k in self.fields and isinstance(self.fields[k], ModelAccessor):
                validated_data[k] = self.fields[k].Meta.model.objects.get(pk=value)
            elif k in self.fields and isinstance(self.fields[k], serializers.Field):
                serializer = self.fields[k]
                validated_data[k] = serializer.to_internal_value(validated_data[k])

        new_obj = self.Meta.model.objects.create(**validated_data)
        for key, cascade_data in cascade_fields.items():
            cascade_serializer = self.fields[key]
            cascade_serializer.create(cascade_data)
        return new_obj

    def to_representation_exclude(self, instance, exclude=None):
        if exclude is None:
            exclude = []

        ret = {}
        fields = self._readable_fields
        for field in fields:
            if field.field_name in exclude:
                continue
            attribute = field.get_attribute(instance)
            check_for_none = attribute.pk if isinstance(attribute, relations.PKOnlyObject) else attribute
            if check_for_none is None:
                ret[field.field_name] = None
            elif isinstance(field, (ModelAccessor, ExcludeFieldListSerializer)):
                ret[field.field_name] = field.to_representation_exclude(attribute,
                                                                        exclude=exclude + self._recurse_exclude)
            else:
                ret[field.field_name] = field.to_representation(attribute)
        return ret

    def to_representation(self, instance):
        return self.to_representation_exclude(instance)

    class Meta:
        list_serializer_class = ExcludeFieldListSerializer


# Base serializers

class BaseSeatSerializer(ModelAccessor):
    player = PlayerName()
    seat = ChoicesDisplay(Seat.SEATS)
    _recurse_exclude = ['hand_history']

    class Meta(ModelAccessor.Meta):
        ordering = ['seat']
        model = Seat
        fields = ['id', 'player', 'seat', 'chips', 'hand_history']


class BaseActionSerializer(ModelAccessor):
    player = PlayerName()
    action = ChoicesDisplay(Action.ACTIONS)
    _recurse_exclude = ['action']

    class Meta(ModelAccessor.Meta):
        model = Action
        ordering = ['street', 'sequence_no']
        fields = ['id', 'action', 'street', 'sequence_no', 'player', 'amount']


class BaseStreetSerializer(ModelAccessor):
    actions = BaseActionSerializer(many=True)
    name = ChoicesDisplay(Street.STREET_NAMES)
    cascade_create = ['actions']
    _recurse_exclude = ['street']

    class Meta(ModelAccessor.Meta):
        model = Street
        ordering = ['hand_history', 'name']
        fields = ['id', 'hand_history', 'name', 'actions', 'cards']


class BaseHandHistorySerializer(ModelAccessor):
    _recurse_exclude = ['hand_history']

    class Meta(ModelAccessor.Meta):
        model = HandHistory
        ordering = ['date_played']
        fields = ['id', 'url', 'date_played']


# Final serializers, used in views

class PlayerSerializer(ModelAccessor):
    seats = serializers.HyperlinkedRelatedField(many=True, read_only=True, view_name='seat-detail')
    _recurse_exclude = ['actions']

    class Meta:
        model = Player
        fields = ['id', 'url', 'name', 'seats']


class StreetSerializer(BaseStreetSerializer):
    hand_history = BaseHandHistorySerializer()

    class Meta(BaseStreetSerializer.Meta):
        fields = BaseStreetSerializer.Meta.fields + ['url']


class ActionSerializer(BaseActionSerializer):
    street = BaseStreetSerializer()

    class Meta(BaseActionSerializer.Meta):
        fields = BaseActionSerializer.Meta.fields + ['url']


class SeatSerializer(BaseSeatSerializer):
    hand_history = BaseHandHistorySerializer()

    class Meta(BaseSeatSerializer.Meta):
        fields = BaseSeatSerializer.Meta.fields + ['url']


class HandHistorySerializer(BaseHandHistorySerializer):
    streets = BaseStreetSerializer(many=True)
    seats = BaseSeatSerializer(many=True)

    class Meta(BaseHandHistorySerializer.Meta):
        fields = BaseHandHistorySerializer.Meta.fields + ['streets', 'seats', 'url']
