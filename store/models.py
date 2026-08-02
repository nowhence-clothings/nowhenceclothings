from django.db import models
from django.conf import settings
from django.utils.text import slugify


class HeroSection(models.Model):
    """Hero background — supports both image and video."""
    MEDIA_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]

    title = models.CharField(max_length=100, default='Nowhence Clothings')
    subtitle = models.CharField(max_length=200, default='Exquisite Elegance Redefined')
    media_type = models.CharField(max_length=5, choices=MEDIA_CHOICES, default='image', help_text='Choose whether the background is an image or video')
    background_image = models.ImageField(upload_to='hero/', blank=True, null=True, help_text='Upload a background image (used when media type is Image)')
    background_video = models.FileField(upload_to='hero/videos/', blank=True, null=True, help_text='Upload a background video — MP4 recommended (used when media type is Video)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Hero Section'
        verbose_name_plural = 'Hero Section'
        ordering = ['-created_at']

    def __str__(self):
        media = self.get_media_type_display()
        return f'{self.title} [{media}] ({"Active" if self.is_active else "Inactive"})'

    def save(self, *args, **kwargs):
        # Ensure only one hero is active
        if self.is_active:
            HeroSection.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @property
    def is_video(self):
        return bool(self.background_video)

    @property
    def is_image(self):
        return not self.is_video and bool(self.background_image)


class FeaturedCollection(models.Model):
    """Cards in the Featured Collections section."""
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Original MRP')
    discount_percent = models.PositiveIntegerField(default=0, help_text='Discount percentage (0-99). Leave 0 for no discount.')
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Final price after discount. Auto-calculated if left blank.')
    image = models.ImageField(upload_to='featured/')
    display_order = models.PositiveIntegerField(default=0, help_text='Lower number = appears first')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Featured Collection'
        verbose_name_plural = 'Featured Collections'
        ordering = ['display_order', '-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto-calculate discounted price whenever discount is set
        if self.discount_percent and self.discount_percent > 0:
            self.discounted_price = round(self.price * (1 - self.discount_percent / 100), 2)
        elif self.discount_percent == 0:
            self.discounted_price = None
        super().save(*args, **kwargs)

    @property
    def formatted_price(self):
        return f'₹{self.price:,.0f}'

    @property
    def formatted_discounted_price(self):
        if self.discounted_price:
            return f'₹{self.discounted_price:,.0f}'
        return ''

    @property
    def has_discount(self):
        return self.discount_percent > 0 and self.discounted_price is not None


class ShowcaseProduct(models.Model):
    """Products in the Shop page."""
    CATEGORY_CHOICES = [
        ('bridal', 'Bridal'),
        ('designer', 'Designer'),
        ('festival', 'Festival'),
        ('party', 'Party Wear'),
        ('casual', 'Casual'),
    ]

    SIZE_CHOICES = [
        ('XS', 'XS'),
        ('S', 'S'),
        ('M', 'M'),
        ('L', 'L'),
        ('XL', 'XL'),
        ('XXL', 'XXL'),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True, help_text='Auto-generated from name if left blank')
    description = models.TextField(blank=True, default='', help_text='Detailed product description')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='bridal')
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Original MRP')
    discount_percent = models.PositiveIntegerField(default=0, help_text='Discount percentage (0-99). Leave 0 for no discount.')
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text='Final price after discount. Auto-calculated if left blank.')
    image = models.ImageField(upload_to='showcase/')
    available_sizes = models.CharField(max_length=100, blank=True, default='S,M,L,XL', help_text='Comma-separated sizes e.g. S,M,L,XL,XXL')
    fabric = models.CharField(max_length=100, blank=True, default='', help_text='e.g. Pure Silk, Georgette')
    care_instructions = models.CharField(max_length=255, blank=True, default='Dry clean only', help_text='Care instructions')
    stock_quantity = models.PositiveIntegerField(default=100, help_text='Available stock quantity. Set to 0 when out of stock.')
    display_order = models.PositiveIntegerField(default=0, help_text='Lower number = appears first')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Showcase Product'
        verbose_name_plural = 'Showcase Products'
        ordering = ['display_order', '-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while ShowcaseProduct.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        if self.discount_percent and self.discount_percent > 0:
            self.discounted_price = round(self.price * (1 - self.discount_percent / 100), 2)
        elif self.discount_percent == 0:
            self.discounted_price = None
        super().save(*args, **kwargs)

    @property
    def size_list(self):
        """Return available sizes as a list."""
        if self.available_sizes:
            return [s.strip() for s in self.available_sizes.split(',') if s.strip()]
        return []

    @property
    def savings(self):
        """Amount saved if discount is applied."""
        if self.has_discount:
            return self.price - self.discounted_price
        return 0

    @property
    def formatted_savings(self):
        if self.savings:
            return f'₹{self.savings:,.0f}'
        return ''

    @property
    def formatted_price(self):
        return f'₹{self.price:,.0f}'

    @property
    def formatted_discounted_price(self):
        if self.discounted_price:
            return f'₹{self.discounted_price:,.0f}'
        return ''

    @property
    def has_discount(self):
        return self.discount_percent > 0 and self.discounted_price is not None

    @property
    def cart_price(self):
        """Price to use for cart (discounted if available, otherwise original)."""
        if self.has_discount:
            return self.discounted_price
        return self.price

    @property
    def in_stock(self):
        """Whether this product is currently in stock."""
        return self.stock_quantity > 0

    @property
    def average_rating(self):
        """Average star rating from reviews (0 if none)."""
        reviews = self.reviews.filter(is_approved=True)
        if not reviews.exists():
            return 0
        return round(reviews.aggregate(avg=models.Avg('rating'))['avg'], 1)

    @property
    def review_count(self):
        return self.reviews.filter(is_approved=True).count()


class ProductImage(models.Model):
    """Additional images for a product (gallery views)."""
    product = models.ForeignKey(ShowcaseProduct, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='showcase/gallery/', help_text='Additional product image')
    alt_text = models.CharField(max_length=120, blank=True, default='', help_text='Image description (e.g. Back View, Detail)')
    display_order = models.PositiveIntegerField(default=0, help_text='Lower = appears first')

    class Meta:
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'
        ordering = ['display_order']

    def __str__(self):
        return f'{self.product.name} — {self.alt_text or "Image"}'


class CollectionCard(models.Model):
    """Flip cards in the Our Collections section."""
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, help_text='Text shown on the back of the flip card')
    image = models.ImageField(upload_to='collections/')
    display_order = models.PositiveIntegerField(default=0, help_text='Lower number = appears first')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Collection Card'
        verbose_name_plural = 'Collection Cards'
        ordering = ['display_order', '-created_at']

    def __str__(self):
        return self.name


