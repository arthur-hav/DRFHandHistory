from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.postgres.fields import ArrayField

# Create your models here.


class Player(models.Model):
    """A poker player. Identified by id or name."""
    name = models.CharField(max_length=48, unique=True)


class HandHistory(models.Model):
    """A hand history. The central object of this model.

    A hand history traces all actions done by all players in a hand, as well as their starting stack and board cards."""
    date_played = models.DateTimeField(auto_now=True)


class Street(models.Model):
    """In poker actions are divided in 4 streets, each having separate cards and action round."""
    CARDS = tuple((rank + color, rank + color) for rank in 'AKQJT98765432' for color in 'hdsc')
    STREET_NAMES = tuple((i, name) for i, name in enumerate(('Preflop', 'Flop', 'Turn', 'River')))
    cards = ArrayField(models.CharField(choices=CARDS, max_length=2), null=True)
    hand_history = models.ForeignKey(HandHistory, on_delete=models.CASCADE, related_name='streets', null=True)
    name = models.IntegerField(choices=STREET_NAMES)


class Seat(models.Model):
    """This is modeling how much a given player had in the beginning of a given hand, as well as the action order."""
    SEATS = tuple((i, seat) for i, seat in enumerate(('BB', 'SB', 'BTN', 'CO', 'HJ', 'MP')))
    player = models.ForeignKey(Player, on_delete=models.DO_NOTHING, related_name='seats')
    hand_history = models.ForeignKey(HandHistory, on_delete=models.CASCADE, related_name='seats', null=True)
    seat = models.IntegerField(choices=SEATS)
    chips = models.IntegerField(validators=[MinValueValidator(0)])


class Action(models.Model):
    """Actions of the betting rounds."""
    ACTIONS = tuple((i, action) for i, action in enumerate(('Blind', 'Check', 'Call', 'Fold', 'Bet', 'Raise')))
    player = models.ForeignKey(Player, on_delete=models.DO_NOTHING, related_name='actions')
    street = models.ForeignKey(Street, on_delete=models.CASCADE, related_name='actions', null=True)
    action = models.IntegerField(choices=ACTIONS)
    amount = models.IntegerField(validators=[MinValueValidator(0)])
    sequence_no = models.IntegerField(validators=[MinValueValidator(1)])
