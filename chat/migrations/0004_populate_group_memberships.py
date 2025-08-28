from django.db import migrations


def populate_group_memberships(apps, schema_editor):
    """
    Populate GroupMembership for existing conversations
    """
    Conversation = apps.get_model('chat', 'Conversation')
    GroupMembership = apps.get_model('chat', 'GroupMembership')
    
    for conversation in Conversation.objects.all():
        participants = conversation.participants.all()
        
        for participant in participants:
            # Create GroupMembership for each participant
            # If it's the creator, make them admin; otherwise, make them member
            role = 'admin' if participant == conversation.created_by else 'member'
            
            GroupMembership.objects.get_or_create(
                conversation=conversation,
                user=participant,
                defaults={
                    'role': role,
                    'added_by': conversation.created_by,
                    'is_active': True
                }
            )


def reverse_populate_group_memberships(apps, schema_editor):
    """
    Reverse the population by clearing GroupMembership
    """
    GroupMembership = apps.get_model('chat', 'GroupMembership')
    GroupMembership.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_create_group_membership'),
    ]

    operations = [
        migrations.RunPython(
            populate_group_memberships,
            reverse_populate_group_memberships,
        ),
    ]
