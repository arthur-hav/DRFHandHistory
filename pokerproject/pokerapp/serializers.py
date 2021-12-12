"""DRF offers very nice functionalities to create RESTful APIs in a few classes, which is good design, but here
I wanted to experiment twisting the model a little bit.

The core experiment is to display hierarchically nested objects in a way that is easy to navigate top-down and
bottom-up, recursively, with asymmetry between get and post behaviors, in a way that could be used to minimize requests
load.

Even though the overall nested design can be reused, the overall goal remain to showcase possible
uses and extensibility of DRF over a simple model."""

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


class HandHistoryUrl(serializers.HyperlinkedRelatedField):
    """Handy shortcut to display hand history as a link, but accept a simple id as post"""
    def __init__(self, *args, **kwargs):
        kwargs['queryset'] = HandHistory.objects.all()
        kwargs['view_name'] = 'handhistory-detail'
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        if isinstance(data, int):
            return HandHistory.objects.get(pk=data)
        return super().to_internal_value(data)

    def to_representation(self, value):
        if isinstance(value, HandHistory):
            value = value.pk
        if isinstance(value, int):
            request = self.context['request']
            return self.reverse(self.view_name, kwargs={'pk': value}, request=request)
        return super().to_representation(value)


class ModelAccessor(serializers.HyperlinkedModelSerializer):
    """Permit a modified nested view of the models.

    Serializers using this accessor for a related model field have access to 3 behaviors:
    - When using GET, display the inner model fields
    - When using POST with a PK, link to an existing object
    - When using POST with data, create a son object in cascade
    """
    cascade_create = {}

    def to_internal_value(self, data):
        if isinstance(data, int):
            return data
        return super().to_internal_value(data)

    def create(self, validated_data):
        cascade_fields = {}
        for k, value in list(validated_data.items()):
            if k in self.cascade_create:
                cascade_fields[k] = validated_data.pop(k)
        print(self.__class__.__name__, validated_data)
        new_obj = super().create(validated_data)
        for key, cascade_data in cascade_fields.items():
            cascade_serializer = self.fields[key]
            cascade_objects = cascade_serializer.create(cascade_data)
            for cascade_object in cascade_objects:
                setattr(cascade_object, self.cascade_create[key] + '_id', new_obj.id)
                cascade_object.save()
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
    cascade_create = {'actions': 'street'}
    _recurse_exclude = ['street']

    class Meta(ModelAccessor.Meta):
        model = Street
        ordering = ['hand_history', 'name']
        fields = ['id', 'hand_history', 'name', 'actions', 'cards']


# Final serializers, used in views

class PlayerSerializer(ModelAccessor):

    class Meta:
        model = Player
        fields = ['id', 'url', 'name']


class StreetSerializer(BaseStreetSerializer):
    hand_history = HandHistoryUrl()

    class Meta(BaseStreetSerializer.Meta):
        fields = BaseStreetSerializer.Meta.fields + ['url']


class ActionSerializer(BaseActionSerializer):
    street = BaseStreetSerializer()

    class Meta(BaseActionSerializer.Meta):
        fields = BaseActionSerializer.Meta.fields + ['url']


class SeatSerializer(BaseSeatSerializer):
    hand_history = HandHistoryUrl()

    class Meta(BaseSeatSerializer.Meta):
        fields = BaseSeatSerializer.Meta.fields + ['url']


class HandHistorySerializer(ModelAccessor):
    streets = BaseStreetSerializer(many=True)
    seats = BaseSeatSerializer(many=True)
    _recurse_exclude = ['hand_history']
    cascade_create = {'streets': 'hand_history', 'seats': 'hand_history'}

    class Meta(ModelAccessor.Meta):
        model = HandHistory
        ordering = ['date_played']
        fields = ['id', 'url', 'date_played', 'streets', 'seats', 'url']

