from pokerapp.models import HandHistory, Seat, Action, Player, Street
from rest_framework import permissions, viewsets
from pokerapp.serializers import HandHistorySerializer, SeatSerializer, \
        ActionSerializer, PlayerSerializer, StreetSerializer


class HandHistoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = HandHistory.objects.all().order_by('date_played')
    serializer_class = HandHistorySerializer
    permission_classes = [permissions.IsAuthenticated]


class SeatViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Seat.objects.all().order_by('hand_history__date_played')
    serializer_class = SeatSerializer
    permission_classes = [permissions.IsAuthenticated]


class ActionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Action.objects.all().order_by('street__hand_history__date_played', 'street__name', 'sequence_no')
    serializer_class = ActionSerializer
    permission_classes = [permissions.IsAuthenticated]


class StreetViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Street.objects.all().order_by('hand_history__date_played', 'name')
    serializer_class = StreetSerializer
    permission_classes = [permissions.IsAuthenticated]


class PlayerViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Player.objects.all().order_by('name')
    serializer_class = PlayerSerializer
    permission_classes = [permissions.IsAuthenticated]
