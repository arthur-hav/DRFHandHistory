from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.postgres.fields import ArrayField

# Create your models here.


class Player(models.Model):
    name = models.CharField(max_length=48)


class HandHistory(models.Model):
    date_played = models.DateTimeField(auto_now=True)


class Street(models.Model):
    CARDS = tuple((rank + color, rank + color) for rank in 'AKQJT98765432' for color in 'hdsc')
    STREET_NAMES = tuple((i, name) for i, name in enumerate(('Preflop', 'Flop', 'Turn', 'River')))
    cards = ArrayField(models.CharField(choices=CARDS, max_length=2), null=True)
    hand_history = models.ForeignKey(HandHistory, on_delete=models.CASCADE, related_name='streets')
    name = models.IntegerField(choices=STREET_NAMES)


class Seat(models.Model):
    SEATS = tuple((i, seat) for i, seat in enumerate(('BB', 'SB', '0', '1', '2', '3', '4', '5')))
    player = models.ForeignKey(Player, on_delete=models.DO_NOTHING, related_name='seats')
    hand_history = models.ForeignKey(HandHistory, on_delete=models.CASCADE, related_name='seats')
    seat = models.IntegerField(choices=SEATS)
    chips = models.IntegerField(validators=[MinValueValidator(0)])


class Action(models.Model):
    ACTIONS = tuple((i, action) for i, action in enumerate(('Blind', 'Check', 'Call', 'Fold', 'Bet', 'Raise')))
    player = models.ForeignKey(Player, on_delete=models.DO_NOTHING, related_name='actions')
    street = models.ForeignKey(Street, on_delete=models.CASCADE, related_name='actions')
    action = models.IntegerField(choices=ACTIONS)
    amount = models.IntegerField(validators=[MinValueValidator(0)])
    sequence_no = models.IntegerField(validators=[MinValueValidator(1)])
