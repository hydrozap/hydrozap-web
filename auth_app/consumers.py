import json
from channels.generic.websocket import AsyncWebsocketConsumer
import asyncio
import firebase_admin
from firebase_admin import db
from .firebase import get_firebase_ref
import datetime

class DeviceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_group_name = f'devices_{self.user_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Start the background task to fetch devices
        self.fetch_task = asyncio.create_task(self.periodic_device_fetch())
    
    async def disconnect(self, close_code):
        # Cancel the background task when disconnecting
        if hasattr(self, 'fetch_task'):
            self.fetch_task.cancel()
            
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """
        Handle incoming messages from WebSocket clients
        """
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')
        
        if message_type == 'fetch_devices':
            # Manually trigger device fetch
            await self.fetch_and_send_devices()
    
    async def periodic_device_fetch(self):
        """
        Periodically fetch devices and send updates
        """
        try:
            while True:
                await self.fetch_and_send_devices()
                # Wait for 10 seconds before fetching again
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            # Task was cancelled, clean up
            pass
    
    async def fetch_and_send_devices(self):
        """
        Fetch devices from Firebase and send to the client
        """
        try:
            # Get devices data for the user
            ref = get_firebase_ref()
            devices_ref = ref.child('devices')
            devices_snapshot = devices_ref.order_by_child('user_id').equal_to(self.user_id).get()
            
            devices_data = {}
            if devices_snapshot:
                devices_data = devices_snapshot
            
            # Send the devices data to the WebSocket
            await self.send(text_data=json.dumps({
                'type': 'devices_update',
                'timestamp': datetime.datetime.now().isoformat(),
                'devices': devices_data
            }))
            
        except Exception as e:
            # Log error and send error message
            print(f"Error fetching devices: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Failed to fetch devices: {str(e)}"
            }))

    async def devices_update(self, event):
        """
        Receive device updates from group and forward to WebSocket
        """
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event))

class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_group_name = f'dashboard_{self.user_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Start the background task to fetch dashboard counts
        self.fetch_task = asyncio.create_task(self.periodic_dashboard_fetch())
    
    async def disconnect(self, close_code):
        # Cancel the background task when disconnecting
        if hasattr(self, 'fetch_task'):
            self.fetch_task.cancel()
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """
        Handle incoming messages from WebSocket clients
        """
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')
        
        if message_type == 'fetch_dashboard':
            # Manually trigger dashboard fetch
            await self.fetch_and_send_dashboard()
    
    async def periodic_dashboard_fetch(self):
        """
        Periodically fetch dashboard counts and send updates
        """
        try:
            while True:
                await self.fetch_and_send_dashboard()
                # Wait for 10 seconds before fetching again
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            # Task was cancelled, clean up
            pass
    
    async def fetch_and_send_dashboard(self):
        """
        Fetch dashboard counts from Firebase and send to the client
        """
        try:
            ref = get_firebase_ref()
            # Device count
            devices_ref = ref.child('devices')
            devices_snapshot = devices_ref.order_by_child('user_id').equal_to(self.user_id).get()
            device_count = len(devices_snapshot) if devices_snapshot else 0
            
            # Alert count
            alerts_ref = ref.child(f'alerts/{self.user_id}')
            alerts_snapshot = alerts_ref.get()
            alert_count = len(alerts_snapshot) if alerts_snapshot else 0
            
            # Grow count (only active grows)
            grows_ref = ref.child('grows')
            grows_snapshot = grows_ref.get()
            grow_count = 0
            if grows_snapshot:
                grow_count = sum(
                    1 for grow in grows_snapshot.values()
                    if grow.get('user_id') == self.user_id and grow.get('status') == 'active'
                )
            
            # Send the dashboard counts to the WebSocket
            await self.send(text_data=json.dumps({
                'type': 'dashboard_update',
                'timestamp': datetime.datetime.now().isoformat(),
                'device_count': device_count,
                'alert_count': alert_count,
                'grow_count': grow_count
            }))
        except Exception as e:
            print(f"Error fetching dashboard counts: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Failed to fetch dashboard counts: {str(e)}"
            }))

    async def dashboard_update(self, event):
        """
        Receive dashboard updates from group and forward to WebSocket
        """
        await self.send(text_data=json.dumps(event)) 