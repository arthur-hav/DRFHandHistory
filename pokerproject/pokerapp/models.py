from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.postgres.fields import ArrayField
from collections import Counter


class PlayerStat:
    """A stat point, expressed in percentage of a hand history subset"""
    name = ''

    @staticmethod
    def is_in_set(player_id, streets, actions):
        return True

    @staticmethod
    def is_in_subset(player_id, streets, actions):
        return True


class VpipStat(PlayerStat):
    name = 'vpip'

    @staticmethod
    def is_in_subset(player_id, streets, actions):
        return any(action.action in {2, 4, 5} and action.player_id == player_id for action in actions)


class PfrStat(PlayerStat):
    name = 'pfr'

    @staticmethod
    def is_in_subset(player_id, streets, actions):
        return any(action.action in {4, 5}
                   and action.player_id == player_id
                   and action.street.name == 0
                   for action in actions)


class ThreeBetStat(PlayerStat):
    name = "threebet"

    @staticmethod
    def is_in_subset(player_id, streets, actions):
        return any(action.action in {4, 5}
                   and action.player_id == player_id
                   and action.street.name == 0
                   for action in actions)

    @staticmethod
    def is_in_set(player_id, streets, actions):
        player_actions = [action for action in actions if action.player_id == player_id and action.action != 0]
        if not player_actions:
            return False
        player_seq_no = min(player_actions)
        return any(action.action in {4, 5}
                   and action.sequence_no < player_seq_no
                   and action.street.name == 0
                   for action in actions)


class PlayerStats:
    """A getter providing hand history statistics summary for a given Player."""

    def __init__(self, player_id, stats):
        self.player_id = player_id
        self.stats = stats

    def get_value(self):
        data = HandHistory.objects.all().filter(seats__player_id=self.player_id)
        set_hits = Counter()
        subset_hits = Counter()
        for hand_history in data:
            streets = Street.objects.all().filter(hand_history_id=hand_history.id)
            street_ids = [street.id for street in streets]
            actions = Action.objects.all().filter(street_id__in=street_ids)
            for stat in self.stats:
                if stat.is_in_set(self.player_id, streets, actions):
                    set_hits[stat.name] += 1
                    if stat.is_in_subset(self.player_id, streets, actions):
                        subset_hits[stat.name] += 1
        return {stat.name: 100 * subset_hits[stat.name] / max(set_hits[stat.name], 1) for stat in self.stats}


class Player(models.Model):
    """A poker player. Identified by id or name."""
    name = models.CharField(max_length=48, unique=True)

    def get_stats(self):
        return PlayerStats(self.id, (VpipStat, PfrStat, ThreeBetStat)).get_value()


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
