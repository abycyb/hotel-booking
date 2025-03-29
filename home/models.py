from django.contrib.auth.models import User
from django.db import models
import uuid
from django.db.models import Sum



class BaseModel(models.Model):
    uid = models.UUIDField(default=uuid.uuid4   , editable=False , primary_key=True)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering=['uid']


class Amenities(BaseModel):
    amenity_name = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.amenity_name

class Hotel(BaseModel):
    hotel_name = models.CharField(max_length=100)
    hotel_price = models.IntegerField()
    description = models.TextField()
    amenities = models.ManyToManyField(Amenities)
    room_count = models.IntegerField(default=10)
    max_occupancy_per_room = models.IntegerField(default=2)

    def __str__(self) -> str:
        return self.hotel_name

    def available_rooms(self, start_date, end_date):
        booked_rooms = HotelBooking.objects.filter(
            hotel=self,
            start_date__lt=end_date,
            end_date__gt=start_date
        ).aggregate(total_rooms=Sum('rooms_reserved'))['total_rooms'] or 0
        return self.room_count - booked_rooms


class HotelImages(BaseModel):
    hotel= models.ForeignKey(Hotel ,related_name="images", on_delete=models.CASCADE)
    images = models.ImageField(upload_to="hotels")



class HotelBooking(BaseModel):
    hotel = models.ForeignKey(Hotel, related_name="hotel_bookings", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="user_bookings", on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    booking_type = models.CharField(
        max_length=100, 
        choices=(('Pre Paid', 'Pre Paid'), ('Post Paid', 'Post Paid'))
    )
    occupants = models.IntegerField(default=1)
    rooms_reserved = models.IntegerField(default=1)
    
    def __str__(self) -> str:
        return f'{self.hotel.hotel_name} {self.start_date} to {self.end_date}'
    
    def save(self, *args, **kwargs):
        """Auto-calculate rooms needed before saving"""
        if not self.rooms_reserved:
            self.rooms_reserved = (self.occupants + self.hotel.max_occupancy_per_room - 1) // self.hotel.max_occupancy_per_room
        super().save(*args, **kwargs)
    
    @property
    def total_price(self):
        """Calculate total price with room count"""
        nights = (self.end_date - self.start_date).days
        return self.hotel.hotel_price * nights * self.rooms_reserved

    def get_nights_count(self):
        return (self.end_date - self.start_date).days
