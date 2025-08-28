from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, login
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import User, Profile, Children
from .serializers import (
    UserRegistrationSerializer,
    LoginSerializer,
    UserSerializer,
    UserProfileUpdateSerializer,
    ForgotPasswordSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer,
    ChildrenSerializer,
    UserchangePasswordSerializer
    
)


class RegisterView(generics.CreateAPIView):
    """
    Register a new user with full name, email, password, and optional profile photo.
    Automatically creates a profile after successful registration.
    """
    queryset = User.objects.all()  
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Register a new user",
        request_body=UserRegistrationSerializer,
        responses={
            201: openapi.Response(
                description="User registered successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'user': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'full_name': openapi.Schema(type=openapi.TYPE_STRING),
                                'email': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(description="Bad request - validation errors")
        }
    )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Serialize user data
        user_serializer = UserSerializer(user, context={'request': request})
        
        return Response({
            'message': 'User registered successfully',
            'user': user_serializer.data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    """
    Authenticate user with email and password.
    Returns user information with access and refresh tokens.
    """
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Login user with email and password",
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                description="Login successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'user': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'full_name': openapi.Schema(type=openapi.TYPE_STRING),
                                'email': openapi.Schema(type=openapi.TYPE_STRING),
                                'profile': openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        'profile_photo': openapi.Schema(type=openapi.TYPE_STRING),
                                    }
                                )
                            }
                        ),
                        'tokens': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'access': openapi.Schema(type=openapi.TYPE_STRING),
                                'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(description="Invalid credentials")
        }
    )

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Serialize user data
        user_serializer = UserSerializer(user, context={'request': request})
        
        return Response({
            'message': 'Login successful',
            'user': user_serializer.data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)


class UserProfileView(generics.RetrieveAPIView):
    """
    Get current user's profile information including profile photo.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get current user profile",
        responses={
            200: openapi.Response(
                description="User profile retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'full_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                        'profile': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'profile_photo': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    }
                )
            ),
            401: openapi.Response(description="Authentication required")
        }
    )

    def get_object(self):
        return self.request.user


class UserProfileUpdateView(generics.UpdateAPIView):
    """
    Update current user's profile including full name and profile photo.
    """
    serializer_class = UserProfileUpdateSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Update user profile",
        request_body=UserProfileUpdateSerializer,
        responses={
            200: openapi.Response(
                description="Profile updated successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'full_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                        'profile': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'profile_photo': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(description="Validation errors"),
            401: openapi.Response(description="Authentication required")
        }
    )

    def get_object(self):
        return self.request.user


@swagger_auto_schema(
    method='post',
    operation_description="Logout user by blacklisting refresh token",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh token to blacklist'),
        },
        required=['refresh']
    ),
    responses={
        200: openapi.Response(
            description="Logout successful",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )
        ),
        400: openapi.Response(description="Invalid token"),
        401: openapi.Response(description="Authentication required")
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    try:
        refresh_token = request.data["refresh"]
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(generics.GenericAPIView):
    """
    Send OTP to user's email for password reset.
    """
    serializer_class = ForgotPasswordSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Send OTP to email for password reset",
        request_body=ForgotPasswordSerializer,
        responses={
            200: openapi.Response(
                description="OTP sent successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'otp': openapi.Schema(type=openapi.TYPE_STRING, description='4-digit OTP for testing purposes'),
                        'expires_at': openapi.Schema(type=openapi.TYPE_STRING, format='datetime'),
                        'valid_for': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: openapi.Response(description="Email not found or invalid"),
        }
    )
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        
        return Response({
            'message': 'OTP has been sent to your email address. Please check your inbox.',
            'otp': result['otp'],  # Include OTP for testing purposes
            'expires_at': result['expires_at'],
            'valid_for': '5 minutes'
        }, status=status.HTTP_200_OK)


class VerifyOTPView(generics.GenericAPIView):
    """
    Verify OTP sent to user's email.
    """
    serializer_class = VerifyOTPSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Verify 4-digit OTP for password reset (OTP expires in 5 minutes)",
        request_body=VerifyOTPSerializer,
        responses={
            200: openapi.Response(
                description="OTP verified successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: openapi.Response(description="Invalid or expired OTP"),
        }
    )
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        return Response({
            'message': 'OTP verified successfully. You can now reset your password.'
        }, status=status.HTTP_200_OK)


class ResetPasswordView(generics.GenericAPIView):
    """
    Reset user's password using verified OTP.
    """
    serializer_class = ResetPasswordSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Reset password using verified 4-digit OTP (OTP expires in 5 minutes)",
        request_body=ResetPasswordSerializer,
        responses={ 
            200: openapi.Response(
                description="Password reset successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: openapi.Response(description="Invalid OTP or password validation errors"),
        }
    )
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Password has been reset successfully. You can now login with your new password.'
        }, status=status.HTTP_200_OK)


class ChildrenListCreateView(generics.ListCreateAPIView):
    """
    Get list of user's children or add a new child.
    """
    serializer_class = ChildrenSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get list of current user's children",
        responses={
            200: openapi.Response(
                description="Children list retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'name': openapi.Schema(type=openapi.TYPE_STRING),
                            'age': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'created_at': openapi.Schema(type=openapi.TYPE_STRING, format='datetime'),
                            'updated_at': openapi.Schema(type=openapi.TYPE_STRING, format='datetime'),
                        }
                    )
                )
            ),
            401: openapi.Response(description="Authentication required")
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Add a new child",
        request_body=ChildrenSerializer,
        responses={
            201: openapi.Response(
                description="Child added successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'name': openapi.Schema(type=openapi.TYPE_STRING),
                        'age': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'created_at': openapi.Schema(type=openapi.TYPE_STRING, format='datetime'),
                        'updated_at': openapi.Schema(type=openapi.TYPE_STRING, format='datetime'),
                    }
                )
            ),
            400: openapi.Response(description="Validation errors"),
            401: openapi.Response(description="Authentication required")
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def get_queryset(self):
        return Children.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


class ChildrenDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete a specific child.
    """
    serializer_class = ChildrenSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get details of a specific child",
        responses={
            200: openapi.Response(
                description="Child details retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'name': openapi.Schema(type=openapi.TYPE_STRING),
                        'age': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'created_at': openapi.Schema(type=openapi.TYPE_STRING, format='datetime'),
                        'updated_at': openapi.Schema(type=openapi.TYPE_STRING, format='datetime'),
                    }
                )
            ),
            404: openapi.Response(description="Child not found"),
            401: openapi.Response(description="Authentication required")
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Update a child's information",
        request_body=ChildrenSerializer,
        responses={
            200: openapi.Response(
                description="Child updated successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'name': openapi.Schema(type=openapi.TYPE_STRING),
                        'age': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'created_at': openapi.Schema(type=openapi.TYPE_STRING, format='datetime'),
                        'updated_at': openapi.Schema(type=openapi.TYPE_STRING, format='datetime'),
                    }
                )
            ),
            400: openapi.Response(description="Validation errors"),
            404: openapi.Response(description="Child not found"),
            401: openapi.Response(description="Authentication required")
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Delete a child",
        responses={
            204: openapi.Response(description="Child deleted successfully"),
            404: openapi.Response(description="Child not found"),
            401: openapi.Response(description="Authentication required")
        }
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def get_queryset(self):
        return Children.objects.filter(profile=self.request.user.profile)


class ChangePasswordView(generics.UpdateAPIView):
    """
    Change user's password.
    """
    serializer_class = UserchangePasswordSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Change user password",
        request_body=UserchangePasswordSerializer,
        responses={
            200: openapi.Response(
                description="Password changed successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'detail': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: openapi.Response(description="Validation errors"),
            401: openapi.Response(description="Authentication required")
        }
    )

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        # Just save the serializer; UpdateAPIView will handle the response.
        serializer.save()

    def patch(self, request, *args, **kwargs):
        """Handle partial update (PATCH) to change password with a custom response body."""
        partial = True
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Optionally, invalidate tokens/log out sessions here
        return Response({
            'message': 'Password changed successfully',
            'detail': 'You have been logged out from all devices for security'
        }, status=status.HTTP_200_OK)