class ParallaxSection(models.Model):
    """Background image for the parallax/experience section."""
    title = models.CharField(max_length=100, default='Experience Elegance')
    subtitle = models.CharField(max_length=255, default='Every piece tells a story of craftsmanship and tradition')
    background_image = models.ImageField(upload_to='parallax/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Parallax Section'
        verbose_name_plural = 'Parallax Section'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({"Active" if self.is_active else "Inactive"})'

    def save(self, *args, **kwargs):
        if self.is_active:
            ParallaxSection.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class ShopBanner(models.Model):
    """Hero banner for the Shop page — supports image or video background."""
    MEDIA_CHOICES = [
        ('pattern', 'Default Pattern'),
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    title = models.CharField(max_length=100, default='Our Shop')
    subtitle = models.CharField(max_length=255, default='Discover handcrafted lehengas that tell a story of elegance and tradition')
    badge_text = models.CharField(max_length=50, default='CURATED COLLECTION', help_text='Small badge text above the title')
    media_type = models.CharField(max_length=10, choices=MEDIA_CHOICES, default='pattern')
    background_image = models.ImageField(upload_to='shop_banner/', blank=True, null=True, help_text='Upload a banner image (used when media type is Image)')
    background_video = models.FileField(upload_to='shop_banner/videos/', blank=True, null=True, help_text='Upload a banner video — MP4 recommended')
    overlay_opacity = models.PositiveIntegerField(default=60, help_text='Dark overlay opacity 0–100 (higher = darker)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Shop Banner'
        verbose_name_plural = 'Shop Banner'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} [{self.get_media_type_display()}] ({"Active" if self.is_active else "Inactive"})'

    def save(self, *args, **kwargs):
        if self.is_active:
            ShopBanner.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @property
    def overlay_opacity_css(self):
        return self.overlay_opacity / 100


class StatItem(models.Model):
    """Individual stat cards in the Stats section."""
    number = models.CharField(max_length=30, help_text='e.g. 10K+, 500+, 100%')
    label = models.CharField(max_length=60, help_text='e.g. Happy Customers, Designs')
    icon = models.CharField(max_length=50, blank=True, default='', help_text='Font Awesome class e.g. fas fa-users (optional)')
    display_order = models.PositiveIntegerField(default=0, help_text='Lower = appears first')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Stat Item'
        verbose_name_plural = 'Stat Items'
        ordering = ['display_order']

    def __str__(self):
        return f'{self.number} — {self.label}'


class ContactInfo(models.Model):
    """Contact section info — phone, email, address, social links."""
    phone = models.CharField(max_length=30, default='+91 (123) 456-7890')
    email = models.EmailField(default='info@NowhenceClothings.com')
    address = models.CharField(max_length=200, default='Hyderabad, India')
    facebook_url = models.URLField(blank=True, default='')
    instagram_url = models.URLField(blank=True, default='https://www.instagram.com/nowhence_clothings/')
    twitter_url = models.URLField(blank=True, default='')
    pinterest_url = models.URLField(blank=True, default='')
    youtube_url = models.URLField(blank=True, default='')
    whatsapp_number = models.CharField(max_length=20, blank=True, default='', help_text='WhatsApp number with country code e.g. 919876543210')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Contact Info'
        verbose_name_plural = 'Contact Info'
        ordering = ['-created_at']

    def __str__(self):
        return f'Contact Info ({"Active" if self.is_active else "Inactive"})'

    def save(self, *args, **kwargs):
        if self.is_active:
            ContactInfo.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @property
    def whatsapp_url(self):
        if self.whatsapp_number:
            return f'https://wa.me/{self.whatsapp_number}'
        return ''

    @property
    def social_links(self):
        """Return list of active social links for template iteration."""
        links = []
        if self.facebook_url:
            links.append({'url': self.facebook_url, 'icon': 'fab fa-facebook', 'name': 'Facebook'})
        if self.instagram_url:
            links.append({'url': self.instagram_url, 'icon': 'fab fa-instagram', 'name': 'Instagram'})
        if self.twitter_url:
            links.append({'url': self.twitter_url, 'icon': 'fab fa-twitter', 'name': 'Twitter'})
        if self.pinterest_url:
            links.append({'url': self.pinterest_url, 'icon': 'fab fa-pinterest', 'name': 'Pinterest'})
        if self.youtube_url:
            links.append({'url': self.youtube_url, 'icon': 'fab fa-youtube', 'name': 'YouTube'})
        if self.whatsapp_number:
            links.append({'url': self.whatsapp_url, 'icon': 'fab fa-whatsapp', 'name': 'WhatsApp'})
        return links


class AboutPage(models.Model):
    """Singleton model for the About page content."""
    heading = models.CharField(max_length=200, default='Our Story')
    subheading = models.CharField(max_length=300, blank=True, default='The Journey Behind Nowhence Clothings')
    main_image = models.ImageField(upload_to='about/', help_text='Main portrait/image displayed on the left side of the page')
    secondary_image = models.ImageField(upload_to='about/', blank=True, null=True, help_text='Optional second image for visual depth')
    founder_name = models.CharField(max_length=100, default='Ambava')
    founder_title = models.CharField(max_length=200, default='Founder & Creative Director')
    story_text = models.TextField(help_text='The main story text about the founder and the brand')
    quote_text = models.CharField(max_length=500, blank=True, default='', help_text='An inspirational quote from the founder')
    mission_title = models.CharField(max_length=200, blank=True, default='Our Mission')
    mission_text = models.TextField(blank=True, default='', help_text='Text about the brand mission and values')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'About Page'
        verbose_name_plural = 'About Page'
        ordering = ['-created_at']

    def __str__(self):
        return f'About Page — {self.heading}'

    def save(self, *args, **kwargs):
        if self.is_active:
            AboutPage.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

class PincodeAvailability(models.Model):
    """Manage pincode-wise product availability for delivery."""
    product = models.ForeignKey(ShowcaseProduct, on_delete=models.CASCADE, related_name='pincode_availability')
    pincode = models.CharField(max_length=10, help_text='Enter the pincode (e.g., 110001)')
    is_available = models.BooleanField(default=True, help_text='Whether this product is available for delivery in this pincode')
    delivery_days = models.PositiveIntegerField(default=5, help_text='Expected delivery days for this pincode')
    extra_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Extra shipping charge for this pincode (if any)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pincode Availability'
        verbose_name_plural = 'Pincode Availabilities'
        unique_together = ('product', 'pincode')
        ordering = ['product', 'pincode']
        indexes = [
            models.Index(fields=['product', 'is_available']),
            models.Index(fields=['pincode']),
        ]

    def __str__(self):
        status = '✓ Available' if self.is_available else '✗ Unavailable'
        return f'{self.product.name} — {self.pincode} ({status})'

    @classmethod
    def is_product_available_in_pincode(cls, product_id, pincode):
        """
        Check if a product is available for delivery in a specific pincode.
        Returns: (is_available, delivery_days, extra_charge) or (False, None, 0) if not found
        """
        availability = cls.objects.filter(
            product_id=product_id,
            pincode=pincode,
            is_available=True
        ).first()
        
        if availability:
            return (True, availability.delivery_days, availability.extra_charge)
        return (False, None, 0)

    @classmethod
    def get_pincodes_for_product(cls, product_id):
        """Get all available pincodes for a product."""
        return cls.objects.filter(
            product_id=product_id,
            is_available=True
        ).values_list('pincode', flat=True)


class UserProfile(models.Model):
    """Extended profile for users — links all login methods to one account."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    google_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    facebook_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} — {self.phone or "No phone"}'


class Address(models.Model):
    """Saved addresses for customer profiles."""
    LABEL_CHOICES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=10, choices=LABEL_CHOICES, default='home')
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    address_line1 = models.CharField('Address line 1', max_length=255)
    address_line2 = models.CharField('Address line 2', max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-updated_at']

    def __str__(self):
        return f'{self.label.title()}: {self.address_line1}, {self.city} — {self.user.username}'

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


import uuid

class Order(models.Model):
    """Customer orders."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    PAYMENT_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('razorpay', 'Razorpay (Online)'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cod')
    razorpay_order_id = models.CharField(max_length=100, blank=True, default='', help_text='Razorpay order ID (order_xxx)')
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default='', help_text='Razorpay payment ID (pay_xxx)')
    razorpay_signature = models.CharField(max_length=255, blank=True, default='', help_text='Razorpay payment signature')
    shipping_full_name = models.CharField(max_length=150, blank=True)
    shipping_phone = models.CharField(max_length=20, blank=True)
    shipping_address = models.TextField(blank=True, help_text='Full shipping address')
    shipping_city = models.CharField(max_length=100, blank=True)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_pincode = models.CharField(max_length=10, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True, help_text='Courier tracking number')
    courier_name = models.CharField(max_length=100, blank=True, help_text='e.g. Delhivery, BlueDart, India Post')
    estimated_delivery = models.DateField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, help_text='Internal notes')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=30, blank=True, default='', help_text='Coupon code used for this order')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Discount from coupon')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cancellation_reason = models.TextField(blank=True, default='', help_text='Reason given by customer when cancelling')
    cancelled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f'Order #{self.order_number} — {self.user.username}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f'HOA-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    @property
    def formatted_total(self):
        return f'₹{self.total:,.0f}'

    @property
    def status_progress(self):
        """Return a 0-100 progress percentage for tracking UI."""
        progress_map = {
            'pending': 10,
            'confirmed': 30,
            'shipped': 55,
            'out_for_delivery': 80,
            'delivered': 100,
            'cancelled': 0,
        }
        return progress_map.get(self.status, 0)

    @property
    def can_cancel(self):
        """Order can be cancelled while it's pending or confirmed (not yet shipped)."""
        return self.status in ('pending', 'confirmed')

    @property
    def can_return(self):
        """Order can be returned once delivered."""
        return self.status == 'delivered'


