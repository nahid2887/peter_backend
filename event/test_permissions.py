"""
Test the event API permissions
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Event, EventResponse

User = get_user_model()


class EventPermissionTests(APITestCase):
    
    def setUp(self):
        # Create test users
        self.host_user = User.objects.create_user(
            email='host@example.com',
            full_name='Host User',
            password='testpass123'
        )
        
        self.normal_user = User.objects.create_user(
            email='normal@example.com', 
            full_name='Normal User',
            password='testpass123'
        )
        
        # Create a test event
        self.event = Event.objects.create(
            title='Test Event',
            description='Test Description',
            date='2025-08-15',
            start_time='14:00:00',
            location='Test Location',
            event_type='open',
            host=self.host_user
        )
    
    def test_event_creator_can_update(self):
        """Test that event creator can update their event"""
        self.client.force_authenticate(user=self.host_user)
        
        url = reverse('event-detail', kwargs={'pk': self.event.pk})
        data = {'title': 'Updated Title'}
        
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'Updated Title')
    
    def test_event_creator_can_delete(self):
        """Test that event creator can delete their event"""
        self.client.force_authenticate(user=self.host_user)
        
        url = reverse('event-detail', kwargs={'pk': self.event.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())
    
    def test_normal_user_cannot_update_event(self):
        """Test that normal user cannot update someone else's event"""
        self.client.force_authenticate(user=self.normal_user)
        
        url = reverse('event-detail', kwargs={'pk': self.event.pk})
        data = {'title': 'Hacked Title'}
        
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, 'Test Event')  # Should not be changed
    
    def test_normal_user_cannot_delete_event(self):
        """Test that normal user cannot delete someone else's event"""
        self.client.force_authenticate(user=self.normal_user)
        
        url = reverse('event-detail', kwargs={'pk': self.event.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())
    
    def test_normal_user_can_respond_to_event(self):
        """Test that normal user can respond to events"""
        self.client.force_authenticate(user=self.normal_user)
        
        url = reverse('event-respond', kwargs={'pk': self.event.pk})
        data = {'response': 'going'}
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check response was created
        self.assertTrue(
            EventResponse.objects.filter(
                event=self.event,
                user=self.normal_user,
                response='going'
            ).exists()
        )
    
    def test_normal_user_can_view_open_events(self):
        """Test that normal user can view open events"""
        self.client.force_authenticate(user=self.normal_user)
        
        url = reverse('event-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # Should see the open event
    
    def test_unauthenticated_user_cannot_access_events(self):
        """Test that unauthenticated users cannot access events"""
        url = reverse('event-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
