import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from mysite.views.helpers import store_otp
from mysite.views.features import review_submit
from store.models import Address, ContactMessage, Coupon, Order, OrderItem, Review, ShowcaseProduct, UserProfile


def _test_image():
    return SimpleUploadedFile(
        'test.gif',
        (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00'
            b'\x00\x00\x00\xff\xff\xff!\xf9\x04\x01'
            b'\x00\x00\x00\x00,\x00\x00\x00\x00\x01'
            b'\x00\x01\x00\x00\x02\x02D\x01\x00;'
        ),
        content_type='image/gif',
    )


class ReviewApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='alice', password='secret123')
        self.other_user = User.objects.create_user(username='bob', password='secret123')
        self.factory = RequestFactory()
        self.product = ShowcaseProduct.objects.create(
            name='Ivory Lehenga',
            slug='ivory-lehenga',
            category='bridal',
            price=Decimal('9999.00'),
            image=_test_image(),
            stock_quantity=10,
            is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            status='delivered',
            payment_status='paid',
            payment_method='cod',
            shipping_full_name='Alice',
            shipping_phone='9999999999',
            shipping_address='123 Street',
            shipping_city='Delhi',
            shipping_state='Delhi',
            shipping_pincode='110001',
            subtotal=Decimal('9999.00'),
            total=Decimal('9999.00'),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            quantity=1,
            price=Decimal('9999.00'),
            total=Decimal('9999.00'),
        )
        Review.objects.create(
            product=self.product,
            user=self.other_user,
            rating=4,
            title='Lovely work',
            comment='Great finish',
            is_approved=True,
        )

    def test_review_submit_accepts_form_posts(self):
        request = self.factory.post(
            reverse('review_submit'),
            data={
                'product_id': self.product.id,
                'rating': 5,
                'title': 'Perfect',
                'comment': 'Beautiful craftsmanship',
            },
        )
        request.user = self.user
        response = review_submit(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['review']['rating'], 5)
        self.assertEqual(
            Review.objects.get(product=self.product, user=self.user).title,
            'Perfect',
        )

    def test_review_list_returns_summary_and_frontend_keys(self):
        response = self.client.get(reverse('review_list'), {'product_id': self.product.id})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['total'], 1)
        self.assertEqual(payload['average'], 4.0)
        self.assertEqual(payload['reviews'][0]['date'], payload['reviews'][0]['created_at'])
        self.assertFalse(payload['reviews'][0]['verified'])


class ContactAndAuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.victim = User.objects.create_user(
            username='9999999999',
            email='victim@example.com',
            password='secret123',
        )
        self.phone = '+919999999999'
        self.raw_phone = '9999999999'

    def test_contact_submit_accepts_form_posts(self):
        response = self.client.post(
            reverse('contact_submit'),
            data={
                'name': 'Asha',
                'email': 'asha@example.com',
                'phone': '9999999999',
                'subject': 'Need help',
                'message': 'Please share delivery details.',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(ContactMessage.objects.count(), 1)
        saved_message = ContactMessage.objects.get()
        self.assertEqual(saved_message.name, 'Asha')
        self.assertEqual(saved_message.subject, 'Need help')

    def test_send_otp_requires_csrf_and_succeeds_with_token(self):
        csrf_client = Client(enforce_csrf_checks=True)

        blocked = csrf_client.post(
            reverse('send_otp'),
            data=json.dumps({'phone': self.raw_phone}),
            content_type='application/json',
        )
        self.assertEqual(blocked.status_code, 403)

        csrf_token = 'b' * 32
        csrf_client.cookies['csrftoken'] = csrf_token
        allowed = csrf_client.post(
            reverse('send_otp'),
            data=json.dumps({'phone': self.raw_phone}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.json()['ok'])

    def test_customer_phone_login_does_not_take_over_existing_numeric_username(self):
        store_otp(self.phone, '123456', self.raw_phone)

        response = self.client.post(
            reverse('customer_login'),
            data={
                'action': 'phone_login',
                'phone': self.raw_phone,
                'otp': '123456',
                '_ajax': '1',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])

        self.assertNotEqual(int(self.client.session['_auth_user_id']), self.victim.pk)
        profile = UserProfile.objects.get(phone=self.phone)
        self.assertNotEqual(profile.user_id, self.victim.pk)
        self.assertTrue(profile.user.username.startswith('phone_'))

    def test_checkout_phone_login_does_not_take_over_existing_numeric_username(self):
        store_otp(self.phone, '654321', self.raw_phone)

        response = self.client.post(
            reverse('checkout_login'),
            data={
                'action': 'phone_login',
                'phone': self.raw_phone,
                'otp': '654321',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertNotEqual(payload['user']['username'], self.victim.username)
        self.assertNotEqual(int(self.client.session['_auth_user_id']), self.victim.pk)


class CheckoutApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='checkout-user',
            email='checkout@example.com',
            password='secret123',
        )
        self.client.force_login(self.user)
        self.product = ShowcaseProduct.objects.create(
            name='Rose Gold Lehenga',
            slug='rose-gold-lehenga',
            category='bridal',
            price=Decimal('8999.00'),
            image=_test_image(),
            stock_quantity=5,
            is_active=True,
        )

    def _payload(self, **overrides):
        payload = {
            'items': [{
                'name': self.product.name,
                'slug': self.product.slug,
                'price': float(self.product.price),
                'quantity': 1,
                'image': '',
                'size': 'M',
            }],
            'email': 'checkout@example.com',
            'save_address': False,
            'payment_method': 'cod',
            'coupon_code': '',
            'discount_amount': 0,
            'shipping': {
                'full_name': 'Checkout User',
                'phone': '9999999999',
                'address_line1': '123 Market Road',
                'address_line2': '',
                'city': 'Delhi',
                'state': 'Delhi',
                'pincode': '110001',
            },
        }
        payload.update(overrides)
        return payload

    def test_place_order_rejects_invalid_coupon_instead_of_silently_ignoring_it(self):
        Coupon.objects.create(
            code='EXPIRED50',
            discount_type='fixed',
            discount_value=Decimal('500.00'),
            is_active=False,
        )

        response = self.client.post(
            reverse('place_order'),
            data=json.dumps(self._payload(coupon_code='EXPIRED50')),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload['ok'])
        self.assertIn('coupon', payload['error'].lower())
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)

    def test_place_order_rejects_items_missing_required_size(self):
        response = self.client.post(
            reverse('place_order'),
            data=json.dumps(self._payload(items=[{
                'name': self.product.name,
                'slug': self.product.slug,
                'price': float(self.product.price),
                'quantity': 1,
                'image': '',
                'size': '',
            }])),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload['ok'])
        self.assertIn('size', payload['error'].lower())
        self.assertEqual(Order.objects.count(), 0)

    @override_settings(RAZORPAY_KEY_ID='', RAZORPAY_KEY_SECRET='')
    def test_razorpay_fallback_to_cod_finalizes_order_side_effects(self):
        coupon = Coupon.objects.create(
            code='WELCOME10',
            discount_type='percent',
            discount_value=Decimal('10.00'),
            min_order_amount=Decimal('1000.00'),
            per_user_limit=1,
            is_active=True,
        )

        response = self.client.post(
            reverse('place_order'),
            data=json.dumps(self._payload(payment_method='razorpay', coupon_code='WELCOME10')),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['payment_method'], 'cod')

        order = Order.objects.get(order_number=payload['order_number'])
        self.product.refresh_from_db()
        coupon.refresh_from_db()

        self.assertEqual(order.payment_method, 'cod')
        self.assertEqual(order.status, 'confirmed')
        self.assertEqual(self.product.stock_quantity, 4)
        self.assertEqual(coupon.used_count, 1)

    def test_pending_online_order_does_not_consume_per_user_coupon_limit(self):
        Coupon.objects.create(
            code='WELCOME10',
            discount_type='percent',
            discount_value=Decimal('10.00'),
            min_order_amount=Decimal('1000.00'),
            per_user_limit=1,
            is_active=True,
        )
        Order.objects.create(
            user=self.user,
            status='pending',
            payment_status='pending',
            payment_method='razorpay',
            coupon_code='welcome10',
            subtotal=Decimal('8999.00'),
            total=Decimal('8099.10'),
        )

        response = self.client.post(
            reverse('place_order'),
            data=json.dumps(self._payload(coupon_code='WELCOME10')),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(Order.objects.filter(coupon_code__iexact='WELCOME10').count(), 2)

    def test_place_order_uses_cart_slug_to_resolve_the_correct_product(self):
        alternate_product = ShowcaseProduct.objects.create(
            name=self.product.name,
            slug='rose-gold-lehenga-alt',
            category='bridal',
            price=Decimal('12999.00'),
            image=_test_image(),
            stock_quantity=2,
            is_active=True,
        )

        response = self.client.post(
            reverse('place_order'),
            data=json.dumps(self._payload(items=[{
                'name': self.product.name,
                'slug': alternate_product.slug,
                'price': float(alternate_product.price),
                'quantity': 1,
                'image': '',
                'size': 'M',
            }])),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])

        order = Order.objects.get(order_number=payload['order_number'])
        order_item = order.items.get()

        self.assertEqual(order_item.product, alternate_product)
        self.assertEqual(order_item.product_name, alternate_product.name)
        self.assertEqual(order.total, alternate_product.price)

    def test_place_order_saves_address_when_requested(self):
        response = self.client.post(
            reverse('place_order'),
            data=json.dumps(self._payload(save_address=True)),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])

        saved_address = Address.objects.get(user=self.user)
        self.assertEqual(saved_address.full_name, 'Checkout User')
        self.assertEqual(saved_address.address_line1, '123 Market Road')
        self.assertTrue(saved_address.is_default)

    def test_place_order_updates_existing_saved_address_instead_of_creating_duplicate(self):
        existing_address = Address.objects.create(
            user=self.user,
            label='work',
            full_name='Old Name',
            phone='8888888888',
            address_line1='Old Address',
            address_line2='',
            city='Delhi',
            state='Delhi',
            pincode='110001',
            is_default=True,
        )

        response = self.client.post(
            reverse('place_order'),
            data=json.dumps(self._payload(
                save_address=True,
                address_id=str(existing_address.pk),
                shipping={
                    'full_name': 'Updated User',
                    'phone': '9999999999',
                    'address_line1': '456 Updated Road',
                    'address_line2': 'Suite 9',
                    'city': 'Gurugram',
                    'state': 'Haryana',
                    'pincode': '122001',
                },
            )),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(Address.objects.filter(user=self.user).count(), 1)

        existing_address.refresh_from_db()
        self.assertEqual(existing_address.label, 'work')
        self.assertEqual(existing_address.full_name, 'Updated User')
        self.assertEqual(existing_address.address_line1, '456 Updated Road')
        self.assertEqual(existing_address.city, 'Gurugram')
        self.assertTrue(existing_address.is_default)

    def test_address_save_keeps_only_one_default_address(self):
        original_default = Address.objects.create(
            user=self.user,
            label='home',
            full_name='Original Default',
            phone='9999999999',
            address_line1='1 First Lane',
            address_line2='',
            city='Delhi',
            state='Delhi',
            pincode='110001',
            is_default=True,
        )

        response = self.client.post(
            reverse('address_save'),
            data={
                'full_name': 'New Default',
                'phone': '9999999999',
                'address_line1': '2 Second Lane',
                'address_line2': '',
                'city': 'Noida',
                'state': 'UP',
                'pincode': '201301',
                'label': 'work',
                'is_default': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

        original_default.refresh_from_db()
        new_default = Address.objects.get(pk=response.json()['address']['id'])

        self.assertFalse(original_default.is_default)
        self.assertTrue(new_default.is_default)
        self.assertEqual(Address.objects.filter(user=self.user, is_default=True).count(), 1)

    def test_checkout_login_requires_csrf_and_succeeds_with_token(self):
        csrf_client = Client(enforce_csrf_checks=True)

        blocked = csrf_client.post(
            reverse('checkout_login'),
            data={
                'action': 'login',
                'username': self.user.username,
                'password': 'secret123',
            },
        )
        self.assertEqual(blocked.status_code, 403)

        csrf_token = 'a' * 32
        csrf_client.cookies['csrftoken'] = csrf_token
        allowed = csrf_client.post(
            reverse('checkout_login'),
            data={
                'action': 'login',
                'username': self.user.username,
                'password': 'secret123',
            },
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(allowed.status_code, 200)
        payload = allowed.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['user']['username'], self.user.username)

    def test_cancel_confirmed_order_restocks_and_releases_coupon(self):
        coupon = Coupon.objects.create(
            code='WELCOME10',
            discount_type='percent',
            discount_value=Decimal('10.00'),
            min_order_amount=Decimal('1000.00'),
            usage_limit=5,
            per_user_limit=1,
            used_count=1,
            is_active=True,
        )
        self.product.stock_quantity = 4
        self.product.save(update_fields=['stock_quantity'])
        order = Order.objects.create(
            user=self.user,
            status='confirmed',
            payment_status='paid',
            payment_method='razorpay',
            shipping_full_name='Checkout User',
            shipping_phone='9999999999',
            shipping_address='123 Market Road',
            shipping_city='Delhi',
            shipping_state='Delhi',
            shipping_pincode='110001',
            subtotal=Decimal('8999.00'),
            discount_amount=Decimal('900.00'),
            total=Decimal('8099.00'),
            coupon_code=coupon.code,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            quantity=1,
            price=Decimal('8999.00'),
            total=Decimal('8999.00'),
            size='M',
        )

        response = self.client.post(
            reverse('cancel_order'),
            data={'order_id': str(order.pk), 'reason': 'Changed my mind'},
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.product.refresh_from_db()
        coupon.refresh_from_db()

        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(order.payment_status, 'refunded')
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertEqual(coupon.used_count, 0)
        self.assertTrue(response.json()['refund'])

    def test_cancel_pending_online_order_marks_payment_failed_without_side_effects(self):
        coupon = Coupon.objects.create(
            code='WELCOME10',
            discount_type='percent',
            discount_value=Decimal('10.00'),
            min_order_amount=Decimal('1000.00'),
            usage_limit=5,
            per_user_limit=1,
            used_count=0,
            is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            status='pending',
            payment_status='pending',
            payment_method='razorpay',
            shipping_full_name='Checkout User',
            shipping_phone='9999999999',
            shipping_address='123 Market Road',
            shipping_city='Delhi',
            shipping_state='Delhi',
            shipping_pincode='110001',
            subtotal=Decimal('8999.00'),
            discount_amount=Decimal('900.00'),
            total=Decimal('8099.00'),
            coupon_code=coupon.code,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            quantity=1,
            price=Decimal('8999.00'),
            total=Decimal('8999.00'),
            size='M',
        )

        response = self.client.post(
            reverse('cancel_order'),
            data={'order_id': str(order.pk), 'reason': 'Payment cancelled'},
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.product.refresh_from_db()
        coupon.refresh_from_db()

        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(order.payment_status, 'failed')
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertEqual(coupon.used_count, 0)
        self.assertFalse(response.json()['refund'])

    def test_address_delete_promotes_another_saved_address_to_default(self):
        original_default = Address.objects.create(
            user=self.user,
            label='home',
            full_name='Original Default',
            phone='9999999999',
            address_line1='1 First Lane',
            address_line2='',
            city='Delhi',
            state='Delhi',
            pincode='110001',
            is_default=True,
        )
        replacement = Address.objects.create(
            user=self.user,
            label='work',
            full_name='Replacement',
            phone='8888888888',
            address_line1='2 Second Lane',
            address_line2='Suite 4',
            city='Noida',
            state='UP',
            pincode='201301',
            is_default=False,
        )

        response = self.client.post(
            reverse('address_delete'),
            data={'address_id': str(original_default.pk)},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['new_default_id'], replacement.pk)

        replacement.refresh_from_db()
        self.assertTrue(replacement.is_default)
        self.assertFalse(Address.objects.filter(pk=original_default.pk).exists())
        self.assertEqual(Address.objects.filter(user=self.user, is_default=True).count(), 1)