class OrderItem(models.Model):
    """Individual items within an order."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(ShowcaseProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    product_name = models.CharField(max_length=150, help_text='Snapshot of product name at time of order')
    product_image = models.ImageField(upload_to='orders/', blank=True, null=True)
    size = models.CharField(max_length=10, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Price per unit at time of order')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        return f'{self.product_name} × {self.quantity}'

    def save(self, *args, **kwargs):
        self.total = self.price * self.quantity
        super().save(*args, **kwargs)

    @property
    def formatted_price(self):
        return f'₹{self.price:,.0f}'

    @property
    def formatted_total(self):
        return f'₹{self.total:,.0f}'


class ReturnExchange(models.Model):
    """Return or exchange requests for orders."""
    TYPE_CHOICES = [
        ('return', 'Return'),
        ('exchange', 'Exchange'),
    ]
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('pickup_scheduled', 'Pickup Scheduled'),
        ('picked_up', 'Picked Up'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]
    REASON_CHOICES = [
        ('wrong_size', 'Wrong Size'),
        ('defective', 'Defective / Damaged'),
        ('not_as_described', 'Not As Described'),
        ('wrong_item', 'Wrong Item Received'),
        ('change_of_mind', 'Change of Mind'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='returns')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='returns')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='returns', null=True, blank=True)
    request_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='return')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='other')
    details = models.TextField(blank=True, help_text='Additional details about the issue')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    admin_notes = models.TextField(blank=True, help_text='Internal notes from admin')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Return / Exchange'
        verbose_name_plural = 'Returns & Exchanges'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_request_type_display()} — Order #{self.order.order_number} ({self.get_status_display()})'

    @property
    def formatted_refund(self):
        return f'₹{self.refund_amount:,.0f}'


class ContactMessage(models.Model):
    """Messages submitted via the contact form."""
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, default='')
    subject = models.CharField(max_length=255, blank=True, default='')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Contact Messages'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} — {self.subject or "No subject"} ({"Read" if self.is_read else "Unread"})'


class Wishlist(models.Model):
    """Server-side wishlist — persists across devices for logged-in users."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(ShowcaseProduct, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist'
        unique_together = ('user', 'product')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} ♥ {self.product.name}'


