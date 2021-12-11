from pokerapp.models import HandHistory, Seat, Action, Player, Street
from rest_framework import permissions, viewsets
from pokerapp.serializers import HandHistorySerializer, SeatSerializer, \
        ActionSerializer, PlayerSerializer, StreetSerializer


class HandHistoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = HandHistory.objects.all().order_by('-date_played')
    serializer_class = HandHistorySerializer
    permission_classes = [permissions.IsAuthenticated]


class PlayerSeatViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer
    permission_classes = [permissions.IsAuthenticated]


class PlayerActionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Action.objects.all()
    serializer_class = ActionSerializer
    permission_classes = [permissions.IsAuthenticated]


class StreetViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Street.objects.all()
    serializer_class = StreetSerializer
    permission_classes = [permissions.IsAuthenticated]


class PlayerViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    permission_classes = [permissions.IsAuthenticated]
