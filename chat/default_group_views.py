from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import DefaultGroup, DefaultGroupMembership, Conversation
from .serializers import DefaultGroupSerializer, ConversationSerializer

User = get_user_model()


@swagger_auto_schema(
    method='get',
    operation_description="Get list of all available default groups",
    responses={
        200: openapi.Response(
            description="List of default groups",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'name': openapi.Schema(type=openapi.TYPE_STRING),
                        'description': openapi.Schema(type=openapi.TYPE_STRING),
                        'member_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'is_member': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'conversation_id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid'),
                    }
                )
            )
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_default_groups(request):
    """
    Get list of all available default groups with user membership status
    """
    try:
        groups = DefaultGroup.objects.filter(is_active=True)
        groups_data = []
        
        for group in groups:
            is_member = DefaultGroupMembership.objects.filter(
                default_group=group,
                user=request.user,
                is_active=True
            ).exists()
            
            groups_data.append({
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'member_count': group.get_member_count(),
                'is_member': is_member,
                'conversation_id': str(group.conversation.id) if group.conversation else None,
                'created_at': group.created_at.isoformat(),
                'updated_at': group.updated_at.isoformat(),
            })
        
        return Response({
            'success': True,
            'groups': groups_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_description="Join one or multiple default groups",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['group_ids'],
        properties={
            'group_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                description="Array of default group IDs to join"
            )
        }
    ),
    responses={
        200: openapi.Response(
            description="Successfully joined groups",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'joined_groups': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    ),
                    'already_member': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_STRING)
                    )
                }
            )
        ),
        400: openapi.Response(description="Bad request"),
        404: openapi.Response(description="Group not found")
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_default_groups(request):
    """
    Join one or multiple default groups
    """
    try:
        group_ids = request.data.get('group_ids', [])
        
        if not group_ids:
            return Response({
                'success': False,
                'error': 'group_ids is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(group_ids, list):
            group_ids = [group_ids]
        
        joined_groups = []
        already_member = []
        errors = []
        
        with transaction.atomic():
            for group_id in group_ids:
                try:
                    group = DefaultGroup.objects.get(id=group_id, is_active=True)
                    
                    # Check if already a member
                    existing_membership = DefaultGroupMembership.objects.filter(
                        default_group=group,
                        user=request.user,
                        is_active=True
                    ).first()
                    
                    if existing_membership:
                        already_member.append(group.name)
                        continue
                    
                    # Add user to the group
                    group.add_user(request.user)
                    
                    joined_groups.append({
                        'id': group.id,
                        'name': group.name,
                        'conversation_id': str(group.conversation.id) if group.conversation else None
                    })
                    
                except DefaultGroup.DoesNotExist:
                    errors.append(f"Group with ID {group_id} not found")
                except Exception as e:
                    errors.append(f"Error joining group {group_id}: {str(e)}")
        
        response_data = {
            'success': True,
            'message': f'Successfully joined {len(joined_groups)} group(s)',
            'joined_groups': joined_groups
        }
        
        if already_member:
            response_data['already_member'] = already_member
        
        if errors:
            response_data['errors'] = errors
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_description="Leave one or multiple default groups",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['group_ids'],
        properties={
            'group_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                description="Array of default group IDs to leave"
            )
        }
    ),
    responses={
        200: openapi.Response(
            description="Successfully left groups",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'left_groups': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    ),
                    'not_member': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_STRING)
                    )
                }
            )
        ),
        400: openapi.Response(description="Bad request"),
        404: openapi.Response(description="Group not found")
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_default_groups(request):
    """
    Leave one or multiple default groups
    """
    try:
        group_ids = request.data.get('group_ids', [])
        
        if not group_ids:
            return Response({
                'success': False,
                'error': 'group_ids is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(group_ids, list):
            group_ids = [group_ids]
        
        left_groups = []
        not_member = []
        errors = []
        
        with transaction.atomic():
            for group_id in group_ids:
                try:
                    group = DefaultGroup.objects.get(id=group_id, is_active=True)
                    
                    # Check if user is a member
                    membership = DefaultGroupMembership.objects.filter(
                        default_group=group,
                        user=request.user,
                        is_active=True
                    ).first()
                    
                    if not membership:
                        not_member.append(group.name)
                        continue
                    
                    # Leave the group
                    membership.leave()
                    
                    left_groups.append({
                        'id': group.id,
                        'name': group.name,
                        'conversation_id': str(group.conversation.id) if group.conversation else None
                    })
                    
                except DefaultGroup.DoesNotExist:
                    errors.append(f"Group with ID {group_id} not found")
                except Exception as e:
                    errors.append(f"Error leaving group {group_id}: {str(e)}")
        
        response_data = {
            'success': True,
            'message': f'Successfully left {len(left_groups)} group(s)',
            'left_groups': left_groups
        }
        
        if not_member:
            response_data['not_member'] = not_member
        
        if errors:
            response_data['errors'] = errors
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_description="Get user's joined default groups",
    responses={
        200: openapi.Response(
            description="List of user's joined default groups",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'groups': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    )
                }
            )
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_default_groups(request):
    """
    Get list of default groups that the current user has joined
    """
    try:
        memberships = DefaultGroupMembership.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('default_group')
        
        groups_data = []
        for membership in memberships:
            group = membership.default_group
            groups_data.append({
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'member_count': group.get_member_count(),
                'conversation_id': str(group.conversation.id) if group.conversation else None,
                'joined_at': membership.joined_at.isoformat(),
            })
        
        return Response({
            'success': True,
            'groups': groups_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_description="Get members of a default group",
    responses={
        200: openapi.Response(
            description="List of group members",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'group': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'members': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(type=openapi.TYPE_OBJECT)
                    )
                }
            )
        ),
        404: openapi.Response(description="Group not found")
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_default_group_members(request, group_id):
    """
    Get list of members in a default group
    """
    try:
        group = get_object_or_404(DefaultGroup, id=group_id, is_active=True)
        
        # Check if user is a member of this group
        is_member = DefaultGroupMembership.objects.filter(
            default_group=group,
            user=request.user,
            is_active=True
        ).exists()
        
        if not is_member:
            return Response({
                'success': False,
                'error': 'You are not a member of this group'
            }, status=status.HTTP_403_FORBIDDEN)
        
        memberships = DefaultGroupMembership.objects.filter(
            default_group=group,
            is_active=True
        ).select_related('user')
        
        members_data = []
        for membership in memberships:
            user = membership.user
            members_data.append({
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'email': user.email,
                'joined_at': membership.joined_at.isoformat(),
            })
        
        return Response({
            'success': True,
            'group': {
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'member_count': len(members_data)
            },
            'members': members_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