class Review(models.Model):
    """Product reviews and ratings."""
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    product = models.ForeignKey(ShowcaseProduct, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(choices=RATING_CHOICES, default=5)
    title = models.CharField(max_length=150, blank=True, default='')
    comment = models.TextField(blank=True, default='')
    is_approved = models.BooleanField(default=True, help_text='Uncheck to hide this review')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        unique_together = ('product', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} — {self.product.name} ({self.rating}★)'


class Coupon(models.Model):
    """Discount coupon codes for checkout."""
    DISCOUNT_TYPE_CHOICES = [
        ('percent', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]

    code = models.CharField(max_length=30, unique=True, help_text='Coupon code (e.g. WELCOME10)')
    description = models.CharField(max_length=255, blank=True, default='')
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='percent')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, help_text='Percentage (0-100) or fixed amount in ₹')
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Minimum cart total required')
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Maximum discount cap (0 = no limit). Useful for percentage coupons.')
    usage_limit = models.PositiveIntegerField(default=0, help_text='Max total uses (0 = unlimited)')
    used_count = models.PositiveIntegerField(default=0, editable=False)
    per_user_limit = models.PositiveIntegerField(default=1, help_text='Max uses per user')
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(blank=True, null=True)
    valid_until = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'
        ordering = ['-created_at']

    def __str__(self):
        if self.discount_type == 'percent':
            return f'{self.code} — {self.discount_value:.0f}% off'
        return f'{self.code} — ₹{self.discount_value:.0f} off'

    def is_valid(self, order_total=0, user=None):
        """Check if coupon can be applied."""
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False, 'This coupon is no longer active.'
        if self.valid_from and now < self.valid_from:
            return False, 'This coupon is not yet valid.'
        if self.valid_until and now > self.valid_until:
            return False, 'This coupon has expired.'
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, 'This coupon has been fully redeemed.'
        if order_total < self.min_order_amount:
            return False, f'Minimum order of ₹{self.min_order_amount:.0f} required.'
        if user and self.per_user_limit:
            user_uses = Order.objects.filter(
                user=user,
                coupon_code__iexact=self.code,
                status__in=('confirmed', 'shipped', 'out_for_delivery', 'delivered'),
            ).count()
            if user_uses >= self.per_user_limit:
                return False, 'You have already used this coupon.'
        return True, ''

    def calculate_discount(self, order_total):
        """Return the actual discount amount."""
        if self.discount_type == 'percent':
            discount = order_total * (self.discount_value / 100)
        else:
            discount = self.discount_value
        if self.max_discount and discount > self.max_discount:
            discount = self.max_discount
        return min(discount, order_total)
