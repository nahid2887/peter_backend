
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Conversation, GroupMembership, Message, UserStatus
from .serializers import (
    CreateGroupSerializer, AddGroupMemberSerializer, RemoveGroupMemberSerializer,
    ChangeGroupNameSerializer, PromoteToAdminSerializer, ConversationListSerializer,
    GroupParticipantSerializer, ConversationDetailSerializer
)

User = get_user_model()


@swagger_auto_schema(
    method='post',
    operation_description="Create a new group chat",
    request_body=CreateGroupSerializer,
    responses={
        201: ConversationListSerializer,
        400: 'Bad Request',
        403: 'Forbidden'
    },
    tags=['Group Management']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_group(request):
    """
    Create a new group chat
    """
    serializer = CreateGroupSerializer(data=request.data)
    
    if serializer.is_valid():
        with transaction.atomic():
            # Create the conversation
            conversation = Conversation.objects.create(
                name=serializer.validated_data['name'],
                is_group=True,
                created_by=request.user
            )
            
            # Add creator as admin
            GroupMembership.objects.create(
                conversation=conversation,
                user=request.user,
                role='admin',
                added_by=request.user
            )
            
            # Add other participants as members
            participant_ids = serializer.validated_data['participant_ids']
            participants = User.objects.filter(id__in=participant_ids)
            
            for participant in participants:
                if participant != request.user:  # Don't add creator twice
                    conversation.add_participant(participant, added_by=request.user, role='member')
            
            # Create welcome message
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=f"Group '{conversation.name}' created",
                message_type='system'
            )
            
            return Response(
                ConversationListSerializer(conversation, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_description="Get group details with participants and their roles",
    responses={
        200: ConversationDetailSerializer,
        404: 'Not Found'
    },
    tags=['Group Management']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_group_details(request, conversation_id):
    """
    Get group details with participants and their roles
    """
    conversation = get_object_or_404(Conversation, id=conversation_id, is_group=True)
    
    # Check if user is a member of the group
    if not GroupMembership.objects.filter(
        conversation=conversation,
        user=request.user,
        is_active=True
    ).exists():
        return Response(
            {"error": "You are not a member of this group"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get group details with participants
    serializer = ConversationDetailSerializer(conversation, context={'request': request})
    response_data = serializer.data
    
    # Add participant details with roles
    active_participants = conversation.get_active_participants()
    response_data['participants'] = GroupParticipantSerializer(
        active_participants,
        many=True,
        context={
            'request': request,
            'conversation': conversation,
            'current_user': request.user
        }
    ).data
    
    # Add user's permissions
    try:
        user_membership = GroupMembership.objects.get(
            conversation=conversation,
            user=request.user,
            is_active=True
        )
        response_data['user_permissions'] = {
            'can_add_members': user_membership.can_add_members(),
            'can_remove_members': user_membership.can_remove_members(),
            'can_change_name': user_membership.can_change_group_name(),
            'can_leave': True,
            'is_admin': user_membership.is_admin()
        }
    except GroupMembership.DoesNotExist:
        response_data['user_permissions'] = {
            'can_add_members': False,
            'can_remove_members': False,
            'can_change_name': False,
            'can_leave': False,
            'is_admin': False
        }
    
    return Response(response_data)


@swagger_auto_schema(
    method='post',
    operation_description="Add members to a group",
    request_body=AddGroupMemberSerializer,
    responses={
        200: 'Success',
        400: 'Bad Request',
        403: 'Forbidden',
        404: 'Not Found'
    },
    tags=['Group Management']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def add_group_members(request, conversation_id):
    """
    Add members to a group (only admins can do this)
    """
    conversation = get_object_or_404(Conversation, id=conversation_id, is_group=True)
    
    # Check if user is an admin of the group
    try:
        user_membership = GroupMembership.objects.get(
            conversation=conversation,
            user=request.user,
            is_active=True
        )
        if not user_membership.can_add_members():
            return Response(
                {"error": "Only admins can add members to the group"},
                status=status.HTTP_403_FORBIDDEN
            )
    except GroupMembership.DoesNotExist:
        return Response(
            {"error": "You are not a member of this group"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = AddGroupMemberSerializer(data=request.data)
    
    if serializer.is_valid():
        user_ids = serializer.validated_data['user_ids']
        users_to_add = User.objects.filter(id__in=user_ids)
        
        added_users = []
        already_members = []
        
        with transaction.atomic():
            for user in users_to_add:
                # Check if user is already an active member
                existing_membership = GroupMembership.objects.filter(
                    conversation=conversation,
                    user=user,
                    is_active=True
                ).first()
                
                if existing_membership:
                    already_members.append(user.full_name)
                else:
                    conversation.add_participant(user, added_by=request.user, role='member')
                    added_users.append(user.full_name)
        
        response_data = {
            'message': 'Members added successfully',
            'added_users': added_users,
            'already_members': already_members
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_description="Remove a member from a group",
    request_body=RemoveGroupMemberSerializer,
    responses={
        200: 'Success',
        400: 'Bad Request',
        403: 'Forbidden',
        404: 'Not Found'
    },
    tags=['Group Management']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def remove_group_member(request, conversation_id):
    """
    Remove a member from a group (only admins can do this)
    """
    conversation = get_object_or_404(Conversation, id=conversation_id, is_group=True)
    
    # Check if user is an admin of the group
    try:
        user_membership = GroupMembership.objects.get(
            conversation=conversation,
            user=request.user,
            is_active=True
        )
        if not user_membership.can_remove_members():
            return Response(
                {"error": "Only admins can remove members from the group"},
                status=status.HTTP_403_FORBIDDEN
            )
    except GroupMembership.DoesNotExist:
        return Response(
            {"error": "You are not a member of this group"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = RemoveGroupMemberSerializer(data=request.data)
    
    if serializer.is_valid():
        user_id = serializer.validated_data['user_id']
        user_to_remove = get_object_or_404(User, id=user_id)
        
        # Don't allow removing the group creator
        if user_to_remove == conversation.created_by:
            return Response(
                {"error": "Cannot remove the group creator"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Don't allow removing yourself through this endpoint
        if user_to_remove == request.user:
            return Response(
                {"error": "Use the leave group endpoint to leave the group"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if target user is a member
        try:
            target_membership = GroupMembership.objects.get(
                conversation=conversation,
                user=user_to_remove,
                is_active=True
            )
            
            # Admins can only remove members, not other admins (unless they're the creator)
            if target_membership.role == 'admin' and conversation.created_by != request.user:
                return Response(
                    {"error": "Only the group creator can remove other admins"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            conversation.remove_participant(user_to_remove, removed_by=request.user)
            
            return Response(
                {"message": f"{user_to_remove.full_name} has been removed from the group"},
                status=status.HTTP_200_OK
            )
            
        except GroupMembership.DoesNotExist:
            return Response(
                {"error": "User is not a member of this group"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_description="Leave a group",
    responses={
        200: 'Success',
        403: 'Forbidden',
        404: 'Not Found'
    },
    tags=['Group Management']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def leave_group(request, conversation_id):
    """
    Leave a group
    """
    conversation = get_object_or_404(Conversation, id=conversation_id, is_group=True)
    
    # Check if user is a member of the group
    try:
        user_membership = GroupMembership.objects.get(
            conversation=conversation,
            user=request.user,
            is_active=True
        )
        
        # Group creator cannot leave the group
        if request.user == conversation.created_by:
            return Response(
                {"error": "Group creator cannot leave the group. Transfer ownership first or delete the group."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_membership.leave_group()
        
        return Response(
            {"message": "You have left the group"},
            status=status.HTTP_200_OK
        )
        
    except GroupMembership.DoesNotExist:
        return Response(
            {"error": "You are not a member of this group"},
            status=status.HTTP_403_FORBIDDEN
        )


@swagger_auto_schema(
    method='post',
    operation_description="Change group name",
    request_body=ChangeGroupNameSerializer,
    responses={
        200: 'Success',
        400: 'Bad Request',
        403: 'Forbidden',
        404: 'Not Found'
    },
    tags=['Group Management']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def change_group_name(request, conversation_id):
    """
    Change group name (only admins can do this)
    """
    conversation = get_object_or_404(Conversation, id=conversation_id, is_group=True)
    
    # Check if user is an admin of the group
    try:
        user_membership = GroupMembership.objects.get(
            conversation=conversation,
            user=request.user,
            is_active=True
        )
        if not user_membership.can_change_group_name():
            return Response(
                {"error": "Only admins can change the group name"},
                status=status.HTTP_403_FORBIDDEN
            )
    except GroupMembership.DoesNotExist:
        return Response(
            {"error": "You are not a member of this group"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = ChangeGroupNameSerializer(data=request.data)
    
    if serializer.is_valid():
        new_name = serializer.validated_data['name']
        conversation.change_group_name(new_name, request.user)
        
        return Response(
            {"message": f"Group name changed to '{new_name}'"},
            status=status.HTTP_200_OK
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_description="Promote a member to admin",
    request_body=PromoteToAdminSerializer,
    responses={
        200: 'Success',
        400: 'Bad Request',
        403: 'Forbidden',
        404: 'Not Found'
    },
    tags=['Group Management']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def promote_to_admin(request, conversation_id):
    """
    Promote a member to admin (only group creator can do this)
    """
    conversation = get_object_or_404(Conversation, id=conversation_id, is_group=True)
    
    # Only group creator can promote members to admin
    if request.user != conversation.created_by:
        return Response(
            {"error": "Only the group creator can promote members to admin"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = PromoteToAdminSerializer(data=request.data)
    
    if serializer.is_valid():
        user_id = serializer.validated_data['user_id']
        user_to_promote = get_object_or_404(User, id=user_id)
        
        # Check if target user is a member
        try:
            target_membership = GroupMembership.objects.get(
                conversation=conversation,
                user=user_to_promote,
                is_active=True
            )
            
            if target_membership.role == 'admin':
                return Response(
                    {"error": "User is already an admin"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            conversation.promote_to_admin(user_to_promote, request.user)
            
            return Response(
                {"message": f"{user_to_promote.full_name} has been promoted to admin"},
                status=status.HTTP_200_OK
            )
            
        except GroupMembership.DoesNotExist:
            return Response(
                {"error": "User is not a member of this group"},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_description="Get all group members with their details and roles",
    responses={
        200: 'Success - Group members list',
        403: 'Forbidden - Not a group member',
        404: 'Group not found'
    },
    tags=['Group Management']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_group_members(request, conversation_id):
    """
    Get all group members with their details and roles
    """
    conversation = get_object_or_404(Conversation, id=conversation_id, is_group=True)
    
    # Check if user is a member of the group
    user_membership = GroupMembership.objects.filter(
        conversation=conversation,
        user=request.user,
        is_active=True
    ).first()
    
    if not user_membership:
        return Response(
            {"error": "You are not a member of this group"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get all active members with their membership details
    members_data = []
    active_memberships = GroupMembership.objects.filter(
        conversation=conversation,
        is_active=True
    ).select_related('user', 'added_by').order_by('-role', 'joined_at')  # Admins first, then by join date
    
    for membership in active_memberships:
        user = membership.user
        
        # Get user's online status
        is_online = False
        try:
            is_online = user.status.is_online()
        except:
            pass
        
        # Get profile photo URL
        profile_photo_url = None
        if user.profile_photo:
            profile_photo_url = request.build_absolute_uri(user.profile_photo.url)
        
        member_data = {
            'id': user.id,
            'full_name': user.full_name,
            'email': user.email,
            'profile_photo_url': profile_photo_url,
            'role': membership.get_role_display(),
            'role_code': membership.role,  # admin/member
            'joined_at': membership.joined_at.isoformat(),
            'is_online': is_online,
            'added_by': {
                'id': membership.added_by.id,
                'full_name': membership.added_by.full_name,
                'email': membership.added_by.email
            } if membership.added_by else None,
            'can_be_removed': user_membership.can_remove_members() and user != request.user,  # Can't remove yourself
            'is_current_user': user == request.user
        }
        
        members_data.append(member_data)
    
    # Group information
    group_info = {
        'id': str(conversation.id),
        'name': conversation.name,
        'member_count': len(members_data),
        'created_at': conversation.created_at.isoformat(),
        'created_by': {
            'id': conversation.created_by.id,
            'full_name': conversation.created_by.full_name,
            'email': conversation.created_by.email
        } if conversation.created_by else None
    }
    
    # Current user's permissions
    user_permissions = {
        'can_add_members': user_membership.can_add_members(),
        'can_remove_members': user_membership.can_remove_members(),
        'can_change_name': user_membership.can_change_group_name(),
        'can_promote_members': user_membership.is_admin(),
        'is_admin': user_membership.is_admin(),
        'can_leave': True
    }
    
    response_data = {
        'group_info': group_info,
        'members': members_data,
        'user_permissions': user_permissions
    }
    
    return Response(response_data, status=status.HTTP_200_OK)



# Group delete endpoint: Only group admin can delete the group
@swagger_auto_schema(
    method='delete',
    operation_description="Delete a group conversation (only group admin can delete)",
    responses={
        200: 'Success',
        403: 'Forbidden',
        404: 'Not Found'
    },
    tags=['Group Management']
)
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_group(request, conversation_id):
    """
    Delete a group conversation (only group admin can delete)
    """
    conversation = get_object_or_404(Conversation, id=conversation_id, is_group=True)
    # Optimize: Only query for admin membership
    admin_membership = GroupMembership.objects.select_related('user').filter(
        conversation=conversation,
        user=request.user,
        is_active=True,
        role='admin'
    ).first()
    if not admin_membership:
        return Response({
            'error': 'Only group admin can delete the group conversation.'
        }, status=status.HTTP_403_FORBIDDEN)
    conversation_name = str(conversation)
    conversation.delete()
    return Response({
        'success': True,
        'message': f'Group conversation "{conversation_name}" has been deleted successfully.'
    }, status=status.HTTP_200_OK)
