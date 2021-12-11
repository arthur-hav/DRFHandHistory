from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.postgres.fields import ArrayField

# Create your models here.


class Player(models.Model):
    name = models.CharField(max_length=48)


class HandHistory(models.Model):
    CARDS = tuple((rank + color, rank + color) for rank in 'AKQJT98765432' for color in 'hdsc')
    date_played = models.DateTimeField(auto_now=True)
    flop_cards = ArrayField(ArrayField(models.CharField(choices=CARDS, max_length=2), size=2), size=2, null=True)
    turn_cards = ArrayField(models.CharField(choices=CARDS, max_length=2), null=True)
    river_card = models.CharField(choices=CARDS, max_length=2, null=True)


class PlayerSeat(models.Model):
    SEATS = tuple((seat, seat) for seat in ('BB', 'SB', '0', '1', '2', '3', '4', '5'))
    player = models.ForeignKey(Player, on_delete=models.DO_NOTHING, related_name='seats')
    hand_history = models.ForeignKey(HandHistory, on_delete=models.CASCADE, related_name='seats')
    seat = models.CharField(choices=SEATS, max_length=2)
    chips = models.IntegerField(validators=[MinValueValidator(0)])


class PlayerAction(models.Model):
    ACTIONS = tuple((action, action) for action in ('Blind', 'Check', 'Call', 'Fold', 'Bet', 'Raise'))
    player = models.ForeignKey(Player, on_delete=models.DO_NOTHING, related_name='actions')
    hand_history = models.ForeignKey(PlayerSeat, on_delete=models.CASCADE, related_name='actions')
    action = models.CharField(choices=ACTIONS, max_length=24)
    amount = models.IntegerField(validators=[MinValueValidator(0)])
    sequence_no = models.IntegerField(validators=[MinValueValidator(1)])
    street_no = models.IntegerField(validators=[MinValueValidator(1)])
