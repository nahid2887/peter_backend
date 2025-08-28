from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from urllib.parse import parse_qs
import jwt
from django.conf import settings

User = get_user_model()


@database_sync_to_async
def get_user_by_id(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    def __init__(self, inner):
        super().__init__(inner)

    async def __call__(self, scope, receive, send):
        # Get token from query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        
        token = None
        if 'token' in query_params:
            token = query_params['token'][0]
        
        # Try to get token from headers if not in query params
        if not token:
            headers = dict(scope.get('headers', []))
            auth_header = headers.get(b'authorization', b'').decode()
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        # Authenticate user with token
        scope['user'] = AnonymousUser()
        
        if token:
            try:
                # Validate the token
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                scope['user'] = await get_user_by_id(user_id)
            except (InvalidToken, TokenError, KeyError) as e:
                # Token is invalid, user remains anonymous
                pass

        return await super().__call__(scope, receive, send)