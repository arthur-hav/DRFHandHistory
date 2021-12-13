from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.postgres.fields import ArrayField
import redis
from collections import Counter
from django.dispatch import receiver
from django.db.models.signals import pre_save, post_save, pre_delete


class AbstractRedisStat:

    @classmethod
    def players_stated(cls, hand_history):
        players = set()
        for seat in hand_history.seats.all():
            players.add(seat.player_id)
        return players

    @classmethod
    def compute(cls):
        hands = Counter()
        hand_histories = HandHistory.objects.all()
        for hh in hand_histories:
            for player_id in cls.players_stated(hh):
                hands[player_id] += 1
        return hands

    @classmethod
    def get(cls, player_id):
        """Get cached value"""
        r = redis.Redis(host='redis')
        key = f'{cls.key_name}.{player_id}'
        value = r.get(key)
        if value is None:
            hands = cls.reset()
            value = hands[player_id]
        return value

    @classmethod
    def reset(cls):
        """Compute for every player the number of hands played, cache it through redis and return it."""
        hands = cls.compute()
        r = redis.Redis(host='redis')
        # Explicitly set to 0 the players that don't have any hand in hands variable
        for player in Player.objects.all():
            r.set(f'{cls.key_name}.{player.id}', hands[player.id])
            # Consistency measure: should the events be badly configured,
            # we still recompute the value fully every once in a while
            r.expire(f'{cls.key_name}.{player.id}', 3600)
        return hands


class HandsPlayedStat(AbstractRedisStat):
    """Number of hands played by a player.

    This could be realistically implemented by an optimized queryset, and is a bit underwhelming function to cache,
    but is one of the simplest example of things that can be cached through redis.
    """

    key_name = 'hands'


class VpipStat(AbstractRedisStat):
    """Number of hands where the player volontarily put money in pot.

    More complex example with manipulating counts
    """

    key_name = 'vpip'

    @classmethod
    def players_stated(cls, hand_history):
        vpip = set()
        for street in hand_history.streets.all():
            for action in street.actions.all():
                if action.action in {2, 4, 5}:
                    vpip.add(action.player_id)
        return vpip


class Player(models.Model):
    """A poker player. Identified by id or name.

    The property hands_played is implemented through a Redis field, which is overly complex for what it does,
    but is a pretext to show a way to hybrid database through cached parameters without creating a new model field,
    and showcase an example use of django signals.
    """

    name = models.CharField(max_length=48, unique=True)

    @property
    def hands_played(self):
        return HandsPlayedStat.get(self.id)

    @property
    def vpip(self):
        return 100 * VpipStat.get(self.id) / max(self.hands_played, 1)

    @staticmethod
    @receiver(pre_save)
    @receiver(pre_delete)
    def handle_pre_save(*args, **kwargs):
        if kwargs['sender'] not in (Seat, HandHistory, Action):
            return
        kwargs['instance'].up_redis_delete()

    @staticmethod
    @receiver(post_save)
    def handle_post_save(*args, **kwargs):
        if kwargs['sender'] not in (Seat, HandHistory, Action):
            return
        kwargs['instance'].up_redis_create()


class HandHistory(models.Model):
    """A hand history. The central object of this model.

    A hand history traces all actions done by all players in a hand, as well as their starting stack and board cards."""
    date_played = models.DateTimeField(auto_now=True)

    def up_redis_create(self):
        r = redis.Redis(host='redis')
        for seat in self.seats.all():
            r.incr(f'hands.{seat.player_id}')

    def up_redis_delete(self):
        r = redis.Redis(host='redis')
        for seat in self.seats.all():
            r.decr(f'hands.{seat.player_id}')


class Seat(models.Model):
    """This is modeling how much a given player had in the beginning of a given hand, as well as the action order."""
    SEATS = tuple((i, seat) for i, seat in enumerate(('BB', 'SB', 'BTN', 'CO', 'HJ', 'MP')))
    player = models.ForeignKey(Player, on_delete=models.DO_NOTHING, related_name='seats')
    hand_history = models.ForeignKey(HandHistory, on_delete=models.CASCADE, related_name='seats', null=True,
                                     db_index=True)
    seat = models.IntegerField(choices=SEATS)
    chips = models.IntegerField(validators=[MinValueValidator(0)])

    def up_redis_create(self):
        self.hand_history.up_redis_create()

    def up_redis_delete(self):
        self.hand_history.up_redis_delete()


class Street(models.Model):
    """In poker actions are divided in 4 streets, each having separate cards and action round."""
    CARDS = tuple((rank + color, rank + color) for rank in 'AKQJT98765432' for color in 'hdsc')
    STREET_NAMES = tuple((i, name) for i, name in enumerate(('Preflop', 'Flop', 'Turn', 'River')))
    cards = ArrayField(models.CharField(choices=CARDS, max_length=2), null=True)
    hand_history = models.ForeignKey(HandHistory, on_delete=models.CASCADE, related_name='streets', null=True,
                                     db_index=True)
    name = models.IntegerField(choices=STREET_NAMES)

    def up_redis_create(self):
        self.hand_history.up_redis_create()

    def up_redis_delete(self):
        self.hand_history.up_redis_delete()


class Action(models.Model):
    """Actions of the betting rounds."""
    ACTIONS = tuple((i, action) for i, action in enumerate(('Blind', 'Check', 'Call', 'Fold', 'Bet', 'Raise')))
    player = models.ForeignKey(Player, on_delete=models.DO_NOTHING, related_name='actions')
    street = models.ForeignKey(Street, on_delete=models.CASCADE, related_name='actions', null=True, db_index=True)
    action = models.IntegerField(choices=ACTIONS)
    amount = models.IntegerField(validators=[MinValueValidator(0)])
    sequence_no = models.IntegerField(validators=[MinValueValidator(1)])

    def up_redis_create(self):
        self.street.up_redis_create()

    def up_redis_delete(self):
        self.street.up_redis_delete()