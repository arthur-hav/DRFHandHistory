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
from rest_framework import serializers, relations, fields
from rest_framework.exceptions import ValidationError


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
        for internal_value, display_value in self.__choice_list:
            if internal_value == data:
                return data
            if display_value == data:
                return internal_value
        raise ValueError(f'Invalid closed list reference {data}.'
                         f' Possible values {[choice[1] for choice in self.__choice_list]}')

    def to_representation(self, value):
        return self.__choice_list[value][1]


class NestedListSerializer(serializers.ListSerializer):

    def to_representation_exclude(self, data, exclude=None):
        iterable = data.all() if isinstance(data, Manager) else data
        if isinstance(self.child, (NestedListSerializer, NestedModelSerializer)):
            return [self.child.to_representation_exclude(item, exclude) for item in iterable]
        return [self.child.to_representation(item) for item in iterable]

    def to_representation(self, data):
        return self.to_representation_exclude(data)


class GenericUrl(serializers.HyperlinkedRelatedField):
    """Handy shortcut to display hand history as a link, but accept a simple id as post"""

    def __init__(self, ref_model, *args, **kwargs):
        kwargs['queryset'] = ref_model.objects.all()
        kwargs['required'] = False
        super().__init__(*args, **kwargs)
        self.__ref_model = ref_model

    def to_internal_value(self, data):
        if isinstance(data, int):
            return self.__ref_model.objects.get(pk=data)
        return super().to_internal_value(data)

    def to_representation(self, value):
        if isinstance(value, int):
            request = self.context['request']
            return self.reverse(self.view_name, kwargs={'pk': value}, request=request)
        return super().to_representation(value)


class NestedModelSerializer(serializers.ModelSerializer):
    """Permit a modified nested view of the models.

    Serializers using this accessor for a related model field have access to 3 behaviors:
    - When using GET, display the inner model fields
    - When using POST with a PK, link to an existing object
    - When using POST with data, create son objects in cascade
    """
    cascade_create = {}
    view_exclude = []

    def create(self, validated_data):
        cascade_fields = {}
        for k, value in list(validated_data.items()):
            if k in self.cascade_create:
                cascade_fields[k] = validated_data.pop(k)
        new_obj = super().create(validated_data)
        for key, cascade_data in cascade_fields.items():
            cascade_serializer = self.fields[key]
            for cascade_dict in cascade_data:
                cascade_dict[self.cascade_create[key]] = new_obj
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
            elif isinstance(field, (NestedModelSerializer, NestedListSerializer)):
                ret[field.field_name] = field.to_representation_exclude(attribute,
                                                                        exclude=exclude + self.view_exclude)
            else:
                ret[field.field_name] = field.to_representation(attribute)
        return ret

    def to_representation(self, instance):
        return self.to_representation_exclude(instance)

    class Meta:
        list_serializer_class = NestedListSerializer


class SeatSerializer(NestedModelSerializer):
    player = PlayerName()
    seat = ChoicesDisplay(Seat.SEATS)
    view_exclude = ['hand_history']
    hand_history = GenericUrl(HandHistory, view_name='handhistory-detail')

    class Meta(NestedModelSerializer.Meta):
        ordering = ['seat']
        model = Seat
        fields = ['id', 'url', 'player', 'seat', 'chips', 'hand_history']


class ActionSerializer(NestedModelSerializer):
    player = PlayerName()
    action = ChoicesDisplay(Action.ACTIONS)
    sequence_no = fields.IntegerField(required=False)
    street = GenericUrl(Street, view_name='street-detail')
    view_exclude = ['action']

    class Meta(NestedModelSerializer.Meta):
        model = Action
        ordering = ['street', 'sequence_no']
        fields = ['id', 'url', 'action', 'street', 'sequence_no', 'player', 'amount']

    def validate(self, attrs):
        if 'street' in attrs and 'sequence_no' in attrs:
            count = Action.objects.all().filter(street=attrs['street'], sequence_no=attrs['sequence_no']).count()
            if count != 0:
                raise ValidationError(['street', 'sequence_no', 'Street and sequence_no must be unique per Action'])
        return attrs

    def create(self, validated_data):
        if 'sequence_no' not in validated_data:
            validated_data['sequence_no'] = Action.objects.all().filter(street=validated_data['street']).count() + 1
        return super().create(validated_data)


class StreetSerializer(NestedModelSerializer):
    actions = ActionSerializer(many=True, required=False)
    name = ChoicesDisplay(Street.STREET_NAMES)
    hand_history = GenericUrl(HandHistory, view_name='handhistory-detail')
    cascade_create = {'actions': 'street'}
    view_exclude = ['street']

    class Meta(NestedModelSerializer.Meta):
        model = Street
        ordering = ['hand_history', 'name']
        fields = ['id', 'url', 'hand_history', 'name', 'actions', 'cards']


class PlayerSerializer(NestedModelSerializer):
    hands_played = fields.ReadOnlyField()

    class Meta:
        model = Player
        fields = ['id', 'url', 'name', 'hands_played']


class HandHistorySerializer(NestedModelSerializer):
    streets = StreetSerializer(many=True, required=False)
    seats = SeatSerializer(many=True, required=False)
    view_exclude = ['hand_history']
    cascade_create = {'streets': 'hand_history', 'seats': 'hand_history'}

    class Meta(NestedModelSerializer.Meta):
        model = HandHistory
        ordering = ['date_played']
        fields = ['id', 'url', 'date_played', 'streets', 'seats']
