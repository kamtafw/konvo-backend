from django.contrib.auth import get_user_model
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer

User = get_user_model()


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def user_signup(request):
    """
    Creates a new user. It's and idempotent operation.
    Required fields for signup are: username, phone_number, and password.

    Arguments:
    - request: Django request object containing user data.

    Returns:
    - 201 response object containing user data and JWT tokens upon successful signup.
    - 400 response object containing error details if signup fails.
    """

    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        if user := serializer.save():
            user_profile = serializer.data
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "profile": user_profile,
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_201_CREATED,
            )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def user_login(request):
    """
    Authenticates a user using username or phone_number.

    Arguments:
    - request: Django request object containing login credentials (username/phone_number and password).

    Returns:
    - 200 response object containing user data and JWT tokens upon successful login.
    - 400 response object containing error details if login fails.
    """

    username = request.data.get("username")
    password = request.data.get("password")

    if username is None or password is None:
        return Response({"error": "Both username/phone-number and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(username=username).first()

    if user is None:
        user = User.objects.filter(phone_number=username).first()

    if user is None:
        return Response({"error": "Invalid login details."}, status=status.HTTP_400_BAD_REQUEST)

    if not user.check_password(password):
        return Response({"error": "Invalid login details."}, status=status.HTTP_400_BAD_REQUEST)

    user_profile = UserSerializer(user).data

    refresh = RefreshToken.for_user(user)
    data = {
        "profile": user_profile,
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
    return Response(data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def get_user_profile(request):
    pass
