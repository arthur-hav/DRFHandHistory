from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.postgres.fields import ArrayField
import redis
from collections import Counter
from django.dispatch import receiver
from django.db.models.signals import pre_save, post_save, post_delete


class Player(models.Model):
    """A poker player. Identified by id or name.

    The property hands_played is implemented through a Redis field, which is overly complex for what it does,
    but is a pretext to show a way to hybrid database through cached parameters without creating a new model field,
    and showcase an example use of django signals.
    """

    name = models.CharField(max_length=48, unique=True)

    @staticmethod
    def reset_hands_played():
        """Computation to be cached through Redis."""

        # I admit once I optimized the queryset this is a bit underwhelming function to cache,
        # but we could pretend the computation is heavy there.
        hands = Counter()
        seats = Seat.objects.all()
        for seat in seats:
            hands[seat.player_id] += 1

        r = redis.Redis(host='redis')
        for player_id, value in hands.items():
            r.set(f'hands.{player_id}', value)
            # Consistency measure: should the events be badly configured,
            # we still recompute the value fully once in a while
            r.expire(f'hands.{player_id}', 3600)
        return hands

    @property
    def hands_played(self):
        r = redis.Redis(host='redis')
        key = f'hands.{self.id}'
        value = r.get(key)
        if value is None:
            hands = self.reset_hands_played()
            value = hands[self.id]
        return value

    @staticmethod
    @receiver(pre_save)
    def handle_pre_save(*args, **kwargs):
        if kwargs['sender'] != Seat:
            return
        r = redis.Redis(host='redis')
        # The gotcha with this django signals is handling correctly partial model updates, which can be difficult
        if kwargs['update_fields'] and 'player' in kwargs['update_fields']:
            old_player_id = kwargs['instance'].player_id
            r.decr(f'hands.{old_player_id}')

    @staticmethod
    @receiver(post_save)
    def handle_post_save(*args, **kwargs):
        if kwargs['sender'] != Seat:
            return
        r = redis.Redis(host='redis')
        player_id = kwargs['instance'].player_id
        if kwargs['created']:
            r.incr(f'hands.{player_id}')
        elif kwargs['update_fields'] and 'player' in kwargs['update_fields']:
            r.incr(f'hands.{player_id}')

    @staticmethod
    @receiver(post_delete)
    def handle_post_delete(*args, **kwargs):
        if kwargs['sender'] != Seat:
            return
        r = redis.Redis(host='redis')
        player_id = kwargs['instance'].player_id
        r.decr(f'hands.{player_id}')


class HandHistory(models.Model):
    """A hand history. The central object of this model.

    A hand history traces all actions done by all players in a hand, as well as their starting stack and board cards."""
    date_played = models.DateTimeField(auto_now=True)


class Seat(models.Model):
    """This is modeling how much a given player had in the beginning of a given hand, as well as the action order."""
    SEATS = tuple((i, seat) for i, seat in enumerate(('BB', 'SB', 'BTN', 'CO', 'HJ', 'MP')))
    player = models.ForeignKey(Player, on_delete=models.DO_NOTHING, related_name='seats')
    hand_history = models.ForeignKey(HandHistory, on_delete=models.CASCADE, related_name='seats', null=True)
    seat = models.IntegerField(choices=SEATS)
    chips = models.IntegerField(validators=[MinValueValidator(0)])


class Street(models.Model):
    """In poker actions are divided in 4 streets, each having separate cards and action round."""
    CARDS = tuple((rank + color, rank + color) for rank in 'AKQJT98765432' for color in 'hdsc')
    STREET_NAMES = tuple((i, name) for i, name in enumerate(('Preflop', 'Flop', 'Turn', 'River')))
    cards = ArrayField(models.CharField(choices=CARDS, max_length=2), null=True)
    hand_history = models.ForeignKey(HandHistory, on_delete=models.CASCADE, related_name='streets', null=True)
    name = models.IntegerField(choices=STREET_NAMES)


class Action(models.Model):
    """Actions of the betting rounds."""
    ACTIONS = tuple((i, action) for i, action in enumerate(('Blind', 'Check', 'Call', 'Fold', 'Bet', 'Raise')))
    player = models.ForeignKey(Player, on_delete=models.DO_NOTHING, related_name='actions')
    street = models.ForeignKey(Street, on_delete=models.CASCADE, related_name='actions', null=True)
    action = models.IntegerField(choices=ACTIONS)
    amount = models.IntegerField(validators=[MinValueValidator(0)])
    sequence_no = models.IntegerField(validators=[MinValueValidator(1)])
